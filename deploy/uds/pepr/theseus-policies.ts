// SPDX-License-Identifier: AGPL-3.0-only
// THESEUS — cluster-enforced rails (Pepr admission policy)
// =============================================================================
// This Pepr Capability turns the THESEUS rails into *admission controls* that the
// cluster enforces at Pod create/update time. It is the cluster-side twin of the
// in-package securityContext template in zarf/manifests/job.yaml — but instead of
// trusting each manifest to opt in, the admission webhook DENIES anything that
// violates a rail.
//
// RAILS ENFORCED (decision-support, NOT autonomous ship control):
//   1. human-in-command — a Pod/Job that declares an autonomy/decision *action*
//      must carry an explicit human-approval annotation that is BOUND to a real
//      sealed decision in the tamper-evident record, or it is denied.
//      (Theseus drafts the call; a human approves; the approval is sealed; the
//       webhook makes "no sealed human decision, no autonomy action" a hard rule.)
//      This is NOT a presence check: a non-empty approver string is necessary but
//      NOT sufficient. The pod must also carry a canonical approval-record-ref that
//      pins a leaf_hash, plus a verify init-container wired to that same ref — and,
//      when the record is mounted to the controller, the webhook chain-verifies the
//      ref against the record at admission time. "type x = approved" -> DENIED.
//   2. no-egress / contained — Theseus model + explainer pods may not run with
//      hostNetwork, hostPID, hostIPC, privileged, or privilege-escalation. They
//      must declare the in-mesh egress posture label so UDS default-deny + a
//      NetworkPolicy can be reasoned about. (SWAN-side only; combat air-gapped.)
//   3. append-only record / hardened workload — the tamper-EVIDENT record volume
//      must be mounted read-only; hostPath escapes are denied; and Theseus pods
//      must run non-root, readOnlyRootFilesystem, drop ALL caps.
//
// NON-GOALS / HONEST SCOPE (no overclaim):
//   - This is *admission-time* enforcement. It does not by itself make egress
//     impossible (that is Istio default-deny + a NetworkPolicy, shipped by the UDS
//     Package CR); it guarantees no Theseus pod can *declare* an escape hatch.
//   - tamper-EVIDENT, not tamper-proof: rule 3 keeps the on-disk record volume
//     read-only to the workload so the chain can't be silently rewritten in place;
//     detection still lives in referee/chain.py's offline verifier.
//   - "deployable; ATO is the gate" — these controls are evidence toward AC-6 /
//     SC-7 / AU-9, not an authorization.
//
// SCOPING: this Capability is scoped to Theseus namespaces (see `namespaces`
// below) so it never adjudicates unrelated platform workloads (uds-core, etc.).
//
// API: verified against pepr@1.2.1 and kubernetes-fluent-client@3.11.7.
//   - When(a.Pod).IsCreatedOrUpdated().InNamespace(...).Validate(req => ...)
//   - req.Raw is a V1Pod (a.Pod === kind.Pod === V1Pod re-export).
//   - req.Approve(warnings?) / req.Deny(message?, code?, warnings?).
//   - req.HasLabel(k) / req.HasAnnotation(k) are convenience helpers on metadata.
// =============================================================================

import { Capability, a, Log } from "pepr";
import type { V1Container, V1PodSpec, V1SecurityContext, V1Volume } from "@kubernetes/client-node";
import {
  parseRef,
  resolveAgainstControllerRecord,
  verifyGateProblem,
  VERIFY_INIT_NAME,
  VERIFY_REF_ENV,
} from "./record-binding";

/** Pod spec or an empty spec — keeps the V1PodSpec shape instead of widening to `{}`. */
const EMPTY_SPEC: V1PodSpec = { containers: [] };

// ---------------------------------------------------------------------------
// Label / annotation contract (the "API" manifests opt into).
// Keep these stable — fixtures, charts, and the UDS Package CR reference them.
// ---------------------------------------------------------------------------
const NS_THESEUS = ["theseus", "theseus-edge"]; // edit to match your deploy ns

// A workload that is part of Theseus and therefore subject to the hardening rail.
const LBL_PART_OF = "app.kubernetes.io/part-of"; // value "theseus"
const VAL_PART_OF = "theseus";

// rule 1: declares an autonomy / decision action -> requires a human approval that
//   is BOUND to a sealed leaf in the tamper-evident record (not just a non-empty string).
//   theseus.forceos.ai/action: "decision" | "autonomy" | "model-promote" | ...
const LBL_ACTION = "theseus.forceos.ai/action";
//   theseus.forceos.ai/human-approved-by: "<sailor-id / ticket>"  (necessary, NOT sufficient)
const ANN_APPROVED_BY = "theseus.forceos.ai/human-approved-by";
//   REQUIRED canonical ref pinning the sealed approval leaf:
//     theseus-record://<kind>/<obs_id>@sha256:<64hex>
//   e.g. theseus-record://human_decision/accepted:CTC-7@sha256:2547e578…6628
//   This is what the webhook resolves + chain-verifies; without it the action is DENIED.
const ANN_APPROVAL_REF = "theseus.forceos.ai/approval-record-ref";

// rule 2: model / explainer pods must declare the contained-egress posture so
// default-deny + NetworkPolicy is auditable. Value is informational; presence is
// what's enforced here (the actual deny is Istio/NetworkPolicy, shipped by UDS).
const LBL_EGRESS = "theseus.forceos.ai/egress"; // expected value "none"
const VAL_EGRESS_NONE = "none";
// roles that handle SWAN-side data and must be contained.
const CONTAINED_ROLES = new Set(["model", "explainer", "inference", "edge-runner"]);
const LBL_ROLE = "theseus.forceos.ai/role";

// rule 3: the tamper-evident record volume. Any volume whose name matches, or any
// mount at this path, must be read-only to the workload.
const RECORD_VOLUME_NAMES = new Set(["theseus-record", "referee-record", "record"]);
const RECORD_MOUNT_PATHS = ["/var/lib/theseus/record", "/work/out/record", "/out/record"];

// ---------------------------------------------------------------------------
// Small pure helpers (kept dependency-free for auditability).
// ---------------------------------------------------------------------------

/** All containers in a pod spec (init + regular + ephemeral). */
function allContainers(pod: a.Pod): V1Container[] {
  const s = pod.spec ?? EMPTY_SPEC;
  return [
    ...(s.containers ?? []),
    ...(s.initContainers ?? []),
    ...((s.ephemeralContainers ?? []) as unknown as V1Container[]),
  ];
}

/** Effective securityContext booleans, treating pod-level as the default. */
function effective(
  pod: a.Pod,
  c: V1Container,
): {
  runAsNonRoot?: boolean;
  readOnlyRootFilesystem?: boolean;
  allowPrivilegeEscalation?: boolean;
  privileged?: boolean;
  dropsAll: boolean;
} {
  const podSc = pod.spec?.securityContext ?? ({} as V1SecurityContext);
  const cSc = c.securityContext ?? ({} as V1SecurityContext);

  const runAsNonRoot = cSc.runAsNonRoot ?? podSc.runAsNonRoot;
  // readOnlyRootFilesystem is container-only in the K8s schema.
  const readOnlyRootFilesystem = cSc.readOnlyRootFilesystem;
  const allowPrivilegeEscalation = cSc.allowPrivilegeEscalation;
  const privileged = cSc.privileged;

  const drops = (cSc.capabilities?.drop ?? []).map(d => String(d).toUpperCase());
  const dropsAll = drops.includes("ALL");

  return { runAsNonRoot, readOnlyRootFilesystem, allowPrivilegeEscalation, privileged, dropsAll };
}

// ---------------------------------------------------------------------------
// The Capability.
// ---------------------------------------------------------------------------
export const TheseusPolicies = new Capability({
  name: "theseus-policies",
  description:
    "Cluster-enforces the THESEUS rails as admission controls: human-in-command, contained (no-egress) posture, and append-only/hardened workloads. Decision-support only — never autonomous ship control.",
  // Scope to Theseus namespaces so we never adjudicate platform/uds-core workloads.
  namespaces: NS_THESEUS,
});

const { When } = TheseusPolicies;

// === RULE 1 — HUMAN-IN-COMMAND (record-bound) =============================
// Any Pod that declares an autonomy/decision action must carry a human approval
// that BINDS to a real, sealed, chain-verifying decision in the tamper-evident
// record. A non-empty approver string is necessary but NOT sufficient — this is
// the fix for the "type any string = approved" kill-shot.
//
// Enforced here, in order (deny on the first failure):
//   A1. non-empty approver id           (who approved)
//   A2. canonical approval-record-ref   (WHICH sealed leaf; pins a leaf_hash)
//   A3. a verify init-container wired to the SAME ref + a record mount (Layer C
//       apparatus must be present — the runtime gate that re-verifies in-cluster)
//   B.  IF the record is mounted to the controller (env THESEUS_RECORD_DIR): read
//       chain.jsonl and chain-verify the ref against it NOW. Forged hash / absent
//       leaf / SNAPped chain -> DENIED at admission. (When not mounted, B is
//       skipped as advisory and A3's init-container is the binding — stated plainly
//       in the warning so the operator knows what is enforced vs deferred.)
//
// The decision is factored into the pure, exported `evaluateRule1` so the offline
// verify harness (deploy/uds/admission-tests/verify.mjs) exercises the EXACT code
// admission runs — against a genuinely sealed record — with no logic duplication or
// drift. The .Validate wrapper only translates the decision into Pepr's
// req.Deny / req.Approve. (Pepr v1.2.1: Validate supports async; Deny(msg, code?,
// warnings?); Approve(warnings?).)

/** Minimal pod shape evaluateRule1 reads — kept structural so the harness can call
 *  it with a parsed-YAML pod without depending on the full V1Pod type machinery. */
export interface Rule1Pod {
  metadata?: {
    name?: string;
    namespace?: string;
    labels?: Record<string, string>;
    annotations?: Record<string, string>;
  };
  spec?: { initContainers?: Parameters<typeof verifyGateProblem>[0] };
}

/** The rule-1 admission decision: deny (with message+code) or approve (with warnings).
 *  This IS the enforcement logic; the .Validate callback below is a thin translator. */
export type Rule1Decision =
  | { deny: true; message: string; code: number }
  | { deny: false; warnings: string[] };

/**
 * Pure, dependency-light rule-1 evaluator. Same ordered checks A1 -> A2 -> A3 -> B.
 * `recordDir` (defaults to THESEUS_RECORD_DIR) lets the harness drive Layer B against
 * a real sealed record dir; pass null to force the Layer-B-skipped (advisory) path.
 */
export function evaluateRule1(pod: Rule1Pod, recordDir?: string | null): Rule1Decision {
  const md = pod.metadata ?? {};
  const action = (md.labels ?? {})[LBL_ACTION] ?? "";
  const ann = md.annotations ?? {};
  const approver = ann[ANN_APPROVED_BY]?.trim();
  const refRaw = ann[ANN_APPROVAL_REF]?.trim();

  // A1 — who approved.
  if (!approver) {
    return {
      deny: true,
      code: 403,
      message:
        `THESEUS rail 1 (human-in-command): pod declares action "${action}" but has no ` +
        `human approver. Set annotation "${ANN_APPROVED_BY}" to a non-empty approver id. ` +
        `Theseus drafts the call; a human approves it.`,
    };
  }

  // A2 — WHICH sealed leaf. The ref is REQUIRED and must be canonical (it pins a
  // leaf_hash). This is the line that kills "type x = approved": a non-empty
  // approver alone no longer passes; there must be a ref naming a real leaf.
  const ref = parseRef(refRaw);
  if (!ref) {
    return {
      deny: true,
      code: 403,
      message:
        `THESEUS rail 1 (human-in-command): pod declares action "${action}" approved by ` +
        `"${approver}" but its "${ANN_APPROVAL_REF}" is ${refRaw ? "MALFORMED" : "MISSING"}. ` +
        `A human approver string is not enough — it must be bound to a sealed decision. ` +
        `Provide a canonical ref: theseus-record://<kind>/<obs_id>@sha256:<64hex> ` +
        `(e.g. theseus-record://human_decision/accepted:CTC-7@sha256:<leafhash>). ` +
        `This is the leaf the watch officer's ACCEPT/OVERRIDE sealed via POST /api/decision.`,
    };
  }

  // A3 — the runtime verify gate must be present and wired to THIS ref. Even when
  // the controller cannot read the record (Layer B skipped), the pod cannot run
  // its decision action until this init-container re-verifies the ref in-cluster.
  const gateProblem = verifyGateProblem(pod.spec?.initContainers, ref.raw, RECORD_MOUNT_PATHS);
  if (gateProblem) {
    return {
      deny: true,
      code: 403,
      message:
        `THESEUS rail 1 (human-in-command): the approval ref must be backed by a runtime ` +
        `verify gate. ${gateProblem} The gate runs referee/chain.py verify_dir against the ` +
        `mounted record and fails the pod if the ref does not chain to a sealed leaf.`,
    };
  }

  // B — in-process chain resolve at admission when the record is mounted to the
  // controller. This is the live flex: a forged ref is rejected HERE, before the
  // pod is ever admitted, not only at runtime.
  const warnings: string[] = [];
  const probe = resolveAgainstControllerRecord(ref, recordDir);
  if (probe.reachable) {
    if (!probe.result.ok) {
      return {
        deny: true,
        code: 403,
        message:
          `THESEUS rail 1 (human-in-command): approval ref does NOT resolve to a sealed, ` +
          `chain-verifying decision in the tamper-evident record. ${probe.result.message}. ` +
          `The cluster admits a decision action only when its approval chains to a real sealed leaf.`,
      };
    }
    warnings.push(
      `THESEUS rail 1: approval ref VERIFIED at admission against the controller-mounted ` +
        `record — ${probe.result.message}. Approved by "${approver}".`,
    );
  } else {
    // Honest disclosure of what is enforced vs deferred when B can't run.
    warnings.push(
      `THESEUS rail 1: ref structurally bound (canonical + wired to the "${VERIFY_INIT_NAME}" ` +
        `init-container via ${VERIFY_REF_ENV}); the chain-verify of this ref runs in-cluster at ` +
        `pod start. Set env THESEUS_RECORD_DIR on the controller to also chain-verify at admission.`,
    );
  }

  return { deny: false, warnings };
}

// Applies to bare Pods and Pods created by Jobs/Deployments alike (we validate the
// Pod, which is what schedules). The *action* label is the trigger, so a stray
// autonomy pod cannot sneak in regardless of part-of.
When(a.Pod)
  .IsCreatedOrUpdated()
  .InNamespace(...NS_THESEUS)
  .WithLabel(LBL_ACTION)
  .Validate(async req => {
    const md = req.Raw.metadata ?? {};
    const ctx = { action: (md.labels ?? {})[LBL_ACTION] ?? "", ns: md.namespace, name: md.name };
    const decision = evaluateRule1(req.Raw as Rule1Pod);
    if (decision.deny) {
      Log.warn({ ...ctx }, `THESEUS rail 1: denied — ${decision.message.split(".")[0]}`);
      return req.Deny(decision.message, decision.code);
    }
    return req.Approve(decision.warnings);
  });

// === RULE 2 — CONTAINED / NO-EGRESS POSTURE ===============================
// Theseus pods (and especially model/explainer/inference roles) must not declare
// a network escape hatch, and contained roles must carry the egress=none posture
// label so UDS default-deny + NetworkPolicy is auditable. The hard egress block
// itself is Istio default-deny + the NetworkPolicy shipped by the UDS Package CR;
// here we guarantee no Theseus pod can *opt out* of containment.
When(a.Pod)
  .IsCreatedOrUpdated()
  .InNamespace(...NS_THESEUS)
  .WithLabel(LBL_PART_OF, VAL_PART_OF)
  .Validate(req => {
    const pod = req.Raw;
    const spec = pod.spec ?? EMPTY_SPEC;

    if (spec.hostNetwork) {
      return req.Deny(
        "THESEUS rail 2 (contained): hostNetwork is forbidden — it bypasses the " +
          "mesh and default-deny egress. SWAN-side only; combat systems are air-gapped.",
        403,
      );
    }
    if (spec.hostPID || spec.hostIPC) {
      return req.Deny(
        "THESEUS rail 2 (contained): hostPID/hostIPC are forbidden — node-namespace " +
          "escapes break containment of the edge node.",
        403,
      );
    }

    // No container may run privileged (also covered by rule 3, kept here for the
    // egress/containment story: privileged ~= raw network/host access).
    for (const c of allContainers(pod)) {
      if (c.securityContext?.privileged) {
        return req.Deny(
          `THESEUS rail 2 (contained): container "${c.name}" requests privileged — ` +
            "forbidden. Privileged pods can reconfigure host networking and escape egress controls.",
          403,
        );
      }
    }

    // Contained roles must declare the egress posture so the NetworkPolicy is auditable.
    const role = (pod.metadata?.labels ?? {})[LBL_ROLE];
    if (role && CONTAINED_ROLES.has(role)) {
      const egress = (pod.metadata?.labels ?? {})[LBL_EGRESS];
      if (egress !== VAL_EGRESS_NONE) {
        return req.Deny(
          `THESEUS rail 2 (contained): role "${role}" handles SWAN-side data and must ` +
            `declare label "${LBL_EGRESS}=${VAL_EGRESS_NONE}" so default-deny egress is ` +
            `auditable. The actual deny is enforced by Istio default-deny + the UDS ` +
            `Package NetworkPolicy; this label records the intended posture.`,
          403,
        );
      }
    }

    return req.Approve();
  });

// === RULE 3 — APPEND-ONLY RECORD + HARDENED WORKLOAD ======================
// For every Theseus pod:
//   (a) the tamper-evident record volume must be mounted read-only to the
//       workload (no in-place rewrite of the hash chain), and no hostPath escape;
//   (b) every container must run non-root, readOnlyRootFilesystem, drop ALL caps,
//       no privilege escalation — matching zarf/manifests/job.yaml's template.
When(a.Pod)
  .IsCreatedOrUpdated()
  .InNamespace(...NS_THESEUS)
  .WithLabel(LBL_PART_OF, VAL_PART_OF)
  .Validate(req => {
    const pod = req.Raw;
    const spec = pod.spec ?? EMPTY_SPEC;
    const volumes: V1Volume[] = spec.volumes ?? [];

    // (a.1) No hostPath volumes at all on Theseus pods — a hostPath is a record /
    // filesystem escape and breaks airgap-bundle hermeticity.
    for (const v of volumes) {
      if (v.hostPath) {
        return req.Deny(
          `THESEUS rail 3 (append-only/hermetic): volume "${v.name}" is a hostPath ` +
            `(${v.hostPath.path ?? "?"}). hostPath is forbidden on Theseus pods — it can ` +
            `escape the record's append-only guarantee and the airgap bundle boundary. ` +
            `Use an emptyDir, configMap (read-only source), or a PVC.`,
          403,
        );
      }
    }

    // Identify which volumes are "the record" by well-known name.
    const recordVolNames = new Set(
      volumes.filter(v => RECORD_VOLUME_NAMES.has(v.name)).map(v => v.name),
    );

    // (a.2) Every mount of a record volume — or any mount at a record path — must
    // be readOnly. The chain is append-only via referee/chain.py; the *volume*
    // must not be writable-in-place from the workload (tamper-EVIDENT integrity).
    for (const c of allContainers(pod)) {
      for (const m of c.volumeMounts ?? []) {
        const isRecordByVol = recordVolNames.has(m.name);
        const isRecordByPath = RECORD_MOUNT_PATHS.some(
          p => m.mountPath === p || m.mountPath.startsWith(p + "/"),
        );
        if ((isRecordByVol || isRecordByPath) && m.readOnly !== true) {
          return req.Deny(
            `THESEUS rail 3 (append-only): container "${c.name}" mounts the tamper-` +
              `evident record ("${m.name}" at "${m.mountPath}") writable. It must be ` +
              `readOnly: true. The record is appended only by the sealing path, never ` +
              `rewritten in place. (tamper-EVIDENT, not tamper-proof — detection is the ` +
              `offline verifier; this stops silent in-place edits.)`,
            403,
          );
        }
      }
    }

    // (b) Hardened workload — match the zarf job.yaml securityContext template.
    for (const c of allContainers(pod)) {
      const sc = effective(pod, c);

      if (sc.privileged) {
        return req.Deny(
          `THESEUS rail 3 (hardened): container "${c.name}" is privileged — forbidden.`,
          403,
        );
      }
      if (sc.runAsNonRoot !== true) {
        return req.Deny(
          `THESEUS rail 3 (hardened): container "${c.name}" must set ` +
            `securityContext.runAsNonRoot: true (pod- or container-level). AC-6 least privilege.`,
          403,
        );
      }
      if (sc.readOnlyRootFilesystem !== true) {
        return req.Deny(
          `THESEUS rail 3 (hardened): container "${c.name}" must set ` +
            `securityContext.readOnlyRootFilesystem: true. Use an emptyDir for scratch.`,
          403,
        );
      }
      if (sc.allowPrivilegeEscalation !== false) {
        return req.Deny(
          `THESEUS rail 3 (hardened): container "${c.name}" must set ` +
            `securityContext.allowPrivilegeEscalation: false.`,
          403,
        );
      }
      if (!sc.dropsAll) {
        return req.Deny(
          `THESEUS rail 3 (hardened): container "${c.name}" must drop ALL Linux ` +
            `capabilities (securityContext.capabilities.drop: ["ALL"]).`,
          403,
        );
      }
    }

    // Recommend seccomp RuntimeDefault (warn, don't deny — some edge kernels lag).
    const warnings: string[] = [];
    const seccompType =
      pod.spec?.securityContext?.seccompProfile?.type ??
      allContainers(pod).find(c => c.securityContext?.seccompProfile?.type)?.securityContext
        ?.seccompProfile?.type;
    if (seccompType !== "RuntimeDefault" && seccompType !== "Localhost") {
      warnings.push(
        "THESEUS rail 3: seccompProfile.type is not RuntimeDefault/Localhost. " +
          "Recommended to match zarf/manifests/job.yaml.",
      );
    }

    return req.Approve(warnings);
  });

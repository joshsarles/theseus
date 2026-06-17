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
//      must carry an explicit human-approval annotation, or it is denied.
//      (Theseus drafts the call; a human approves. The webhook makes "no human,
//       no autonomy action" a hard cluster rule.)
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

// rule 1: declares an autonomy / decision action -> requires human approval.
//   theseus.forceos.ai/action: "decision" | "autonomy" | "model-promote" | ...
const LBL_ACTION = "theseus.forceos.ai/action";
//   theseus.forceos.ai/human-approved-by: "<sailor-id / ticket>"  (must be non-empty)
const ANN_APPROVED_BY = "theseus.forceos.ai/human-approved-by";
//   optional corroborating annotation pointing at the sealed approval leaf.
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
    ...(s.ephemeralContainers ?? []) as unknown as V1Container[],
  ];
}

/** Effective securityContext booleans, treating pod-level as the default. */
function effective(
  pod: a.Pod,
  c: V1Container,
): { runAsNonRoot?: boolean; readOnlyRootFilesystem?: boolean; allowPrivilegeEscalation?: boolean; privileged?: boolean; dropsAll: boolean } {
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

// === RULE 1 — HUMAN-IN-COMMAND ============================================
// Any Pod that declares an autonomy/decision action must carry a non-empty
// human-approval annotation. No human, no autonomy action. Applies to bare Pods
// and to Pods created by Jobs/Deployments alike (we validate the Pod, which is
// what actually schedules). Action-labeled Pods need not be part-of=theseus —
// the *action* label is the trigger, so a stray autonomy pod can't sneak in.
When(a.Pod)
  .IsCreatedOrUpdated()
  .InNamespace(...NS_THESEUS)
  .WithLabel(LBL_ACTION)
  .Validate(req => {
    const action = (req.Raw.metadata?.labels ?? {})[LBL_ACTION] ?? "";
    const approver = (req.Raw.metadata?.annotations ?? {})[ANN_APPROVED_BY]?.trim();

    if (!approver) {
      Log.warn(
        { action, ns: req.Raw.metadata?.namespace, name: req.Raw.metadata?.name },
        "THESEUS rail 1 (human-in-command): denied autonomy/decision action without human approval",
      );
      return req.Deny(
        `THESEUS rail 1 (human-in-command): pod declares action "${action}" ` +
          `but has no human approval. Set annotation "${ANN_APPROVED_BY}" to a ` +
          `non-empty approver id (and ideally "${ANN_APPROVAL_REF}" pointing at the ` +
          `sealed approval leaf). Theseus drafts the call; a human approves it.`,
        // 403 Forbidden — the request is well-formed but disallowed by policy.
        403,
      );
    }

    const warnings: string[] = [];
    if (!(req.Raw.metadata?.annotations ?? {})[ANN_APPROVAL_REF]) {
      warnings.push(
        `THESEUS rail 1: approved by "${approver}" but no "${ANN_APPROVAL_REF}" ` +
          `linking the sealed approval record. Recommended for the audit trail.`,
      );
    }
    return req.Approve(warnings);
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
      allContainers(pod).find(c => c.securityContext?.seccompProfile?.type)
        ?.securityContext?.seccompProfile?.type;
    if (seccompType !== "RuntimeDefault" && seccompType !== "Localhost") {
      warnings.push(
        "THESEUS rail 3: seccompProfile.type is not RuntimeDefault/Localhost. " +
          "Recommended to match zarf/manifests/job.yaml.",
      );
    }

    return req.Approve(warnings);
  });

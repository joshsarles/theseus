// SPDX-License-Identifier: AGPL-3.0-only
// THESEUS — record-binding helper for the human-in-command admission rail.
// =============================================================================
// This is the engine behind rail-1's upgrade from "type any string = approved"
// to "DENIED unless it chains to a sealed decision." It is a faithful, dependency-
// free TypeScript port of referee/chain.py's leaf-hash + prev-hash chain verify,
// plus a parser/resolver for the canonical approval-record-ref.
//
// WHY THIS EXISTS (the honest binding story):
//   A Kubernetes *validating admission webhook* cannot, by itself, reach an
//   arbitrary file on the operator's laptop. So "bind the ref to a real sealed
//   leaf" is enforced in TWO honest layers, and this module powers both:
//
//   LAYER A — ADMISSION STRUCTURE (always enforced, synchronous, in theseus-
//     policies.ts): the ref MUST be present and canonically formed
//     (theseus-record://<kind>/<obs_id>@sha256:<64hex>), the action must be a
//     bound decision action, and the pod MUST carry a verify init-container wired
//     to the SAME ref against a read-only record mount. A forged/absent/malformed
//     ref, or a missing verify gate, is DENIED at admission. parseRef() is the
//     gate; it is what turns "x = approved" into a structurally-bound claim.
//
//   LAYER B — IN-PROCESS CHAIN RESOLVE (enforced when the record is reachable to
//     the controller via env THESEUS_RECORD_DIR; async): the webhook reads
//     chain.jsonl, runs the FULL prev-hash chain verification (verifyChain), and
//     confirms the ref's leaf exists with the pinned leaf_hash AND that the chain
//     verifies up to and including it (resolveRefInChain). Forged hash or absent
//     leaf -> DENIED at admission with the snap reason. This is the live flex when
//     the record volume is mounted into the Pepr controller.
//
//   LAYER C — RUNTIME VERIFY GATE (the init-container required by Layer A; lives
//     in the applied manifest, runs referee/chain.py's real verify_dir before the
//     workload starts): the in-cluster binding that holds even when the controller
//     has no record mount. Layer A guarantees it is present and correctly wired.
//
// HONEST SCOPE: tamper-EVIDENT, not tamper-proof — same as the Python chain.
//   The hash chain detects any in-place edit of a sealed leaf (the leaf_hash and
//   every subsequent prev_hash stop matching). It is NOT a signature: it does not
//   prove WHO sealed the leaf, only that the named leaf exists and the chain is
//   internally consistent. Ed25519/cosign signing of leaves is the stronger,
//   separately-tracked upgrade (referee/chain.py header + bundle.rfc3161).
// =============================================================================

import { createHash } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

/** 64 zero hex chars — the genesis prev_hash, matching referee/chain.py GENESIS. */
export const GENESIS = "0".repeat(64);

/** A single stored leaf, mirroring referee.chain.Leaf's persisted shape. */
export interface Leaf {
  idx: number;
  ts: number;
  kind: string;
  obs_id: string;
  record_b64: string;
  prev_hash: string;
  leaf_hash: string;
}

/** A parsed approval-record-ref. */
export interface ApprovalRef {
  /** leaf kind, e.g. "human_decision". */
  kind: string;
  /** leaf obs_id, e.g. "accepted:CTC-7" (may itself contain ':'). */
  obsId: string;
  /** pinned 64-hex leaf_hash the ref commits to. */
  leafHash: string;
  /** the exact string that was parsed (for echoing in messages). */
  raw: string;
}

function sha256hex(data: string): string {
  return createHash("sha256").update(Buffer.from(data, "utf8")).digest("hex");
}

/**
 * Recompute a leaf's hash exactly as referee/chain.py LocalHashChain._leaf_hash:
 *   sha256(f"{prev_hash}|{kind}|{obs_id}|{record_b64}")
 * The '|' join order and field set are load-bearing — keep in lockstep with chain.py.
 */
export function leafHash(prevHash: string, kind: string, obsId: string, recordB64: string): string {
  return sha256hex(`${prevHash}|${kind}|${obsId}|${recordB64}`);
}

const HEX64 = /^[0-9a-f]{64}$/;

/**
 * Canonical approval-record-ref:
 *   theseus-record://<kind>/<obs_id>@sha256:<64-lowercase-hex>
 * e.g. theseus-record://human_decision/accepted:CTC-7@sha256:2547e578...6628
 *
 * The ref is SELF-BINDING: it names the exact leaf (kind + obs_id) AND pins its
 * leaf_hash. That is what makes a forged "approved" string impossible to fake at
 * admission — there is nothing to type that resolves to a sealed leaf unless one
 * was actually sealed. Returns null on any malformation (caller -> Deny).
 *
 * obs_id may legitimately contain ':' (e.g. "accepted:CTC-7"), so we split on the
 * LAST '@' and the FIRST '/' after the scheme, never on ':'.
 */
export function parseRef(ref: string | undefined | null): ApprovalRef | null {
  if (!ref) return null;
  const raw = ref.trim();
  const SCHEME = "theseus-record://";
  if (!raw.startsWith(SCHEME)) return null;

  const at = raw.lastIndexOf("@sha256:");
  if (at < 0) return null;
  const leafHashPart = raw.slice(at + "@sha256:".length).toLowerCase();
  if (!HEX64.test(leafHashPart)) return null;

  const body = raw.slice(SCHEME.length, at); // "<kind>/<obs_id>"
  const slash = body.indexOf("/");
  if (slash <= 0) return null; // need a non-empty kind before the first '/'
  const kind = body.slice(0, slash);
  const obsId = body.slice(slash + 1);
  if (!kind || !obsId) return null;

  return { kind, obsId, leafHash: leafHashPart, raw };
}

/** Result of a chain-resolution attempt. */
export interface ResolveResult {
  ok: boolean;
  /** human-readable reason (PASS detail or the SNAP/absent reason). */
  message: string;
  /** the resolved leaf when ok. */
  leaf?: Leaf;
}

/**
 * Faithful port of referee/chain.py verify_dir's per-leaf check: walk the chain
 * from genesis, recomputing each leaf_hash and confirming prev_hash linkage. Stops
 * at the first SNAP. Returns ok + the verified prefix length.
 *
 * (We verify the linkage exactly; the Merkle-root/bundle cross-check in verify_dir
 *  is an additional integrity check the runtime verify-gate init-container runs in
 *  full via the real Python verify_dir. Here, linkage is the property that binds a
 *  ref's leaf_hash to a tamper-evident position in the chain.)
 */
export function verifyChain(leaves: Leaf[]): {
  ok: boolean;
  firstBad: number | null;
  message: string;
} {
  let prev = GENESIS;
  for (const row of leaves) {
    const expect = leafHash(prev, row.kind, row.obs_id, row.record_b64);
    if (row.prev_hash !== prev || row.leaf_hash !== expect) {
      return {
        ok: false,
        firstBad: row.idx,
        message: `chain SNAP at leaf ${row.idx} (${row.kind}:${row.obs_id})`,
      };
    }
    prev = row.leaf_hash;
  }
  return {
    ok: true,
    firstBad: null,
    message: `${leaves.length} leaves verify, head ${prev.slice(0, 12)}…`,
  };
}

/** Parse chain.jsonl text into Leaf rows (skips blank lines), or throw on bad JSON. */
export function parseChainJsonl(text: string): Leaf[] {
  const out: Leaf[] = [];
  for (const line of text.split("\n")) {
    const t = line.trim();
    if (!t) continue;
    out.push(JSON.parse(t) as Leaf);
  }
  return out;
}

/**
 * The binding check: does `ref` resolve to a real, sealed, chain-verifying leaf?
 *
 * 1. the chain up to the named leaf must verify (verifyChain) — no SNAP;
 * 2. a leaf must exist whose kind+obs_id match the ref;
 * 3. that leaf's actual leaf_hash must equal the ref's pinned hash (forged hash -> fail);
 * 4. that leaf's hash must be the recomputed hash (defense-in-depth vs a doctored file
 *    where someone set leaf_hash to match the ref but the contents don't hash to it).
 */
export function resolveRefInChain(ref: ApprovalRef, leaves: Leaf[]): ResolveResult {
  const chain = verifyChain(leaves);
  if (!chain.ok) {
    return {
      ok: false,
      message: `record does not verify (${chain.message}); ref cannot be trusted`,
    };
  }
  const hit = leaves.find(l => l.kind === ref.kind && l.obs_id === ref.obsId);
  if (!hit) {
    return {
      ok: false,
      message: `no sealed leaf "${ref.kind}:${ref.obsId}" in the record (forged or absent ref)`,
    };
  }
  if (hit.leaf_hash.toLowerCase() !== ref.leafHash) {
    return {
      ok: false,
      message:
        `leaf "${ref.kind}:${ref.obsId}" exists but its sealed hash ${hit.leaf_hash.slice(0, 12)}… ` +
        `does not match the ref's pinned ${ref.leafHash.slice(0, 12)}… (forged leaf_hash)`,
    };
  }
  const recomputed = leafHash(hit.prev_hash, hit.kind, hit.obs_id, hit.record_b64);
  if (recomputed !== hit.leaf_hash) {
    return {
      ok: false,
      message: `leaf "${ref.kind}:${ref.obsId}" fails recomputation (tampered contents)`,
    };
  }
  return {
    ok: true,
    message: `ref resolves to sealed, chain-verified leaf idx=${hit.idx}`,
    leaf: hit,
  };
}

/**
 * Where the controller can read the record, if it has been mounted in.
 * Set THESEUS_RECORD_DIR (in package.json `pepr.env`, or the controller Deployment)
 * to enable Layer-B in-process resolution at admission. Absent -> Layer B is
 * skipped (advisory), Layers A + C still enforce.
 */
export function controllerRecordDir(): string | null {
  const d = process.env.THESEUS_RECORD_DIR;
  return d && d.trim() ? d.trim() : null;
}

/**
 * Attempt Layer-B in-process resolution. Returns:
 *   { reachable:false } when no record is mounted to the controller (skip, advisory);
 *   { reachable:true, result } when the record was read and the ref resolved/failed.
 */
export function resolveAgainstControllerRecord(
  ref: ApprovalRef,
  recordDir?: string | null,
): { reachable: false } | { reachable: true; result: ResolveResult } {
  const dir = recordDir ?? controllerRecordDir();
  if (!dir) return { reachable: false };
  const chainPath = join(dir, "chain.jsonl");
  if (!existsSync(chainPath)) {
    return {
      reachable: true,
      result: { ok: false, message: `THESEUS_RECORD_DIR set but ${chainPath} missing` },
    };
  }
  let leaves: Leaf[];
  try {
    leaves = parseChainJsonl(readFileSync(chainPath, "utf8"));
  } catch (e) {
    return {
      reachable: true,
      result: { ok: false, message: `failed to read/parse ${chainPath}: ${String(e)}` },
    };
  }
  return { reachable: true, result: resolveRefInChain(ref, leaves) };
}

// ---------------------------------------------------------------------------
// Layer-A structural checks on the verify init-container the pod must carry.
// ---------------------------------------------------------------------------

/** Container name (init) that runs the runtime verify-gate (Layer C). */
export const VERIFY_INIT_NAME = "theseus-approval-verify";
/** Env var the verify init-container reads the ref from (so it checks the SAME ref). */
export const VERIFY_REF_ENV = "THESEUS_APPROVAL_REF";

/** Minimal shapes we read off the pod — kept structural so we don't depend on the full V1 types here. */
interface MiniEnv {
  name?: string;
  value?: string;
}
interface MiniMount {
  mountPath?: string;
  readOnly?: boolean;
}
interface MiniContainer {
  name?: string;
  env?: MiniEnv[];
  volumeMounts?: MiniMount[];
}

/**
 * Does the pod carry a correctly-wired verify init-container (Layer C apparatus)?
 *   - an initContainer named VERIFY_INIT_NAME exists;
 *   - it carries env VERIFY_REF_ENV equal to the SAME ref string (so it verifies the
 *     exact ref admission saw, not a different one);
 *   - it mounts a record at one of the known record paths READ-ONLY (rail-3 also
 *     enforces RO; here we require the mount EXISTS so there is something to verify).
 * Returns null if OK, else a human-readable reason the gate is missing/miswired.
 */
export function verifyGateProblem(
  initContainers: MiniContainer[] | undefined,
  refRaw: string,
  recordMountPaths: string[],
): string | null {
  const gate = (initContainers ?? []).find(c => c.name === VERIFY_INIT_NAME);
  if (!gate) {
    return (
      `no "${VERIFY_INIT_NAME}" init-container. A bound decision action must carry the runtime ` +
      `verify gate (it runs referee/chain.py verify_dir on the mounted record before the workload starts).`
    );
  }
  const refEnv = (gate.env ?? []).find(e => e.name === VERIFY_REF_ENV)?.value?.trim();
  if (refEnv !== refRaw) {
    return (
      `init-container "${VERIFY_INIT_NAME}" must set env ${VERIFY_REF_ENV} to the SAME approval-record-ref ` +
      `as the annotation (so it verifies the exact sealed leaf admission was shown).`
    );
  }
  const hasRecordMount = (gate.volumeMounts ?? []).some(m => {
    const mp = m.mountPath;
    return !!mp && recordMountPaths.some(p => mp === p || mp.startsWith(p + "/"));
  });
  if (!hasRecordMount) {
    return (
      `init-container "${VERIFY_INIT_NAME}" must mount the tamper-evident record (one of ` +
      `${recordMountPaths.join(", ")}) so it has something to chain-verify.`
    );
  }
  return null;
}

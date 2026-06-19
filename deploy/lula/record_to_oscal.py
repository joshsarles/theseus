#!/usr/bin/env python3
"""THESEUS — emit the tamper-evident record as NIST OSCAL assessment-results.

INTEGRATION_SPEC §4/§7 adopt #1 (Defense Unicorns Lula / NIST OSCAL): the record's
EXTERNAL accreditation artifact is OSCAL, the AO's own language. This reads the ACTUAL
sealed record (referee/chain.py output: chain.jsonl + bundle.json + attestations.jsonl,
all read-only) and projects its runtime events onto NIST SP 800-53 rev5 controls, emitting
an OSCAL **assessment-results** document (OSCAL 1.1.3, the version Lula emits).

This is the runtime-decision extension of the supply-chain story: in-toto/SLSA/cosign attest
BUILD time; THESEUS attests RUNTIME decisions onboard and reports them as OSCAL assessment
evidence an AO can ingest. It is distinct from (and complements) the static Lula
component-definition validations in lula/ — those validate the bundle ARTIFACT against OPA
rules; this projects the record's actual sealed EVENTS onto controls as observations/findings.

  python3 deploy/lula/record_to_oscal.py --record <dir> [--out <oscal.json>]
  python3 deploy/lula/record_to_oscal.py --selftest      # build a sample record, emit + self-check

Mapping (THESEUS event kind -> NIST SP 800-53 rev5 control):
  model_trained  -> CM-3  (configuration change control: every model promotion sealed + versioned)
  ais_anomaly    -> CA-7  (continuous monitoring: cold-start PoL anomaly surveillance, sealed)
  violation      -> CM-3  (config change control: authorized-parameters gate trip, policy-stamped)
  human_decision -> AC-6  (least privilege / human-in-command: a sealed human ACCEPT/OVERRIDE)
  scorecard      -> CA-7  (continuous monitoring: drift/scorecard evaluation over the live feed)
  observation    -> AU-2  (audit events: every observed vendor decision -> chained leaf)
  (every leaf)   -> AU-9  (protection of audit information: the SHA-256 chain + Ed25519 + in-toto)

Honesty (matches referee/chain.py + the repo honesty lock):
  - The hash chain is tamper-EVIDENT, not tamper-proof; stated in every AU-9 finding.
  - A finding is `satisfied` ONLY when the record cryptographically verifies (verify_dir PASS)
    AND the control's events are present + signed/attested. If verify fails, AU-9 is
    `not-satisfied` and ALL controls degrade to not-satisfied (an unverifiable record is no
    evidence). No fabricated PASS.
  - accreditation never asserted: props carry accreditation-status=EVIDENCE_LOGGED, never CERTIFIED.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from referee.chain import verify_dir  # read-only verifier, public interface  # noqa: E402

OSCAL_VERSION = "1.1.3"            # the version Lula emits (matches lula/assessment-results.yaml)
LULA_NS = "https://docs.lula.dev/oscal/ns"
THESEUS_NS = "https://forceos.ai/theseus/oscal/ns"
SP80053_REV5 = (
    "https://raw.githubusercontent.com/usnistgov/oscal-content/main/"
    "nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
)

# THESEUS record event kind -> (control-id, control title, control rationale for the finding).
KIND_TO_CONTROL = {
    "model_trained":  ("cm-3", "Configuration Change Control",
                       "Every model promotion is sealed with version + metrics + model SHA-256 "
                       "into the tamper-evident record (configuration change is recorded + provable)."),
    "violation":      ("cm-3", "Configuration Change Control",
                       "Authorized-parameters gate trips are sealed, stamped with policy_id+version "
                       "and the tripped rule (an unauthorized configuration/decision is recorded)."),
    "ais_anomaly":    ("ca-7", "Continuous Monitoring",
                       "Cold-start Pattern-of-Life anomalies are surveilled over the live feed and "
                       "each alert is sealed with a plain-language reason + recommended action."),
    "scorecard":      ("ca-7", "Continuous Monitoring",
                       "Scorecard/drift evaluation runs over the live feed; accreditation status is "
                       "logged (EVIDENCE_LOGGED), never asserted as CERTIFIED."),
    "human_decision": ("ac-6", "Least Privilege / Human-in-Command",
                       "Each human ACCEPT/OVERRIDE is sealed with operator + rationale + the decision "
                       "reference, binding authority-of-record to a human (decision-support, not autonomy)."),
    "observation":    ("au-2", "Audit Events",
                       "Every observed vendor decision is chain-appended at ingest as an audit event."),
    # Fleet-learning leaf kinds (fleet/out/fleet_record) — the provenance-gated, eval-gated
    # FedAvg merge the live poison-rejection beat (POST /api/fleet/inject) seals.
    "fleet_delta_accepted":  ("ca-7", "Continuous Monitoring",
                              "Each ship's locally-trained model delta is provenance-verified, "
                              "evaluated, and sealed on receipt — continuous monitoring of fleet-wide "
                              "model evolution under DDIL."),
    "fleet_merge_accepted":  ("cm-3", "Configuration Change Control",
                              "Every accepted FedAvg merge (a model promotion) is sealed with the "
                              "contributing ships + before/after held-out RMSE + the eval-gate verdict "
                              "— a model configuration change that is recorded and provable."),
    "fleet_merge_rejected":  ("si-7", "Software, Firmware, and Information Integrity",
                              "A model-update delta that fails the provenance gate (forged/unattested "
                              "keyid not in the trust registry, or a weight-hash mismatch) or the eval "
                              "gate (regression) is REJECTED and sealed — integrity verification detects "
                              "and refuses an unauthorized/poisoned model change before it can merge."),
}

# AU-9 is satisfied by the chain mechanism itself (covers ALL leaves), evaluated from verify_dir.
AU9 = ("au-9", "Protection of Audit Information",
       "SHA-256 prev-hash chain + Merkle root over all leaves; each leaf additionally Ed25519-signed "
       "and emitted as a DSSE-wrapped in-toto Statement v1. Tamper-EVIDENT (not tamper-proof): one "
       "flipped byte SNAPs the chain and breaks the signature + attestation at that leaf. The full "
       "re-hash + signature + attestation walk is referee/chain.py verify_dir (offline, third-party-buildable).")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _u() -> str:
    return str(_uuid.uuid4())


def _read_record(record_dir: Path) -> tuple[list[dict], dict, list[dict] | None]:
    """Read the record READ-ONLY: chain.jsonl leaves, bundle.json, attestations.jsonl (if present)."""
    chain_path = record_dir / "chain.jsonl"
    bundle_path = record_dir / "bundle.json"
    attest_path = record_dir / "attestations.jsonl"
    if not chain_path.exists() or not bundle_path.exists():
        raise FileNotFoundError(
            f"no record at {record_dir} (need chain.jsonl + bundle.json). "
            f"Seal one first (e.g. python3 demo/ais_pol.py) or use --selftest."
        )
    leaves = [json.loads(l) for l in chain_path.read_text().splitlines() if l.strip()]
    bundle = json.loads(bundle_path.read_text())
    attests = None
    if attest_path.exists():
        attests = [json.loads(l) for l in attest_path.read_text().splitlines() if l.strip()]
    return leaves, bundle, attests


def _leaf_summary(leaf: dict) -> str:
    """Human-readable one-liner for a sealed leaf, decoded from its real record payload."""
    try:
        rec = json.loads(base64.b64decode(leaf["record_b64"]))
    except Exception:
        rec = {}
    bits = []
    for k in ("name", "version", "type", "mmsi", "decision", "operator", "policy_id",
              "rule", "confidence", "accreditation_status", "model_sha256"):
        if k in rec:
            v = rec[k]
            if k == "model_sha256":
                v = str(v)[:12] + "…"
            bits.append(f"{k}={v}")
    return ", ".join(bits) if bits else leaf.get("obs_id", "")


def _observation(leaf: dict, signed: bool, attested: bool) -> dict:
    """One OSCAL observation per sealed leaf — the runtime-decision evidence item.

    methods=[TEST] (Lula's convention for an automated check); relevant-evidence carries the
    REAL leaf_hash, signature presence, and attestation binding so the observation is checkable
    against the on-disk record by anyone (offline, zero trust in us).
    """
    crypto = []
    if signed:
        crypto.append("Ed25519-signed")
    if attested:
        crypto.append("in-toto/DSSE-attested")
    crypto_s = (" · " + " + ".join(crypto)) if crypto else " · UNSIGNED (chain-hash only)"
    return {
        "uuid": _u(),
        "title": f"Sealed record event: {leaf['kind']}:{leaf['obs_id']}",
        "description": (
            f"[TEST]: leaf {leaf['idx']} ({leaf['kind']}:{leaf['obs_id']}) "
            f"sealed into the tamper-evident record{crypto_s}. {_leaf_summary(leaf)}"
        ),
        "methods": ["TEST"],
        "collected": datetime.fromtimestamp(leaf["ts"], timezone.utc).astimezone().isoformat(),
        "props": [
            {"name": "leaf-index", "ns": THESEUS_NS, "value": str(leaf["idx"])},
            {"name": "leaf-kind", "ns": THESEUS_NS, "value": leaf["kind"]},
            {"name": "leaf-hash", "ns": THESEUS_NS, "value": leaf["leaf_hash"]},
            {"name": "prev-hash", "ns": THESEUS_NS, "value": leaf["prev_hash"]},
            {"name": "ed25519-signed", "ns": THESEUS_NS, "value": "true" if signed else "false"},
            {"name": "in-toto-attested", "ns": THESEUS_NS, "value": "true" if attested else "false"},
        ],
        "relevant-evidence": [
            {"description": (
                f"leaf_hash={leaf['leaf_hash']}; prev_hash={leaf['prev_hash']}; "
                f"signature={'present' if signed else 'absent'}; "
                f"in-toto/DSSE attestation={'present' if attested else 'absent'}. "
                f"Verifiable offline via referee/chain.py verify_dir."
            )}
        ],
    }


def build_assessment_results(record_dir: Path) -> dict:
    """Project the ACTUAL sealed record onto NIST SP 800-53 rev5 as OSCAL assessment-results."""
    leaves, bundle, attests = _read_record(record_dir)
    ok, bad_idx, verify_msg = verify_dir(record_dir)   # the real offline verifier (read-only)

    signed_idx = {i for i, lf in enumerate(leaves) if lf.get("sig")}
    n_attest = len(attests) if attests is not None else 0
    # attestations.jsonl is 1:1-ordered with leaves (referee/chain.py guarantees this when present)
    attested_idx = set(range(min(n_attest, len(leaves)))) if attests is not None else set()

    # group leaves by their mapped control; build one observation per leaf
    obs_by_control: dict[str, list[dict]] = defaultdict(list)
    leaf_count_by_control: dict[str, int] = defaultdict(int)
    all_observations: list[dict] = []
    for i, leaf in enumerate(leaves):
        kind = leaf["kind"]
        ctrl = KIND_TO_CONTROL.get(kind, ("au-2", "Audit Events",
                                          "Sealed audit event (default mapping)."))[0]
        ob = _observation(leaf, i in signed_idx, i in attested_idx)
        all_observations.append(ob)
        obs_by_control[ctrl].append(ob)
        leaf_count_by_control[ctrl] += 1

    # every leaf is also evidence for AU-9 (the chain mechanism protects them all)
    fully_crypto = bool(leaves) and len(signed_idx) == len(leaves) and len(attested_idx) == len(leaves)

    findings: list[dict] = []
    controls_seen: set[str] = set()

    def _status(satisfied: bool, reason: str, remark: str | None = None) -> dict:
        st = {"reason": reason, "state": "satisfied" if satisfied else "not-satisfied"}
        if remark:
            st["remarks"] = remark
        return st

    # --- AU-9 finding (the chain mechanism; gates everything) ---
    controls_seen.add(AU9[0])
    au9_remark = (
        f"verify_dir: {verify_msg}. "
        f"merkle_root={bundle.get('merkle_root', '')[:16]}…, chain_head={bundle.get('chain_head', '')[:16]}…, "
        f"leaf_count={bundle.get('leaf_count')}, signed={len(signed_idx)}/{len(leaves)}, "
        f"in-toto-attested={len(attested_idx)}/{len(leaves)}. Tamper-EVIDENT, not tamper-proof."
    )
    findings.append({
        "uuid": _u(),
        "title": f"Record integrity — Control: {AU9[0].upper()} ({AU9[1]})",
        "description": AU9[2],
        "related-observations": [{"observation-uuid": ob["uuid"]} for ob in all_observations],
        "target": {
            "type": "objective-id",
            "target-id": AU9[0],
            "status": _status(
                ok,
                "pass" if ok else "fail",
                au9_remark if ok else f"RECORD DID NOT VERIFY at leaf {bad_idx}: {verify_msg}",
            ),
        },
    })

    # --- per-control findings from the actual sealed events ---
    # A control is satisfied iff (the record verifies) AND (it has >=1 sealed, signed+attested event).
    for ctrl in sorted(obs_by_control):
        if ctrl == AU9[0]:
            continue
        controls_seen.add(ctrl)
        # title/rationale from the first kind that mapped here
        title = next(
            (v[1] for v in KIND_TO_CONTROL.values() if v[0] == ctrl), "Mapped Control"
        )
        rationale = next(
            (v[2] for v in KIND_TO_CONTROL.values() if v[0] == ctrl), "Sealed events mapped to this control."
        )
        ctrl_obs = obs_by_control[ctrl]
        ctrl_idxs = [ob["props"][0]["value"] for ob in ctrl_obs]  # leaf indices as strings
        idx_set = {int(x) for x in ctrl_idxs}
        ctrl_signed = idx_set <= signed_idx
        ctrl_attested = idx_set <= attested_idx
        satisfied = ok and bool(ctrl_obs) and ctrl_signed and ctrl_attested
        remark = (
            f"{len(ctrl_obs)} sealed event(s) mapped to {ctrl.upper()} "
            f"(signed={'all' if ctrl_signed else 'partial'}, "
            f"attested={'all' if ctrl_attested else 'partial'}); "
            f"record verify {'PASS' if ok else 'FAIL'}."
        )
        findings.append({
            "uuid": _u(),
            "title": f"Runtime evidence — Control: {ctrl.upper()} ({title})",
            "description": rationale,
            "related-observations": [{"observation-uuid": ob["uuid"]} for ob in ctrl_obs],
            "target": {
                "type": "objective-id",
                "target-id": ctrl,
                "status": _status(satisfied, "pass" if satisfied else "fail", remark),
            },
        })

    findings.sort(key=lambda f: f["target"]["target-id"])
    include_controls = [{"control-id": c} for c in sorted(controls_seen)]

    result = {
        "uuid": _u(),
        "title": "THESEUS Runtime Decision Record — OSCAL Assessment Results",
        "description": (
            "Assessment results projected from the THESEUS tamper-evident record (referee/chain.py). "
            "Each sealed leaf (model promotion, AIS Pattern-of-Life anomaly, policy violation, human "
            "ACCEPT/OVERRIDE, scorecard) is an OSCAL observation; per-control findings aggregate them "
            "onto NIST SP 800-53 rev5. The runtime-decision extension of in-toto/SLSA/OSCAL "
            "(INTEGRATION_SPEC §3.2): supply-chain attestations cover build time; this covers runtime "
            "decisions onboard. Read-only over the record; never asserts accreditation."
        ),
        "start": _now_iso(),
        "end": _now_iso(),
        "props": [
            {"name": "target", "ns": LULA_NS, "value": SP80053_REV5},
            {"name": "record-verified", "ns": THESEUS_NS, "value": "true" if ok else "false"},
            {"name": "record-verify-message", "ns": THESEUS_NS, "value": verify_msg},
            {"name": "merkle-root", "ns": THESEUS_NS, "value": bundle.get("merkle_root", "")},
            {"name": "chain-head", "ns": THESEUS_NS, "value": bundle.get("chain_head", "")},
            {"name": "leaf-count", "ns": THESEUS_NS, "value": str(bundle.get("leaf_count", len(leaves)))},
            {"name": "ed25519-signed-leaves", "ns": THESEUS_NS, "value": f"{len(signed_idx)}/{len(leaves)}"},
            {"name": "in-toto-attested-leaves", "ns": THESEUS_NS, "value": f"{len(attested_idx)}/{len(leaves)}"},
            # honesty lock — accreditation is never asserted from a record alone
            {"name": "accreditation-status", "ns": THESEUS_NS, "value": "EVIDENCE_LOGGED"},
            {"name": "tamper-evident-not-tamper-proof", "ns": THESEUS_NS, "value": "true"},
        ],
        "reviewed-controls": {
            "description": "NIST SP 800-53 rev5 controls evidenced by sealed THESEUS runtime events.",
            "control-selections": [
                {
                    "description": "Controls evidenced by the tamper-evident record",
                    "include-controls": include_controls,
                }
            ],
            "remarks": "A control is satisfied only when the record cryptographically verifies "
                       "AND its mapped events are sealed, signed, and in-toto attested.",
        },
        "observations": all_observations,
        "findings": findings,
    }

    return {
        "assessment-results": {
            "uuid": _u(),
            "metadata": {
                "title": "THESEUS — Tamper-Evident Record Security Assessment Results (SAR)",
                "last-modified": _now_iso(),
                "version": "0.1.0",
                "oscal-version": OSCAL_VERSION,
                "published": _now_iso(),
                "remarks": (
                    "Generated by deploy/lula/record_to_oscal.py from the THESEUS tamper-evident "
                    "record. Runtime-decision OSCAL evidence (INTEGRATION_SPEC §4/§7 adopt #1). "
                    "Read-only over the record; tamper-EVIDENT not tamper-proof; never CERTIFIED."
                ),
                "props": [
                    {"name": "generator", "ns": THESEUS_NS, "value": "theseus/record_to_oscal.py"},
                ],
            },
            # OSCAL requires import-ap (a uri-reference). The record IS the evidence source; we point
            # at the offline verifier as the assessment procedure, with an honest remark.
            "import-ap": {
                "href": "referee/chain.py#verify_dir",
                "remarks": "No separate OSCAL assessment-plan; the assessment procedure is the "
                           "offline record verifier (referee/chain.py verify_dir).",
            },
            "results": [result],
        }
    }


def emit(record_dir: Path, out_path: Path | None) -> dict:
    doc = build_assessment_results(record_dir)
    text = json.dumps(doc, indent=2) + "\n"
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
    return doc


def _selftest() -> int:
    """Build a sample record in an isolated tmp dir, emit OSCAL, and self-check structure."""
    import tempfile
    sys.path.insert(0, str(ROOT / "demo"))
    from _record import seal, verify  # noqa: E402

    tmp = Path(tempfile.mkdtemp(prefix="theseus-oscal-selftest-"))
    rec = tmp / "record"
    seal(rec, "model_trained", "theseus-ae:v1",
         {"name": "theseus-ae", "version": 1, "framework": "pytorch",
          "roc_auc": 0.93, "model_sha256": "ab" * 32})
    seal(rec, "ais_anomaly", "loiter:367767310",
         {"mmsi": "367767310", "type": "loiter", "confidence": 0.7,
          "why": "transited then loitered", "recommended_action": "verify intent"})
    seal(rec, "violation", "policy:authorized-parameters",
         {"policy_id": "authorized-parameters", "version": "1.2.0", "rule": "max_autonomy_action"})
    seal(rec, "human_decision", "accepted:CTC-7",
         {"decision": "ACCEPT", "operator": "watch-officer", "obs_ref": "loiter:367767310"})
    seal(rec, "scorecard", "session:drift-eval",
         {"accreditation_status": "EVIDENCE_LOGGED", "drift": "nominal"})
    vok, _, _ = verify(rec)
    assert vok, "sample record did not verify"

    doc = build_assessment_results(rec)
    ar = doc["assessment-results"]
    assert ar["metadata"]["oscal-version"] == OSCAL_VERSION
    assert ar["import-ap"]["href"]
    res = ar["results"][0]
    assert res["uuid"] and res["title"] and res["description"] and res["start"]
    assert len(res["observations"]) == 5, res["observations"]
    # AU-9 + the four mapped controls (cm-3, ca-7, ac-6) -> at least 4 findings
    ctrls = {f["target"]["target-id"] for f in res["findings"]}
    assert {"au-9", "cm-3", "ca-7", "ac-6"} <= ctrls, ctrls
    # a verifying record with full crypto -> all satisfied
    states = {f["target"]["target-id"]: f["target"]["status"]["state"] for f in res["findings"]}
    assert all(s == "satisfied" for s in states.values()), states
    print("selftest OK — controls:", sorted(ctrls), "| all findings satisfied")

    # negative path: tamper the record -> AU-9 (and all) must flip to not-satisfied
    from referee.chain import tamper  # noqa: E402
    tamper(rec, 0)
    doc2 = build_assessment_results(rec)
    states2 = {f["target"]["target-id"]: f["target"]["status"]["state"]
               for f in doc2["assessment-results"]["results"][0]["findings"]}
    assert states2["au-9"] == "not-satisfied", states2
    assert all(s == "not-satisfied" for s in states2.values()), states2
    print("selftest OK — tampered record correctly degrades ALL findings to not-satisfied:", states2)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit the THESEUS record as OSCAL assessment-results.")
    ap.add_argument("--record", help="record dir (chain.jsonl + bundle.json), READ-ONLY")
    ap.add_argument("--out", help="write OSCAL JSON here (else stdout)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if not a.record:
        print("need --record <dir> (or --selftest)")
        return 2
    doc = emit(Path(a.record), Path(a.out) if a.out else None)
    if not a.out:
        print(json.dumps(doc, indent=2))
    else:
        ar = doc["assessment-results"]["results"][0]
        print(f"wrote {a.out}  ({len(ar['observations'])} observations, {len(ar['findings'])} findings)")
        print(f"  validate: lula tools lint -f {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

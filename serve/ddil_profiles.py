"""DDIL fault-injection profiles + a reproducible test harness for THESEUS.

DDIL = Denied / Degraded / Intermittent / Limited-bandwidth — the comms reality a UUV
fleet operates under. Most "DDIL demos" are a manual cord-pull; this is *reproducible,
seed-fixed* fault injection so the edge model-delivery path can be tested under realistic
degradation and the resilience asserted (clean-room reference implementation — no external
T&E dependency; concept-aligned with CRUCIBLE's DDIL simulator).

The harness drives the same resilience contract the live serve path enforces:
  • a corrupted delivery (bit flip on a lossy link) must FAIL the sha-256 integrity gate
    and the node must keep serving last-good;
  • a denied/dropped link delivers nothing and the node keeps serving last-good;
  • a clean (nominal / high-latency) link delivers and the new model is adopted.

    python3 serve/ddil_profiles.py            # run the self-test across all profiles
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    latency_ms: float       # base one-way latency
    jitter_ms: float        # +/- random jitter
    loss_pct: float         # probability a delivered payload is corrupted (bit flip)
    drop_pct: float         # probability the link drops the transfer entirely
    bandwidth_kbps: float   # 0 = unmetered

# Mission-relevant DDIL profiles (UUV comms reality). Ordered nominal → fully denied.
PROFILES = [
    Profile("NOMINAL",             5,    2,    0.00, 0.00, 0),       # shore / surfaced, good link
    Profile("SATCOM",              600,  200,  0.01, 0.02, 256),     # over-the-horizon satellite
    Profile("ACOUSTIC_UUV",        2000, 1500, 0.05, 0.10, 9.6),     # underwater acoustic modem (the hard one)
    Profile("MESH_DEGRADED",       150,  100,  0.08, 0.05, 1024),    # contested mesh
    Profile("BANDWIDTH_THROTTLED", 300,  50,   0.01, 0.01, 2.4),     # near-floor bandwidth
    Profile("INTERMITTENT",        250,  300,  0.03, 0.40, 512),     # link flapping
    Profile("DENIED",              0,    0,    0.00, 1.00, 0),       # fully cut (submerged, contested)
]


class LinkDropped(Exception):
    """The degraded link dropped the transfer entirely (no bytes arrive)."""


class Link:
    """A seed-fixed degraded link. transfer() returns the (possibly corrupted) payload and
    the modeled delay, or raises LinkDropped. Deterministic for a given (profile, seed)."""

    def __init__(self, profile: Profile, seed: int = 42):
        self.p = profile
        self.rng = random.Random(seed)

    def transfer(self, payload: bytes) -> tuple[bytes, float]:
        if self.rng.random() < self.p.drop_pct:
            raise LinkDropped(f"{self.p.name}: link dropped the transfer")
        delay = (self.p.latency_ms + self.rng.uniform(-self.p.jitter_ms, self.p.jitter_ms)) / 1000.0
        if self.p.bandwidth_kbps:
            delay += (len(payload) * 8) / (self.p.bandwidth_kbps * 1000.0)
        out = bytearray(payload)
        if out and self.rng.random() < self.p.loss_pct:           # corruption: flip one byte
            i = self.rng.randrange(len(out)); out[i] ^= 0x01
        return bytes(out), max(0.0, delay)


def deliver_with_integrity_gate(link: Link, model_bytes: bytes, expected_sha: str,
                                last_good: bytes) -> tuple[bytes, str]:
    """Model the edge delivery contract: pull the model over `link`, verify sha-256, adopt on
    match, else keep last-good. Returns (served_model, outcome). Never serves a corrupt model."""
    try:
        received, _delay = link.transfer(model_bytes)
    except LinkDropped:
        return last_good, "denied → serving last-good"
    if hashlib.sha256(received).hexdigest() == expected_sha:
        return received, "delivered → adopted new model"
    return last_good, "integrity FAIL (corruption) → serving last-good"


def selftest(n: int = 50) -> int:
    new_model = b"theseus-uuv-model-v2:" + b"\x01\x02\x03" * 64
    expected = hashlib.sha256(new_model).hexdigest()
    last_good = b"theseus-uuv-model-v1:last-good"
    ok = True
    print(f"DDIL fault-injection self-test ({n} model-delivery attempts/profile, seed-fixed, reproducible):")
    for p in PROFILES:
        link = Link(p)
        adopted = denied = integrity_rejected = unsafe = 0
        for _ in range(n):
            served, outcome = deliver_with_integrity_gate(link, new_model, expected, last_good)
            if "adopted" in outcome: adopted += 1
            elif "denied" in outcome: denied += 1
            else: integrity_rejected += 1
            # Resilience invariant: NEVER serve a corrupt model — only the verified new model
            # or the known-good last-good is ever served.
            if served not in (new_model, last_good): unsafe += 1
        ok = ok and unsafe == 0
        flag = "✓" if unsafe == 0 else "✗ UNSAFE"
        print(f"  {flag}  {p.name:<20} {adopted:>2} adopted · {integrity_rejected:>2} integrity-rejected · "
              f"{denied:>2} denied  →  last-good held {n - unsafe}/{n}")
    print(f"\n{'PASS' if ok else 'FAIL'} — across {len(PROFILES)} DDIL profiles, a corrupt or dropped "
          f"delivery NEVER replaced the served model (integrity gate + last-good held every time).")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selftest())

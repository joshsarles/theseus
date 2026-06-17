# smoke_25 — expected outcomes (the Day 1 acceptance gate)

Deterministic (seeded). `make smoke` asserts these; if any differ, the spine is broken — fix before anything else.

| Metric | Expected |
|---|---|
| observations ingested | 25 (17 clean + 1 stale-clean + 4 peril + 3 malformed) |
| chain leaves | 33 (25 observation + 8 violation leaves — every violation is chained too) |
| BREACH violations | 4 — `confidence_floor` (v3 @0.55) · `geofence` (walk-out during satcom_denied) · `forbidden_class_adjacency` (school in CE) · `provenance_missing` |
| WARN violations | 4 — 1 `stale_decision` + 3 `malformed` (garbage is observed and chained) |
| gate HALTs | 7 observations (4 peril + 3 malformed) |
| `make verify` | PASS (chain + merkle root + head all recompute) |
| `make tamper` then verify | **chain SNAP at leaf 9**, exit 2 |

Note: the strategy spec's `confidence_integrity` composite (drift fingerprint + ECE mismatch on confident-and-WRONG output) is the event-side beat via the CRUCIBLE wheels; the scaffold's local rule is the simpler `confidence_floor`. Both demo the same gate mechanics.

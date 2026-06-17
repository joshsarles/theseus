# THESEUS — Compliance & Impact-Level Roadmap
*Warhacker is UNCLASSIFIED. This is the forward story: how the same build climbs to IL5 → IL6 / Secret without a rebuild.*

## Now — UNCLASS (Warhacker)
- SWAN-side, unclassified data only. No combat-system data (air-gapped/classified — out of scope by design).
- Real/representative data, stated as such. The tamper-evident record is live from day one.

## Why we're already on the IL path (not bolted on later)
We picked the accreditation-easy lane on purpose, and the architecture is the compliance argument:
- **Tamper-evident, replayable record** = the AU-family audit evidence + the answer to "show what the AI did and why" — generated *as it runs*, not reconstructed.
- **Human-in-command, decision-support only** = no autonomous-control safety case to clear.
- **Airgap-native deploy (UDS/Zarf)** = disconnected-by-design, the posture IL6/classified networks require.
- `lula/` compliance-as-code already maps NIST 800-53 controls (AU-9 proof-bundle, CM-3 versioned-policy); extend the OSCAL as controls are added.

## The climb (inherit, don't rebuild)
| Level | What it takes | Our lever |
|---|---|---|
| **IL4/IL5** | 800-53 moderate/high technical controls, SBOM, continuous monitoring | **Ride UDS Core** — ships most 800-53 technical controls + auto SBOM/compliance artifacts (`docs/integration/DEFENSE_UNICORNS.md`). |
| **IL5 → IL6 / Secret** | Deploy into a pre-authorized classified environment; inherit its ATO | **UDS ATO-inheritance** (UDS Army model: ~18mo→2wk). The DU+Leidos shipboard-delivery OTA (NIWC Atlantic RCC) is the on-ramp. |
| **Embedded / combat-side** | NAVSEA cert + Wallops testing + a program sponsor | Long pole; needs a **program-office sponsor** + prime teaming. Not a hackathon goal — name it as the Phase III path. |

## Build-now choices that keep IL6 cheap later
- **Podman (rootless/daemonless)** + digest-pinned images + cosign signing → the supply-chain posture classified accreditation expects.
- **Pepr policy module** that *cluster-enforces* human-in-command + no-egress + append-only record → machine-enforced controls = the strongest safety-case artifact.
- **Everything seals into the record** → the body-of-evidence writes itself; at IL6 you hand over a verifiable, replayable trail, not a slideware audit.
- Keep crown-jewel IP as private deps/wheels (never in this repo) → clean public surface, no IP entanglement at accreditation.

## Honest caveat
There is no public turnkey IL5/IL6 stamp for UDS Core itself — the pitch is **control inheritance + 800-53 coverage + auto-generated artifacts**, plus a sponsor who owns the boundary. Verify the current IL status with Defense Unicorns directly.

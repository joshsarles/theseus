# APPRENTICE — Team One-Pager (print this)

**The problem.** An imagery analyst decides what matters in a firehose of sensor feeds, and there is now far more footage than analysts to watch it. The AI finds things; the human who reviews, connects, and decides is the bottleneck, and you cannot hire past it. The one thing that would fix it is the one thing nobody has time for: teaching the AI how the best analysts actually work.

**What we build (the demo, 5 beats):** SCREEN (a fleet screens a synthetic imagery stream full-auto) → CORRELATE (scattered detections fuse into one living target picture over time and sensors; co-movers cluster into a formation) → DRAFT + HUMAN IN COMMAND (the fleet drafts a nomination; the human accepts or overrides; it never decides) → RACE/LEARN (models race and the apprentice gets sharper at the operator's job run over run) → FIELD IT + PROVE (deploy to airgap from one bundle; NIST 800-53 evidence via Lula; every call sealed in a tamper-evident record — VERIFY green, flip one byte, chain SNAPS, restore, re-verify).

**What is real vs scripted (we say it out loud):** REAL and runnable today — the correlation engine (`make ped`), the apprentice capture + handback + record (`make apprentice`), the deploy/compliance spine (`make deploy-local`, Lula AU-9 + CM-3), the tamper-evident chain. SCRIPTED on synthetic data — the live model-race and the run-over-run learning beats (real engine substrate underneath; say so if asked). Sample/synthetic, unclassified imagery only, stated every time.

**Why we win the rubric:** Mission Impact = the analyst-bottleneck the customer named. Portability + Mission Readiness = the airgap bundle + compliance evidence (about half the score is the deploy story, already built). Resourceful = a real engine wrapped in stdlib glue, with operators on the team.

**Slots (roles not names):** LEAD architecture/demo/story · PKG zarf/uds/lula deploy + evidence · BE detection adapter + PED preset + correlation wiring · COT TAK/Cursor-on-Target emit/listen · FE the watch console (target picture + nomination card + learning curve) · OPS operator realism (scenario/fixtures, recruiting, the 60s recording).

**Day plan:** Day 0 recruit + `make onboard` green on every laptop · Day 1 detection adapter + PED preset + console shell + first airgap deploy · Day 2 full loop end-to-end + the deploy story locked under 90s + clean recording · Day 3 freeze 1000, dry-run the outbrief twice, deliver.

**Ground rules:** synthetic/unclassified only · model-agnostic, no Anthropic/Claude dependency · integrate with what the mission runs, never replace · human always in command · tamper-evident not tamper-proof · no real-vendor performance claims · banned words (safety, guardrails, responsible AI) · IP guard runs on every commit (never `--no-verify`) · roles not names in anything left behind.

**Quickstart (zero deps, Py 3.10+):** `make onboard` (gets your laptop green) then `make ped` · `make apprentice` · `make demo`. Deploy rehearsal: `make deploy-local` (isolated k3d cluster) → `make deploy-teardown`.

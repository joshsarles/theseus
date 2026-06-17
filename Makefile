PY ?= python3

.PHONY: fixtures smoke guardian apprentice ped verify tamper demo hooks onboard deploy-local deploy-teardown clean

K3D_CLUSTER ?= referee-demo

onboard:
	@sh scripts/onboard.sh

# Full airgap rehearsal in an ISOLATED k3d cluster (PKG slot; the half-the-rubric deploy beat).
# Creates a dedicated cluster so it never touches other local clusters. Tear down with deploy-teardown.
ZARF_VER := $(shell zarf version 2>/dev/null)
ZARF_ARCH := $(shell uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
ZARF_INIT := zarf-init-$(ZARF_ARCH)-$(ZARF_VER).tar.zst

deploy-local:
	@command -v k3d zarf >/dev/null 2>&1 || { echo "need k3d + zarf on PATH"; exit 1; }
	k3d cluster create $(K3D_CLUSTER) --wait
	@# zarf init auto-discovers the init package from the CWD; fetch it once if missing.
	@test -f $(ZARF_INIT) || curl -fsSL -o $(ZARF_INIT) \
	  https://github.com/zarf-dev/zarf/releases/download/$(ZARF_VER)/$(ZARF_INIT)
	zarf init --confirm
	zarf package deploy $(firstword $(wildcard zarf/dist/zarf-package-referee-*.tar.zst)) --confirm
	zarf tools kubectl -n referee wait --for=condition=complete job/referee-smoke --timeout=180s
	zarf tools kubectl -n referee logs job/referee-smoke --tail=60
	@echo "=== in-cluster smoke complete; running lula compliance evidence ==="
	$(MAKE) smoke >/dev/null 2>&1 || true
	lula validate -f lula/component-definition.yaml --confirm-execution || true

deploy-teardown:
	-k3d cluster delete $(K3D_CLUSTER)

fixtures:
	$(PY) fixtures/gen_smoke.py

detections:
	$(PY) fixtures/gen_detections.py

ped: detections
	$(PY) -m referee.ped_demo

smoke: fixtures
	$(PY) -m referee.demo --smoke

guardian:
	$(PY) -m referee.guardian_demo

apprentice:
	$(PY) -m referee.apprentice_demo

ped-detections: detections
console: ped-detections
	$(PY) -m referee.console

verify:
	$(PY) -m referee.demo --verify

tamper:
	$(PY) -m referee.demo --tamper 9
	-$(PY) -m referee.demo --verify
	@echo "(expected: chain SNAP at leaf 9 — re-run 'make smoke' to regenerate a clean record)"

demo: smoke verify

hooks:
	@TOP="$$(git rev-parse --show-toplevel 2>/dev/null)"; \
	if [ "$$TOP" != "$$(pwd)" ]; then \
	  echo "SKIP: this repo is nested inside another git repo ($$TOP)."; \
	  echo "      Installing here would overwrite the PARENT repo's hooks."; \
	  echo "      The IP-guard hook installs automatically in a STANDALONE clone (the event setup)."; \
	  exit 0; \
	fi; \
	HOOKS="$$(git rev-parse --git-path hooks)"; mkdir -p "$$HOOKS"; \
	printf '#!/bin/sh\n$(PY) scripts/ip_guard.py || exit 1\n' > "$$HOOKS/pre-commit"; \
	chmod +x "$$HOOKS/pre-commit"; \
	echo "pre-commit IP guard installed at $$HOOKS/pre-commit"

clean:
	rm -rf out out_guardian fixtures/smoke_25.jsonl

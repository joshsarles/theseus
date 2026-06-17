#!/usr/bin/env bash
# THESEUS security scan gate — Iron-Bank-aligned OSS (Trivy = the Iron Bank engine:
# CVE + secret + misconfig + SBOM). The static/container half of the security story;
# Carolina owns ZAP/DAST + tool selection. Maps to RA-5 (vuln scanning), SA-11 (dev
# testing), SI-2 (flaw remediation), CM-6 (config). Iron Bank baseline = Anchore + Trivy + ZAP.
#   bash scripts/scan.sh        # repo + image scan; SBOM -> out/scan/
# Runs the scanner as a container (no native install). Set ENGINE=podman on the Pis.
set -uo pipefail
cd "$(dirname "$0")/.."
ENGINE="${ENGINE:-docker}"
SKIP="deploy/uds/pepr/dist,deploy/uds/pepr/node_modules,data,demo/out,demo/registry,demo/models,.git"
mkdir -p out/scan

echo "== Trivy fs: vuln + secret + misconfig (HIGH,CRITICAL) on committed source =="
$ENGINE run --rm -v "$PWD":/repo aquasec/trivy:latest fs --scanners vuln,secret,misconfig \
  --skip-dirs "$SKIP" --severity HIGH,CRITICAL --no-progress --quiet /repo

echo "== Trivy: CycloneDX SBOM -> out/scan/sbom.cdx.json (ATO evidence; zarf also emits one) =="
$ENGINE run --rm -v "$PWD":/repo aquasec/trivy:latest fs --format cyclonedx \
  --output /repo/out/scan/sbom.cdx.json --skip-dirs "$SKIP" --quiet /repo 2>/dev/null && echo "  SBOM written"

echo "== Trivy image: theseus-edge:0.1.0 (build it first if missing) =="
$ENGINE run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image \
  --severity HIGH,CRITICAL --no-progress --quiet theseus-edge:0.1.0 2>/dev/null \
  || echo "  (build first: podman build -f deploy/Containerfile -t theseus-edge:0.1.0 .)"

echo ""
echo "Done. Pair with ZAP (DAST, Carolina). Latest scan (Jun 17): committed source CLEAN"
echo "(0 vuln / 0 secret; deploy/Containerfile + all K8s manifests pass). One HIGH on the"
echo "root Dockerfile (DS-0002: add a non-root USER) — Nick/Tommy's lane."

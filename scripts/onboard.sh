#!/bin/sh
# onboard.sh — get a new teammate's laptop green for the Warhacker build.
# Self-service: a recruit runs `make onboard`, reads the PASS/FAIL list, and is ready.
# No babysitting required. Exits non-zero if any required check fails.
#
# Checks (required): python >= 3.10, in a git repo, IP-guard hook installed,
#   fixtures+smoke green, apprentice demo green, IP guard actually blocks a bad commit.
# Checks (advisory): defusedxml is an EVENT-LAPTOP-ONLY install (never vendored here).

set -u
PY="${PY:-python3}"
fail=0
pass=0
note=0

ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=$((fail+1)); }
info() { printf '  \033[33mNOTE\033[0m  %s\n' "$1"; note=$((note+1)); }

cd "$(dirname "$0")/.." || { echo "cannot cd to repo root"; exit 1; }

printf '\n=== WARHACKER ONBOARD CHECK ===\n\n'

# 1. Python >= 3.10
if ver=$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null); then
  if "$PY" -c 'import sys;raise SystemExit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
    ok "python $ver (>= 3.10)"
  else
    bad "python $ver is < 3.10 — install 3.10+ (the repo is stdlib-only, no pip needed)"
  fi
else
  bad "no working '$PY' on PATH"
fi

# 2. In a git repo (the IP guard and branch-per-task workflow need it)
if git rev-parse --git-dir >/dev/null 2>&1; then
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
  ok "git repo present (branch: ${branch:-unknown})"
else
  bad "not a git repo — clone the event repo, don't copy the files"
fi

# 3. IP-guard pre-commit hook installed (the crown-jewel firewall)
# Only meaningful in a STANDALONE clone (the event setup). If this repo is nested
# inside a parent git repo (dev checkout), installing would clobber the parent's
# hooks, so we skip with a NOTE instead of failing.
TOP="$(git rev-parse --show-toplevel 2>/dev/null)"
HOOK="$(git rev-parse --git-path hooks 2>/dev/null)/pre-commit"
if [ "$TOP" != "$(pwd)" ]; then
  info "nested dev checkout (git root is $TOP) — IP-guard hook installs in a standalone clone; skipping to protect the parent repo's hooks"
elif [ -x "$HOOK" ] && grep -q ip_guard "$HOOK" 2>/dev/null; then
  ok "IP-guard pre-commit hook installed ($HOOK)"
else
  info "IP-guard hook not installed yet — installing now via 'make hooks'"
  if make hooks >/dev/null 2>&1 && [ -x "$HOOK" ] && grep -q ip_guard "$HOOK" 2>/dev/null; then
    ok "IP-guard pre-commit hook installed (auto)"
  else
    bad "could not install IP-guard hook — run 'make hooks' and re-check"
  fi
fi

# 4. fixtures + smoke green (the deploy/record spine)
if make smoke >/dev/null 2>&1; then
  ok "make smoke green (ingest -> policy gate -> hash chain -> proof)"
else
  bad "make smoke FAILED — run 'make smoke' and read the error"
fi

# 5. apprentice demo green (the headline build)
if make apprentice >/dev/null 2>&1; then
  ok "make apprentice green (learn-the-operator story runs end to end)"
else
  bad "make apprentice FAILED — run 'make apprentice' and read the error"
fi

# 6. IP guard actually blocks a forbidden commit (prove the firewall, then clean up)
guard_tmp="referee/__onboard_guard_probe.py"
printf 'import force_core  # forbidden retained-IP import\n' > "$guard_tmp"
git add "$guard_tmp" >/dev/null 2>&1
if "$PY" scripts/ip_guard.py >/dev/null 2>&1; then
  bad "IP guard did NOT block a forbidden import — firewall is not protecting us"
else
  ok "IP guard blocks forbidden retained-IP imports (firewall live)"
fi
git rm --cached "$guard_tmp" >/dev/null 2>&1
rm -f "$guard_tmp"

# 7. defusedxml — advisory only (event-laptop install, never in this repo)
if "$PY" -c 'import defusedxml' 2>/dev/null; then
  info "defusedxml present on this laptop (fine — event-laptop install, never vendored in the repo)"
else
  info "defusedxml not installed — only the EVENT LAPTOP needs it (pip install on the laptop; never add it to the repo)"
fi

printf '\n=== RESULT: %d pass, %d fail, %d note ===\n' "$pass" "$fail" "$note"
if [ "$fail" -eq 0 ]; then
  printf '\033[32mLAPTOP IS GREEN.\033[0m Next: read CONTRIBUTING.md, then your slot brief in the team-activation page.\n\n'
  exit 0
else
  printf '\033[31m%d CHECK(S) FAILED.\033[0m Fix the FAILs above, then re-run: make onboard\n\n' "$fail"
  exit 1
fi

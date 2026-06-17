#!/usr/bin/env bash
# Fetch a Qwen2.5 GGUF for the edge LLM server (deploy/child-node-compose/llm-serv.yml).
# GGUFs are gitignored (1-2GB each) — run this once per node before `compose up`.
#
#   scripts/fetch_llm_model.sh            # default: Qwen2.5-3B Q4_K_M (the agent model)
#   scripts/fetch_llm_model.sh 1.5b       # the faster chat-only fallback
#   MODELS_DIR=/home/pi1/models scripts/fetch_llm_model.sh 3b
set -euo pipefail

SIZE="${1:-3b}"
MODELS_DIR="${MODELS_DIR:-$(cd "$(dirname "$0")/.." && pwd)/models}"

case "$SIZE" in
  1.5b|1.5B) FILE="qwen2.5-1.5b-instruct-q4_k_m.gguf"; REPO="Qwen/Qwen2.5-1.5B-Instruct-GGUF" ;;
  3b|3B)     FILE="qwen2.5-3b-instruct-q4_k_m.gguf";   REPO="Qwen/Qwen2.5-3B-Instruct-GGUF" ;;
  *) echo "usage: $0 [1.5b|3b]" >&2; exit 2 ;;
esac

URL="https://huggingface.co/${REPO}/resolve/main/${FILE}?download=true"
mkdir -p "$MODELS_DIR"
DEST="$MODELS_DIR/$FILE"

if [ -s "$DEST" ]; then
  echo "already present: $DEST ($(du -h "$DEST" | cut -f1))"
  exit 0
fi

echo "fetching $FILE -> $DEST"
# resumable; works with wget or curl
if command -v wget >/dev/null 2>&1; then
  wget -c -O "$DEST" "$URL"
else
  curl -fL -C - -o "$DEST" "$URL"
fi

# sanity: GGUF magic
if [ "$(head -c4 "$DEST")" != "GGUF" ]; then
  echo "ERROR: $DEST is not a valid GGUF (download may have failed)" >&2
  exit 1
fi
echo "OK: $DEST ($(du -h "$DEST" | cut -f1))"

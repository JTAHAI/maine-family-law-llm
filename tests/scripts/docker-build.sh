#!/usr/bin/env sh
set -eu
IMAGE_TAG="${1:-maine-family-law-llm:local}"
REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$REPO_ROOT"
docker build --pull -t "$IMAGE_TAG" -f Dockerfile .

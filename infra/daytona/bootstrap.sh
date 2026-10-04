#!/usr/bin/env bash
# For a bare public-image worker when custom snapshot creation is unavailable.
# Contains no credentials; run as a Daytona asynchronous process session.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
cd /workspace/vision/infra/daytona
apt-get update
apt-get install -y --no-install-recommends gcc g++ libgomp1 git curl ca-certificates nodejs npm tini procps
rm -rf /var/lib/apt/lists/*
/usr/local/bin/python -m pip install --no-cache-dir uv==0.11.11
npm install -g @openai/codex@0.154.0
uv venv --python /usr/local/bin/python --allow-existing /opt/venvs/science
uv pip install --no-cache --python /opt/venvs/science/bin/python --require-hashes -r science.lock
/opt/venvs/science/bin/python configure_cuda.py
uv venv --python /usr/local/bin/python --allow-existing /opt/venvs/torch
uv pip install --no-cache --python /opt/venvs/torch/bin/python --require-hashes -r torch.lock
uv pip check --python /opt/venvs/science/bin/python
uv pip check --python /opt/venvs/torch/bin/python
mkdir -p /opt/checkpoints /logs/agent /logs/verifier /output /work /persist/setup /persist/artifacts
date -u +%FT%TZ > /persist/setup/bootstrap-complete.txt

#!/bin/sh
set -eu
download_maia_weights.sh
exec uvicorn backend.app:app --host 0.0.0.0 --port 8000

#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export APPWORLD_ROOT=/data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
exec .venv/bin/python -m daedalus.scripts.accumulation --config /data/workspace/PredictMem/configs/ace_appworld_accumulation.yaml --parallel 2

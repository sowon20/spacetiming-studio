#!/usr/bin/env bash
set -e

# 작업 디렉토리를 스크립트 위치로 맞추기
cd "$(dirname "$0")"

# 최상위 프로젝트 루트 기준으로 Python 3.10 가상환경 활성화
ROOT="$(cd ../ && pwd)"
if [ -f "$ROOT/.venv310/bin/activate" ]; then
  source "$ROOT/.venv310/bin/activate"
fi

export PYTHONUNBUFFERED=1

# 필요하면 여기서 GEMINI_API_KEY를 export 해도 됨
# export GEMINI_API_KEY="YOUR_KEY_HERE"

uvicorn main:app \
  --host 127.0.0.1 \
  --port 8899 \
  --reload
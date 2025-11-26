#!/usr/bin/env bash
set -e

# 작업 디렉토리를 스크립트 위치로 맞추기
cd "$(dirname "$0")"

export PYTHONUNBUFFERED=1

# 필요하면 여기서 GEMINI_API_KEY를 export 해도 됨
# export GEMINI_API_KEY="YOUR_KEY_HERE"

uvicorn main:app \
  --host 127.0.0.1 \
  --port 8899 \
  --reload
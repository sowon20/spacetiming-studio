#!/bin/bash

echo "🛰  Flow Automation Agent starting..."

# 0) 루트 env 불러오기
source ../spacetiming-env.sh

# 1) venv 체크
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

# 2) 패키지
pip install --upgrade pip
pip install -r requirements.txt

# 3) 서버 실행
echo "✨ Ready! Running Flow agent at http://127.0.0.1:8898"
uvicorn main:app --reload --port 8898
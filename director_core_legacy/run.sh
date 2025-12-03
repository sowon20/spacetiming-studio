#!/bin/zsh -l

# 🔭 Spacetime Studio - Director Core (부감독 뇌 서버) 실행 스크립트

# 프로젝트 루트 경로
ROOT="$HOME/시공간 스튜디오/spacetiming-studio"

# 1) 가상환경 활성화 (Python 3.10용)
source "$ROOT/.venv310/bin/activate"

# 2) 프로젝트 루트로 이동
cd "$ROOT"

# 3) 필요 라이브러리 설치 (최초 1~2회 정도만 실제로 설치됨)
#   - 이미 설치됐다면 그냥 "Requirement already satisfied" 로그만 찍히고 넘어감
if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
fi

# 4) FastAPI 서버 실행 (포트 8897)
python -m uvicorn director_core.main:app --host 127.0.0.1 --port 8897 --reload

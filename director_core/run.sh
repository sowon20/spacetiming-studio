#!/bin/zsh -l
source ~/.zshrc

# 🔭 Spacetime Studio - Director Core (부감독 뇌 서버) 실행 스크립트

# 프로젝트 루트 경로
ROOT="$HOME/시공간 스튜디오/spacetiming-studio"

# 1) 가상환경 활성화
source "$ROOT/.venv/bin/activate"

# 2) director_core 디렉토리로 이동
cd "$ROOT/director_core"

# 3) 필요 라이브러리 설치 (최초 1~2회 정도만 실제로 설치됨)
pip install -r requirements.txt

# 4) FastAPI 서버 실행 (포트 8897)
python -m uvicorn main:app --host 127.0.0.1 --port 8897 --reload

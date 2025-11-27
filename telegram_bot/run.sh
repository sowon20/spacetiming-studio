#!/bin/zsh -l

ROOT="$HOME/시공간 스튜디오/spacetiming-studio"

# venv 활성화
source "$ROOT/.venv/bin/activate"

# 텔레그램 봇 폴더로 이동
cd "$ROOT/telegram_bot"

# 패키지 설치
pip install -r requirements.txt

# 봇 실행
python bot.py
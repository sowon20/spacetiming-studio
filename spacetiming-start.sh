#!/bin/zsh -l
source ~/.zshrc

# 🔭 Spacetime Studio 일괄 실행 스크립트

# 0) 프로젝트 루트 경로
ROOT="$HOME/시공간 스튜디오/spacetiming-studio"

# 1) VEO 프롬프트 에이전트 서버 (8899)
cd "$ROOT/veo_agent"
/bin/zsh ./run.sh &

sleep 2

# 2) Flow 자동화 에이전트 서버 (8898)
cd "$ROOT/flow_automation"
/bin/zsh ./run.sh &

sleep 2

# 3) Director Core (공통 뇌, 8897)
cd "$ROOT/director_core"
/bin/zsh ./run.sh &

sleep 2

# 4) Telegram Bot (텔레그램 입/귀)
/bin/zsh "$ROOT/telegram_bot/run.sh" &

sleep 2

# 5) 디버그 크롬 띄우기 (Flow 탭 포함)
PROFILE="$HOME/SpacetimeStudioDebugProfile"
mkdir -p "$PROFILE"

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE" \
  "https://labs.google/fx/ko/tools/flow" \
  &

# 조용히 종료 (터미널 창 안남기려고)
exit 0
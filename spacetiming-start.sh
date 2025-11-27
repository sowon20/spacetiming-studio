#!/bin/zsh -l

# 🔭 Spacetime Studio 일괄 실행 스크립트

# 0) 프로젝트 루트 경로 (필요하면 네 맥 경로에 맞게 수정 가능)
ROOT="$HOME/시공간 스튜디오/spacetiming-studio"

# 1) VEO 프롬프트 에이전트 서버 (8899)
cd "$ROOT/veo_agent"
/bin/zsh ./run.sh &

# 너무 동시에 달리면 헷갈리니까 살짝 여유
sleep 2

# 2) Flow 자동화 에이전트 서버 (8898)
cd "$ROOT/flow_automation"
/bin/zsh ./run.sh &

sleep 2

# 3) 디버그 크롬 띄우기 (Flow 탭 포함)
#    - 이 크롬이 Playwright가 붙는 대상.
#    - user-data-dir 은 부감독 전용 프로필 폴더.
PROFILE="$HOME/SpacetimeStudioDebugProfile"
mkdir -p "$PROFILE"

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$PROFILE" \
  "https://labs.google/fx/ko/tools/flow" \
  &

# 조용히 종료 (터미널 창 안남기려고)
exit 0
from typing import Dict, Any, Optional

from playwright.async_api import async_playwright  # pyright: ignore[reportMissingImports]

# 한국어 Flow 페이지
FLOW_URL = "https://labs.google/fx/ko/tools/flow"

# 디버그 크롬 CDP 엔드포인트 (오토메이커/쉘에서 띄운 크롬 포트와 맞춰야 함)
CDP_ENDPOINT = "http://127.0.0.1:9222"

# 전역 상태: 이미 떠 있는 디버그 크롬/탭을 재사용하기 위한 핸들들
_playwright = None          # type: ignore[var-annotated]
_browser = None             # type: ignore[var-annotated]
_flow_page = None           # type: ignore[var-annotated]


async def _ensure_debug_browser():
    """
    이미 떠 있는 '디버그 크롬'에 CDP로 붙는다.
    - 새 브라우저를 띄우지 않고, 오로지 127.0.0.1:9222 에 떠 있는 크롬만 사용.
    - 오토메이커/쉘에서 미리 실행해둔 크롬이 없으면 예외 발생.
    """
    global _playwright, _browser

    if _playwright is None:
        _playwright = await async_playwright().start()

    # 이미 연결된 브라우저가 있으면 그대로 사용
    if _browser is not None:
        try:
            # contexts 접근이 되면 아직 살아있는 걸로 간주
            _ = _browser.contexts
            return _browser
        except Exception:
            _browser = None

    # 새로 디버그 크롬에 attach
    _browser = await _playwright.chromium.connect_over_cdp(CDP_ENDPOINT)
    return _browser


async def _ensure_flow_page():
    """
    디버그 크롬 안에서 Flow 탭을 찾거나, 없으면 새로 연다.

    - 이미 캐시된 _flow_page 가 살아있으면 그대로 사용
    - 아니면 모든 context/pages 를 훑어서 FLOW_URL 로 시작하는 탭을 찾는다
    - 찾지 못하면 첫 번째 context 에서 새 탭을 열어 Flow 로 이동
    """
    global _browser, _flow_page

    browser = await _ensure_debug_browser()

    # 1) 캐시된 페이지가 아직 살아 있으면 그대로 사용
    if _flow_page is not None:
        try:
            if not _flow_page.is_closed():
                return _flow_page
        except Exception:
            _flow_page = None

    # 2) 모든 context/page 에서 Flow 탭 찾기
    for context in browser.contexts:
        for page in context.pages:
            try:
                if page.url.startswith(FLOW_URL):
                    _flow_page = page
                    return _flow_page
            except Exception:
                # 페이지가 로딩 중이거나 url 접근이 안 될 수도 있으니 그냥 무시
                continue

    # 3) 못 찾았으면 새 탭 열기
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = await browser.new_context()

    page = await context.new_page()
    await page.goto(FLOW_URL)
    _flow_page = page
    return _flow_page


async def run_flow_once(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flow 자동화의 외부 진입점.
    - 이미 떠 있는 디버그 크롬(127.0.0.1:9222)에 붙는다.
    - 그 안에서 Flow 탭을 찾거나 열고, payload 를 DevTools 콘솔에 찍어둔다.
    - 나중에 여기서 진짜 자동화(프로젝트 선택, 프롬프트 입력, Generate 버튼 클릭 등)를 추가하면 됨.
    """
    try:
        page = await _ensure_flow_page()
    except Exception as e:
        # 디버그 크롬이 안 떠 있는 경우 등
        return {
            "status": "error",
            "error": f"디버그 크롬(CDP: {CDP_ENDPOINT})에 연결하지 못했어. 먼저 디버그 크롬을 실행해줘. ({e})",
        }

    # 사용자가 Flow 말고 다른 페이지로 가 있었을 수 있으니, 다시 Flow로 보내준다.
    try:
        if not page.url.startswith(FLOW_URL):
            await page.goto(FLOW_URL)
    except Exception:
        await page.goto(FLOW_URL)

    # 여기서 굳이 bring_to_front() 는 안 한다.
    # 디버그 크롬이 갑자기 앞으로 튀어나오는 게 거슬릴 수 있어서,
    # 그냥 조용히 같은 탭 안에서만 동작하도록 둔다.
    # 필요하면 아래 주석을 풀어도 됨.
    #
    # try:
    #     await page.bring_to_front()
    # except Exception:
    #     pass

    # 현재는 payload 를 DevTools 콘솔에 출력만 한다.
    title = payload.get("title", "")
    main_prompt = payload.get("main_prompt", "")
    teaser_prompt = payload.get("teaser_prompt", "")
    plan = payload.get("plan", "")

    await page.evaluate(
        """({ title, main_prompt, teaser_prompt, plan }) => {
            console.log("[Spacetime Studio] Flow automation payload:", {
              title,
              main_prompt,
              teaser_prompt,
              plan,
            });
        }""",
        {
            "title": title,
            "main_prompt": main_prompt,
            "teaser_prompt": teaser_prompt,
            "plan": plan,
        },
    )

    # 나중에 여기서:
    # - 프로젝트 리스트/카드 찾기
    # - 해당 title 과 매칭되는 프로젝트 클릭
    # - 프롬프트 입력 박스 찾기 + 값 세팅
    # - Generate 버튼 클릭
    # - 진행 상태 감시
    # 같은 DOM / Vision 기반 자동화를 얹으면 됨.

    return {
        "status": "browser_attached",
        "notes": (
            "이미 떠 있는 디버그 크롬(127.0.0.1:9222)에 붙어서 Flow 탭을 찾았어. "
            "payload 는 Flow 탭의 DevTools 콘솔에 출력해뒀고, "
            "이제 여기 위에 진짜 자동화 로직(버튼 클릭 등)을 올리면 돼."
        ),
    }
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

ZONE_REQUIRE_APPROVAL = "A"  # 소원 허락 필수
ZONE_AUTO_OK = "B"           # 나중에 자동 적용 가능
ZONE_FORBIDDEN = "C"         # 절대 금지 (기본값)


def apply_config_updates(updates: List[Dict] | None) -> None:
    """
    LLM이 제안한 config_updates를 처리하는 자리.
    지금은 아무 것도 실제로 바꾸지 않고, 로그만 남긴다.
    나중에 A/B 존별로 실제 적용 로직을 붙이면 된다.
    """
    if not updates:
        return

    for u in updates:
        zone = u.get("zone") or ZONE_FORBIDDEN
        target = u.get("target")
        field = u.get("field")
        value = u.get("value")

        if zone == ZONE_FORBIDDEN:
            logger.info("config_update ignored (forbidden zone C): %s", u)
            # 완전 무시
            continue

        if zone == ZONE_REQUIRE_APPROVAL:
            logger.info("config_update pending approval (zone A): %s", u)
            # TODO: 나중에 '승인 대기' 큐에 쌓기
            continue

        if zone == ZONE_AUTO_OK:
            logger.info("config_update auto-ok candidate (zone B): %s", u)
            # TODO: 나중에 실제 설정 적용 로직 추가
            continue

        logger.info("config_update with unknown zone ignored: %s", u)
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from flow_playwright import run_flow_once

logger = logging.getLogger(__name__)

app = FastAPI()


class FlowRunRequest(BaseModel):
    title: str
    main_prompt: str
    teaser_prompt: Optional[str] = ""
    plan: Optional[str] = ""


@app.get("/")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "flow_automation"}


@app.post("/flow/run")
async def flow_run(req: FlowRunRequest) -> Dict[str, Any]:
    """
    사이드바에서 'Flow 자동 실행' 버튼 누르면 호출되는 엔드포인트.
    asyncio.run() 안 쓰고, 그냥 run_flow_once를 await로 한 번 실행만 해.
    """
    try:
        payload = {
            "title": req.title,
            "main_prompt": req.main_prompt,
            "teaser_prompt": req.teaser_prompt or "",
            "plan": req.plan or "",
        }
        result = await run_flow_once(payload)
        return {"ok": True, "result": result}
    except Exception as e:
        logger.exception("Flow run failed")
        return {"ok": False, "error": str(e)}
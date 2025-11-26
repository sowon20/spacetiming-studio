from typing import Tuple
import json

from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL_TEXT

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았어.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _extract_json_block(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def generate_veo_prompts_sync(title: str, plan: str) -> Tuple[str, str]:
    client = _get_client()

    system_prompt = (
        "You are an expert cinematic director and prompt writer for Google Veo.\n"
        "The channel tone is dreamy, calm, cosmic, ASMR-friendly.\n"
        "No harsh flashing lights, no gore, no loud sounds.\n"
        "Camera moves are smooth and gentle, lighting is warm or moonlit.\n"
    )

    user_prompt = f'''Create two prompts for Google Veo.

Title: {title}
Plan / mood / intent:
{plan}

Requirements:
- main_prompt: around 4-5 minutes, 4-6 scenes, smooth camera, warm or moonlit lighting,
  gentle cosmic feeling, small but clear emotional arc, ASMR-friendly.
- teaser_prompt: 8-12 seconds, one striking moment or emotional peak from the same world.
- Avoid loops, flashing lights, graphic content.
- Avoid over-explaining: give Veo a clean, direct prompt.

Return them as JSON with keys "main_prompt" and "teaser_prompt".
'''

    result = client.models.generate_content(
        model=GEMINI_MODEL_TEXT,
        contents=system_prompt + "\n\n" + user_prompt,
    )
    text = (result.text or "").strip()

    try:
        block = _extract_json_block(text)
        data = json.loads(block)
        main_prompt = data.get("main_prompt", "").strip()
        teaser_prompt = data.get("teaser_prompt", "").strip()
        if not main_prompt:
            main_prompt = text
        if not teaser_prompt:
            teaser_prompt = (text[:500] + "...") if len(text) > 500 else text
        return main_prompt, teaser_prompt
    except Exception:
        teaser = (text[:500] + "...") if len(text) > 500 else text
        return text, teaser
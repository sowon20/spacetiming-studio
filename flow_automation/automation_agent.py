"""
Flow automation entrypoint.

uvicorn main:app --reload --port 8898

이 파일은 단순히 automation_agent.py 안의 FastAPI app을 다시 export만 해줘.
"""

from automation_agent import app
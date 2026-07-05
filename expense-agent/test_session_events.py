import os
import asyncio
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

os.environ["GOOGLE_CLOUD_PROJECT"] = "gen-lang-client-0560374860"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east1"

async def run():
    service = VertexAiSessionService(
        project="gen-lang-client-0560374860",
        location="us-east1",
        agent_engine_id="6217043363724525568"
    )
    
    sess = await service.get_session(app_name="app", user_id="default-user", session_id="3565263759842738176")
    history = getattr(sess, "events", getattr(sess, "history", []))
    for event in history:
        print(event)

asyncio.run(run())

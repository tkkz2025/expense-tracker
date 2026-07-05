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
    
    sessions = await service.list_sessions(user_id="default-user", app_name="app")
    if sessions:
        sess = sessions[0]
        print(f"Session object: {dir(sess)}")
        history = sess.history if hasattr(sess, "history") else sess.events if hasattr(sess, "events") else None
        print(f"History: {history}")

asyncio.run(run())

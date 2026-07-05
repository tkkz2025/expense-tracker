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
    
    resp = await service.list_sessions(user_id="default-user", app_name="app")
    print(dir(resp))
    if hasattr(resp, "sessions"):
        for s in resp.sessions:
            print(f"Session: {s.id}")
            sess = await service.get_session(app_name="app", user_id="default-user", session_id=s.id)
            print(dir(sess))
            history = sess.history if hasattr(sess, "history") else sess.events if hasattr(sess, "events") else None
            print(history)

asyncio.run(run())

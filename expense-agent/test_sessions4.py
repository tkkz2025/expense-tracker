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
    for s in getattr(resp, "sessions", []):
        sess = await service.get_session(app_name="app", user_id="default-user", session_id=s.id)
        history = getattr(sess, "events", getattr(sess, "history", []))
        call_events = {}
        response_events = set()
        for event in history:
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", []) if content else getattr(event, "parts", [])
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc and getattr(fc, "name", "") == "adk_request_input":
                    call_events[getattr(fc, "id", "")] = fc
                fr = getattr(part, "function_response", None)
                if fr and getattr(fr, "name", "") == "adk_request_input":
                    response_events.add(getattr(fr, "id", ""))
        print(f"Session {s.id}:")
        print(f"  Calls: {list(call_events.keys())}")
        print(f"  Responses: {response_events}")

asyncio.run(run())

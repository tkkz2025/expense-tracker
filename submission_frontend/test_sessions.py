import os
import google.auth
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService

os.environ["GOOGLE_CLOUD_PROJECT"] = "gen-lang-client-0560374860"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east1"
os.environ["AGENT_RUNTIME_ID"] = "6217043363724525568"

service = VertexAiSessionService(
    project="gen-lang-client-0560374860",
    location="us-east1",
    engine_id="6217043363724525568"
)

sessions = service.list_sessions(user_id="default-user")
print(f"Found {len(sessions)} sessions for default-user")
for s in sessions:
    print(f"Session: {s.id}")
    history = service.read_history(user_id="default-user", session_id=s.id)
    for event in history:
        print(f"  Event: {event}")

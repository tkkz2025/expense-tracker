from vertexai.agent_engines.templates.adk import AdkApp
from app.agent import app as adk_app
from app.app_utils import services

runtime = AdkApp(
    app=adk_app,
    session_service_builder=services.get_session_service,
    artifact_service_builder=services.get_artifact_service,
)
runtime.set_up()
operations = runtime.register_operations()
print(operations)

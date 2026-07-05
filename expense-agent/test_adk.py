from app.app_utils.reasoning_engine_adapter import attach_reasoning_engine_routes
from fastapi import FastAPI
app = FastAPI()
try:
    attach_reasoning_engine_routes(app)
except Exception as e:
    print(e)

import asyncio
from httpx import AsyncClient

async def run():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/reasoning_engine", json={"class_method": "query", "input": {}})
        print(response.json())
        
        response2 = await ac.post("/api/reasoning_engine", json={"class_method": "stream_query", "input": {}})
        print(response2.json())

asyncio.run(run())

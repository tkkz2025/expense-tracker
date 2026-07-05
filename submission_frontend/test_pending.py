import os
os.environ["GOOGLE_CLOUD_PROJECT"] = "gen-lang-client-0560374860"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east1"
os.environ["AGENT_RUNTIME_ID"] = "6217043363724525568"

import asyncio
import main
from main import app, get_pending

async def test():
    pending = await get_pending()
    for item in pending:
        print("Pending:", item)

asyncio.run(test())

import asyncio
import aiohttp

async def check():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://boards-api.greenhouse.io/v1/boards/2k/jobs", timeout=10) as resp:
                print(resp.status)
        except Exception as e:
            print("Error:", e)
            
asyncio.run(check())

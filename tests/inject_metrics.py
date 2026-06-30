import asyncio
import httpx
import argparse
import time

async def inject_good(target_url: str, count: int = 10):
    print(f"Injecting {count} GOOD requests...")
    async with httpx.AsyncClient() as client:
        for _ in range(count):
            try:
                # Assuming router handles GET to /
                await client.get(target_url)
            except Exception:
                pass
            await asyncio.sleep(0.1)
            
async def inject_bad(target_url: str, count: int = 10):
    print(f"Injecting {count} BAD (500) requests...")
    async with httpx.AsyncClient() as client:
        for _ in range(count):
            try:
                # Hitting an endpoint that doesn't exist on the stub
                await client.get(f"{target_url}/trigger_error")
            except Exception:
                pass
            await asyncio.sleep(0.1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("type", choices=["good", "bad"])
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()
    
    if args.type == "good":
        asyncio.run(inject_good(args.url, args.count))
    else:
        asyncio.run(inject_bad(args.url, args.count))

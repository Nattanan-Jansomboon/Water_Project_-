import asyncio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def test():
    async with httpx.AsyncClient(timeout=145) as client:
        async with streamable_http_client(
            "http://localhost:8080/mcp", http_client=client
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()

                # เช็คว่าเห็น tool
                listing = await session.list_tools()
                print("Tools found:", [t.name for t in listing.tools])

                # ทดสอบถามจริง
                result = await session.call_tool("ask_wiki", {
                    "task": "กำแพงเพชรมีแหล่งมรดกโลกอะไรบ้าง"
                })

                if result.isError:
                    print("ERROR — ดู server logs")
                else:
                    for block in result.content:
                        if block.type == "text":
                            print("Answer:", block.text)

asyncio.run(test())
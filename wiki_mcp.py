"""
servers/wiki_mcp.py — MCP wrapper สำหรับ Wiki กำแพงเพชร

วางไฟล์นี้ไว้ใน project เดียวกับ agents.py, config.py, session_store.py
แล้วรันด้วย:
    uv run --no-sync python -m servers.wiki_mcp --http 8080

หรือจะรันตรงจาก directory เดียวกับไฟล์ก็ได้:
    python wiki_mcp.py --http 8080

จุดสำคัญ:
- expose เฉพาะ ask_wiki (query) เท่านั้น ไม่ expose ingest
- แต่ละ MCP call ได้ session ใหม่เสมอ (stateless per call)
  ถ้าต้องการ multi-turn ให้ client ส่ง session_id มาใน task เอง
- _profile_switch_lock ใน agents.py ยังทำงานอยู่ตามปกติ
  ดังนั้น concurrent MCP calls จะถูก serialize โดยอัตโนมัติ
- exception จาก run_query ถูก sanitize ก่อนส่งกลับ client
  ไม่ expose stack trace หรือ path จริงออกไป
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.mcpserver import MCPServer as FastMCP
from mcp.server.transport_security import TransportSecuritySettings
# import จาก project เดิม (อยู่ใน directory เดียวกัน หรือใน PYTHONPATH)
import agents
import session_store

# ---- logging ----------------------------------------------------------------
# ใช้ stderr เท่านั้น — stdout สงวนไว้สำหรับ MCP protocol messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],  # StreamHandler default คือ stderr
)
logger = logging.getLogger("wiki_mcp")

# ---- lifespan ---------------------------------------------------------------
# ใช้ lifespan ของ FastMCP เพื่อ log ตอน startup/shutdown
# (agents.py ไม่มี async resource ที่ต้อง init ที่นี่เพิ่มเติม
#  เพราะ AIAgent สร้างใหม่ทุก request อยู่แล้ว)

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    logger.info("wiki_mcp: starting up — vault path: %s", agents.settings.obsidian_vault_path)
    yield
    logger.info("wiki_mcp: shutting down")


# ---- MCP server -------------------------------------------------------------
mcp = FastMCP(
    name="wiki-kamphaeng-phet",
    lifespan=lifespan,
)


transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[
        "waterwiki.pasaflow.com",
        "waterwiki.pasaflow.com:*",
        "10.222.43.195",
        "10.222.43.195:*",
    ],
    allowed_origins=[
        "https://waterwiki.pasaflow.com",
    ],
)


# ---- tools ------------------------------------------------------------------

@mcp.tool()
async def ask_wiki(task: str) -> str:
    """
    ตอบคำถามจาก wiki กำแพงเพชร โดยค้นหาจาก Obsidian vault แล้วสรุปคำตอบพร้อมอ้างอิง note

    Args:
        task: คำถามที่ต้องการถามเกี่ยวกับข้อมูลในฐานความรู้กำแพงเพชร
              เช่น "กำแพงเพชรมีแหล่งมรดกโลกอะไรบ้าง"

    Returns:
        คำตอบจาก Query Agent พร้อมระบุ note ที่ใช้อ้างอิง
    """
    if not task or not task.strip():
        return "กรุณาระบุคำถาม"

    # สร้าง session id ใหม่ต่อ 1 MCP call (stateless)
    session_id = f"mcp-{uuid.uuid4()}"
    history = session_store.get_history(session_id)  # จะได้ [] เสมอ (session ใหม่)

    logger.info("ask_wiki called | session=%s | task_preview=%.80s", session_id, task)

    try:
        result = await asyncio.to_thread(
            agents.run_query,
            task,
            history,
            session_id,
        )
    except Exception as exc:
        # sanitize — ไม่ส่ง stack trace หรือ internal path ออกไปให้ client
        logger.exception("ask_wiki: run_query failed | session=%s", session_id)
        raise RuntimeError(
            "Query agent failed — ตรวจสอบ server logs สำหรับรายละเอียด"
        ) from exc

    answer = result.get("final_response", "").strip()
    if not answer:
        logger.warning("ask_wiki: empty response | session=%s", session_id)
        return "Agent ไม่ได้ส่งคำตอบกลับมา — ลองถามใหม่อีกครั้ง"

    logger.info("ask_wiki: ok | session=%s | answer_len=%d", session_id, len(answer))
    return answer


# ---- entrypoint -------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wiki Kamphaeng Phet MCP server")
    parser.add_argument(
        "--http",
        metavar="PORT",
        type=int,
        default=None,
        help="รันเป็น Streamable HTTP บน port นี้ (ละไว้ = stdio mode)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="bind address สำหรับ HTTP mode (default: 0.0.0.0)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.http:
        import uvicorn
        logger.info("wiki_mcp: HTTP mode — http://%s:%d/mcp", args.host, args.http)
        uvicorn.run(mcp.streamable_http_app(transport_security=transport_security, host="0.0.0.0"), host="0.0.0.0", port=args.http)
    else:
        logger.info("wiki_mcp: stdio mode")
        mcp.run(transport="stdio")

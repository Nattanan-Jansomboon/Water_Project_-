# Hermes Ingest + Query Backend

Implementation ตามไฟล์ `hermes-ingest-query-plan.md`

## วิธีติดตั้ง/รัน

### ติดตั้ง Miniforge (ครั้งแรกครั้งเดียว)

```bash
wget "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
bash Miniforge3-$(uname)-$(uname -m).sh
source ~/.bashrc
```

### สร้าง Environment และติดตั้ง Package

```bash
# สร้าง environment Python 3.12 (hermes-agent ต้องการ >=3.11,<3.14)
conda create --name water_project python=3.12 -y
conda activate water_project

# clone hermes-agent และติดตั้ง
git clone https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
pip install -e .

# ติดตั้ง package ที่ backend ต้องใช้
pip install -r requirements.txt
```

### รัน Backend

```bash
python -m uvicorn main:app --reload --port 8888 --host 0.0.0.0
จากนั้นเปิดด้วย http://<server-ip>:8888
```

### เปิด MCP Server

```bash
python wiki_mcp.py --http 8888
```

เปิด `http://localhost:8888/` เพื่อใช้งานหน้าเว็บอัปโหลด + แชท  
`GET /api/health` ใช้เช็คว่า path ที่ตั้งค่าไว้ทั้ง 4 ตัวมีอยู่จริงหรือไม่

### ครั้งต่อไป (activate environment ที่มีอยู่แล้ว)

```bash
conda activate water_project
cd backend
python -m uvicorn main:app --reload
```

## หมายเหตุสำคัญ

- hermes-agent กำหนด `requires-python = ">=3.11,<3.14"` ใน `pyproject.toml` — ต้องใช้ Python ในช่วงนี้เท่านั้น
- ต้องรัน `pip install` ทั้งหมด **ขณะที่ activate environment อยู่** ไม่งั้น package จะไปลงที่ Python ของระบบแทน
- `python-multipart` จำเป็นสำหรับ FastAPI endpoint `/api/ingest` ที่รับ `multipart/form-data` (อัปโหลดไฟล์)

## จุดที่แก้ไขจากแผนเดิม (ตรวจสอบกับซอร์สโค้ด hermes-agent จริงแล้ว)

- **`enabled_toolsets=["terminal", "filesystem"]` ผิด** — ชื่อที่ถูกต้องคือ **`"file"`** แก้ไขแล้วใน `agents.py`: Ingestion Agent ใช้ `["terminal", "file"]`, Query Agent ใช้ `["file"]`
- ส่วน `AIAgent.__init__`, `run_conversation()` และ key ของผลลัพธ์ (`final_response` / `messages`) ตรงกับที่แผนระบุทุกอย่าง
- กลไก `HERMES_HOME` ตรงกับแผน: default เป็น `~/.hermes` ถ้าไม่ตั้งค่า

## สิ่งที่ implement แล้ว

- `config.py` — โหลด `.env`, validate path/API key ที่จำเป็น
- `agents.py` — สร้าง `AIAgent` ทั้ง 2 profile ด้วย `threading.Lock` (Option A) เพื่อกัน race condition
- `session_store.py` — in-memory `dict[session_id] -> messages`
- `main.py` — endpoint `POST /api/ingest`, `POST /api/query`, `GET /api/health` และ mount หน้าเว็บ static ที่ `/`
- `static/index.html` — หน้าเว็บ plain HTML/JS อัปโหลดไฟล์ + แชท

## สิ่งที่ยังไม่ได้ทำ

- ยืนยัน path ของทั้ง 2 profile (`water_llm`, `water_llm_qa`) มีอยู่จริง — เช็คผ่าน `/api/health`
- ทดสอบ multi-turn แบบ end-to-end (ต้องมี vault จริง + รัน Hermes จริง)
- Option B (แยกเป็น 2 process) — ยังไม่จำเป็นจนกว่าจะมี concurrent traffic จริง
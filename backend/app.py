import json
import time
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .engine import PdrEngine


app = FastAPI(title="PDR Backend Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


sessions: Dict[str, PdrEngine] = {}
frontend_dir = Path(__file__).resolve().parents[1]


@app.get("/health")
def health() -> Dict:
    return {"ok": True, "sessions": len(sessions)}


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.post("/api/session")
def create_session() -> Dict:
    sid = str(uuid.uuid4())
    engine = PdrEngine()
    engine.reset(time.time() * 1000.0)
    sessions[sid] = engine
    return {"session_id": sid}


@app.websocket("/ws/pdr/{session_id}")
async def ws_pdr(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    if session_id not in sessions:
        sessions[session_id] = PdrEngine()
        sessions[session_id].reset(time.time() * 1000.0)
    engine = sessions[session_id]
    try:
        await websocket.send_text(json.dumps({"type": "session_ready", "session_id": session_id}))
        while True:
            payload = await websocket.receive_text()
            msg = json.loads(payload)
            event_type = msg.get("type")
            if event_type == "reset":
                engine.reset(float(msg.get("t_ms") or (time.time() * 1000.0)))
                await websocket.send_text(json.dumps({"type": "reset_ack"}))
                continue
            if event_type != "sensor_frame":
                continue
            pose = engine.process_frame(msg)
            await websocket.send_text(json.dumps(pose))
    except WebSocketDisconnect:
        return

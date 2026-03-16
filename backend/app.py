import json
import random
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .engine import PdrEngine
from . import coord_convert

TILE_SOURCES = [
    "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
]


app = FastAPI(title="PDR Backend Engine", version="1.0.0")

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


@app.get("/api/tiles/{z:int}/{x:int}/{y:int}")
async def proxy_tile(z: int, x: int, y: int) -> Response:
    """Proxy map tiles for users in China where OSM is blocked."""
    url = random.choice(TILE_SOURCES).format(z=z, x=x, y=y)
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "PDR-AirChina/1.0 (map-tile-proxy)"},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            return Response(
                content=r.content,
                media_type="image/png",
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        return Response(status_code=502)


class CoordBody(BaseModel):
    lat: float
    lng: Optional[float] = None
    lon: Optional[float] = None


@app.post("/api/coord/gcj02_to_wgs84")
def api_gcj02_to_wgs84(body: CoordBody) -> Dict:
    """Convert a single point from GCJ-02 to WGS-84 (for OSM / GPS)."""
    lon = body.lng if body.lng is not None else body.lon
    if lon is None:
        return {"error": "lng or lon required"}
    wgs_lat, wgs_lon = coord_convert.gcj02_to_wgs84(body.lat, lon)
    return {"lat": wgs_lat, "lng": wgs_lon}


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
        pass
    finally:
        sessions.pop(session_id, None)

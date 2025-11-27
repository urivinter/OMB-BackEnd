# main.py
from random import randint


from starlette.websockets import WebSocketDisconnect
from fastapi import FastAPI, HTTPException, responses, WebSocket

from fastapi.middleware.cors import CORSMiddleware

from modules import ConnectionManager, decode, set_bit, get_all

# --- FastAPI Application Setup ---

app = FastAPI()
manager = ConnectionManager()
# This allows frontend to communicate with backend
origins = [
    "http://localhost:8000",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

SPECIAL = {randint(0, 999999): randint(0, 3) for _ in range(2000)}
# --- API Endpoints ---

@app.get("/api/boxes/")
async def get_boxes():
    try:
        res = await get_all()
        return responses.Response(res, media_type="application/octet-stream")

    except Exception as e:
        print(e)
        return HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/api/special/")
async def get_specials():
    return SPECIAL


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            offset, value = decode(data)
            set_bit(offset, value)
            await manager.broadcast(data)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

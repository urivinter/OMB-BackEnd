# main.py
import pickle
import os

import logfire
from starlette.websockets import WebSocketDisconnect
from fastapi import FastAPI, HTTPException, responses, WebSocket

from fastapi.middleware.cors import CORSMiddleware
from modules import ConnectionManager, decode, set_bit, get_all


# --- FastAPI Application Setup ---

app = FastAPI()
logfire.configure()
logfire.instrument_fastapi(app)
manager = ConnectionManager()

# Read allowed origins from an environment variable, splitting by comma
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",")
logfire.info(f"Allowing CORS for origins: {origins}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

with open('special.pkl', 'rb') as file:
    SPECIAL = pickle.load(file)
SPECIAL.update({30:0, 40:1, 50:2, 60:3})

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

@app.get("/api/active_players")
async def get_active_players():
    return await manager.get_total_active_players()


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            try:
                offset, value = decode(data)
            except ValueError:
                logfire.error("Invalid data received", data=data)
                continue
            e =  await set_bit(offset, value)
            if e is not None:
                logfire.error(f"Error setting bit", offset=offset, value=value, error=e)
                continue

            await manager.broadcast(data)
    except WebSocketDisconnect:
        pass
    finally: # The 'finally' block ensures disconnection even if an error occurs in the loop
        await manager.disconnect(websocket)

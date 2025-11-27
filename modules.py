from fastapi import WebSocket
import redis

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    @property
    def active_players(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: bytes):
        for connection in self.active_connections:
            await connection.send_bytes(data)


def decode(data: bytes) -> tuple[int, int]:
    """
    Decode 3-byte binary format to (offset, value).
    Compatible with the 23-bit offset, 1-bit value frontend scheme.
    Scheme: metadata: 3 bits, val: 1 bit, offset: 20 bits
    """
    if len(data) != 3:
        raise ValueError(f"Error: Expected 3 bytes, got {len(data)}")

    value = 1 if (data[0] & 0x10) else 0
    offset = data[2] | (data[1] << 8) | ((data[0] & 0x0F) << 16)

    return offset, value

def set_bit(offset: int, value: int):
    try:
        r = redis.Redis()
        pipe = r.bitfield('boxes')
        pipe.set('u1', offset, value)
        _ = pipe.execute()
        r.close()
    except Exception as e:
        print(e)

async def get_all():
    # Connect to Redis
    r = redis.Redis(decode_responses=False)
    res = r.get('boxes')
    r.close()
    return res

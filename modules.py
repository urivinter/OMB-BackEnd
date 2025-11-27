from fastapi import WebSocket
import redis

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, offset: int, value: int):
        msg = encode(offset, value)
        print(f'PUSHED:\t\t{msg}')
        for connection in self.active_connections:
            await connection.send_bytes(msg)


def decode(data: bytes) -> tuple[int, int]:
    """
    Decode 3-byte binary format to (offset, value).
    Compatible with the 23-bit offset, 1-bit value frontend scheme.
    """
    if len(data) != 3:
        raise ValueError(f"Error: Expected 3 bytes, got {len(data)}")

    # Value is stored in the most significant bit (MSB) of the third byte.
    value = 1 if (data[2] & 0x80) else 0

    # Offset is stored in the first two bytes and the lower 7 bits of the third byte.
    # Mask the third byte with 0x7F to exclude the value bit.
    offset = data[0] | (data[1] << 8) | ((data[2] & 0x7F) << 16)

    return offset, value


def encode(offset: int, value: int) -> bytes:
    """
    Encode (offset, value) to a 3-byte binary format.
    Uses 23 bits for offset and 1 bit for value.
    """
    if offset >= 2 ** 23:
        raise ValueError(f"Offset {offset} is too large for 23 bits.")

    data = bytearray(3)
    data[0] = offset & 0xFF
    data[1] = (offset >> 8) & 0xFF

    # Use the lower 7 bits of the byte for the offset, and the MSB for the value.
    data[2] = ((offset >> 16) & 0x7F) | (0x80 if value else 0)

    return bytes(data)


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

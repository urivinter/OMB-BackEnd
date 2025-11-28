import logfire
from fastapi import WebSocket
import redis
from dotenv import load_dotenv
import requests
from enum import IntEnum
import os

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class Notification(IntEnum):
    blank           = 0
    active_players  = 1



class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        logfire.info("Connection manager initialized")

    @property
    def active_players(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        logfire.info(f"New player connected.", total=self.active_players, player=websocket.client.host)
        notify_admin(f"New player connected.\nCurrently active: {self.active_players}")
        self.active_connections.append(websocket)
        data = notification(Notification.active_players, self.active_players)
        await self.broadcast(data)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
            logfire.info(f"Player disconnected.", total=self.active_players, player=websocket.client.host)
            data = notification(Notification.active_players, self.active_players)
            self.broadcast(data)
        except ValueError:
            logfire.warning(f"Attempted to disconnect a non-existent websocket: {websocket.client.host}")


    async def broadcast(self, data: bytes):

        for connection in self.active_connections:
            try:
                await connection.send_bytes(data)
            except Exception as e:
                logfire.error(f"Failed to send broadcast", player=connection.client.host, error=e)
                # maybe:
                # self.disconnect(connection)
        



def decode(data: bytes) -> tuple[int, int]:
    """
    Decode 3-byte binary format to (offset, value).
    Scheme: metadata: 3 bits, val: 1 bit, offset: 20 bits
    """
    if len(data) != 3:
        raise ValueError(f"Error: Expected 3 bytes, got {len(data)}")

    value = 1 if (data[0] & 0x10) else 0
    offset = data[2] | (data[1] << 8) | ((data[0] & 0x0F) << 16)

    return offset, value

def set_bit(offset: int, value: int) -> Exception | None:
    try:
        r = redis.Redis()
        pipe = r.bitfield('boxes')
        pipe.set('u1', offset, value)
        _ = pipe.execute()
        r.close()
    except Exception as e:
        return e

async def get_all():
    try:
        # Connect to Redis
        r = redis.Redis(decode_responses=False)
        res = r.get('boxes')
        r.close()
        return res
    except redis.exceptions.ConnectionError as e:
        logfire.error(f"Redis connection error in get_all", error=e)
        return e
    except Exception as e:
        logfire.error(f"An unexpected error occurred in get_all", error=e)
        return e


def notification(notification: Notification, value: int) -> bytes:
    return (notification << 20 | value).to_bytes(3)

def notify_admin(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logfire.warning("Telegram bot token or chat ID not set. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })
        response.raise_for_status()  # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        logfire.error(f"Failed to send Telegram notification", error=e)

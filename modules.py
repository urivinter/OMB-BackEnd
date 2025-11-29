import logfire
from fastapi import WebSocket
import asyncio
import redis
from redis.asyncio import Redis
import httpx
from dotenv import load_dotenv
from enum import IntEnum
import os

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Create a single, reusable Redis connection pool
redis_pool = redis.asyncio.ConnectionPool.from_url(REDIS_URL, decode_responses=False)
BROADCAST_CHANNEL = "broadcast_channel"
GLOBAL_PLAYERS_KEY = "global_active_players"


# Create a single async Redis client instance to be reused by helper functions
redis_client = Redis(connection_pool=redis_pool)

class Notification(IntEnum):
    blank           = 0
    active_players  = 1



class ConnectionManager:
    def __init__(self):
        # This dictionary will map a WebSocket to its Redis listener task
        self.active_connections: dict[WebSocket, asyncio.Task] = {}
        logfire.info("Connection manager initialized")

    async def get_total_active_players(self) -> int:
        """Gets the total number of active players from the shared Redis counter."""
        count = await redis_client.get(GLOBAL_PLAYERS_KEY)
        return int(count) if count else 0

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        # Atomically increment the global player count and get the new total
        total_players = await redis_client.incr(GLOBAL_PLAYERS_KEY)

        await notify_admin(f"New player connected.\nCurrently active: {total_players}")
        logfire.info(f"New player connected.", total=total_players, player=websocket.client.host)

        # Create a listener task for this specific websocket
        listener_task = asyncio.create_task(self._redis_listener(websocket))
        self.active_connections[websocket] = listener_task

        # Announce the new total player count to all clients via Redis Pub/Sub
        data = notification(Notification.active_players, total_players)
        await self.broadcast(data)

    async def disconnect(self, websocket: WebSocket):
        try:
            # Cancel the listener task and remove the websocket from the active list
            listener_task = self.active_connections.pop(websocket)
            listener_task.cancel()

            # Atomically decrement the global player count and get the new total
            total_players = await redis_client.decr(GLOBAL_PLAYERS_KEY)
            logfire.info(f"Player disconnected.", total=total_players, player=websocket.client.host)

            # Notify remaining players about the updated count via Redis Pub/Sub
            data = notification(Notification.active_players, total_players)
            await self.broadcast(data)
        except ValueError:
            logfire.warning(f"Attempted to disconnect a non-existent websocket: {websocket.client.host}")
        except KeyError:
            logfire.warning(f"Attempted to disconnect a websocket that was not in the active list: {websocket.client.host}")


    async def broadcast(self, data: bytes):
        """Publishes a message to the Redis channel for all workers to receive."""
        await redis_client.publish(BROADCAST_CHANNEL, data)

    async def _redis_listener(self, websocket: WebSocket):
        """Listens for messages on the Redis channel and sends them to a single websocket."""
        # Use a separate client for pubsub to avoid conflicts with other commands
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(BROADCAST_CHANNEL)
            while True:
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
                    if message and message['type'] == 'message':
                        await websocket.send_bytes(message['data'])
                except asyncio.CancelledError:
                    break # Task was cancelled, exit loop
                except Exception as e:
                    logfire.error("Error in Redis listener or sending to websocket", error=e)
                    break # Exit on other errors


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


async def set_bit(offset: int, value: int) -> Exception | None:
    try:
        # Use the async Redis client with the connection pool
        await redis_client.bitfield('boxes').set('u1', offset, value).execute()
    except Exception as e:
        return e

async def get_all():
    try:
        # Use the async Redis client with the connection pool
        res = await redis_client.get('boxes')
        return res
    except redis.exceptions.ConnectionError as e:
        logfire.error(f"Redis connection error in get_all", error=e)
        return e
    except Exception as e:
        logfire.error(f"An unexpected error occurred in get_all", error=e)
        return e


def notification(notification: Notification, value: int) -> bytes:
    return ((notification << 21) | value).to_bytes(3)

async def notify_admin(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logfire.warning("Telegram bot token or chat ID not set. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML"
            })
            response.raise_for_status()  # Raise an exception for bad status codes
        except httpx.RequestError as e:
            logfire.error(f"Failed to send Telegram notification", error=e)

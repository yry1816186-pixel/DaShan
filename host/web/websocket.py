import logging
import json
import asyncio
from typing import Dict, Set, Any, Callable, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import orjson

logger = logging.getLogger(__name__)


@dataclass
class WebSocketMessage:
    event_type: str
    data: Any
    timestamp: float
    source: str = "dashan"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> bytes:
        return orjson.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketMessage':
        return cls(
            event_type=data.get("event_type", ""),
            data=data.get("data", {}),
            timestamp=data.get("timestamp", datetime.now().timestamp()),
            source=data.get("source", "dashan")
        )


class WebSocketBroadcaster:
    def __init__(self):
        self._connections: Set[asyncio.Queue] = set()
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._message_history: List[WebSocketMessage] = []
        self._max_history = 100
        self._stats = {
            "total_messages": 0,
            "connections": 0,
            "errors": 0
        }
        
        logger.info("WebSocketBroadcaster initialized")
    
    def add_connection(self, connection: asyncio.Queue):
        self._connections.add(connection)
        self._stats["connections"] = len(self._connections)
        logger.info(f"Connection added (total: {len(self._connections)})")
    
    def remove_connection(self, connection: asyncio.Queue):
        if connection in self._connections:
            self._connections.discard(connection)
            self._stats["connections"] = len(self._connections)
            logger.info(f"Connection removed (total: {len(self._connections)})")
    
    def broadcast(self, event_type: str, data: Any, source: str = "dashan"):
        message = WebSocketMessage(
            event_type=event_type,
            data=data,
            timestamp=datetime.now().timestamp(),
            source=source
        )
        
        self._message_history.append(message)
        
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]
        
        self._stats["total_messages"] += 1
        
        asyncio.create_task(self._broadcast_async(message))
        
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    handler(message)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")
    
    async def _broadcast_async(self, message: WebSocketMessage):
        disconnected = set()
        
        for connection in self._connections:
            try:
                await connection.put(message)
            except Exception as e:
                logger.error(f"Failed to send to connection: {e}")
                disconnected.add(connection)
                self._stats["errors"] += 1
        
        for conn in disconnected:
            self.remove_connection(conn)
    
    def on(self, event_type: str, handler: Callable):
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [msg.to_dict() for msg in self._message_history[-limit:]]
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "active_connections": len(self._connections),
            "history_size": len(self._message_history)
        }
    
    def clear_history(self):
        self._message_history.clear()
        logger.info("Message history cleared")


class WebSocketManager:
    def __init__(self, broadcaster: WebSocketBroadcaster):
        self.broadcaster = broadcaster
        self._client_info: Dict[str, Dict[str, Any]] = {}
        self._subscriptions: Dict[str, Set[str]] = {}
        
        logger.info("WebSocketManager initialized")
    
    async def connect(self, client_id: str, queue: asyncio.Queue):
        self.broadcaster.add_connection(queue)
        
        self._client_info[client_id] = {
            "connected_at": datetime.now().isoformat(),
            "subscribed_events": set()
        }
        
        await queue.put(WebSocketMessage(
            event_type="connected",
            data={"client_id": client_id},
            timestamp=datetime.now().timestamp()
        ).to_json())
        
        logger.info(f"Client connected: {client_id}")
    
    async def disconnect(self, client_id: str, queue: asyncio.Queue):
        self.broadcaster.remove_connection(queue)
        
        if client_id in self._client_info:
            del self._client_info[client_id]
        
        logger.info(f"Client disconnected: {client_id}")
    
    def subscribe(self, client_id: str, event_types: List[str]):
        if client_id not in self._client_info:
            return
        
        for event_type in event_types:
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = set()
            self._subscriptions[event_type].add(client_id)
        
        self._client_info[client_id]["subscribed_events"].update(event_types)
        logger.info(f"Client {client_id} subscribed to: {event_types}")
    
    def unsubscribe(self, client_id: str, event_types: List[str]):
        if client_id not in self._client_info:
            return
        
        for event_type in event_types:
            if event_type in self._subscriptions:
                self._subscriptions[event_type].discard(client_id)
        
        self._client_info[client_id]["subscribed_events"].difference_update(event_types)
        logger.info(f"Client {client_id} unsubscribed from: {event_types}")
    
    def get_subscribed_clients(self, event_type: str) -> Set[str]:
        return self._subscriptions.get(event_type, set())
    
    def get_client_info(self, client_id: str) -> Optional[Dict[str, Any]]:
        return self._client_info.get(client_id)
    
    def get_all_clients(self) -> Dict[str, Dict[str, Any]]:
        return self._client_info.copy()
    
    def broadcast_to_subscribers(self, event_type: str, data: Any, source: str = "dashan"):
        subscribers = self.get_subscribed_clients(event_type)
        
        if subscribers:
            self.broadcaster.broadcast(event_type, data, source)
            logger.debug(f"Broadcasted {event_type} to {len(subscribers)} subscribers")
        else:
            self.broadcaster.broadcast(event_type, data, source)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "connected_clients": len(self._client_info),
            "subscriptions": {
                event: len(clients)
                for event, clients in self._subscriptions.items()
            },
            "broadcaster_stats": self.broadcaster.get_stats()
        }

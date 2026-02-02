import threading
import logging
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from enum import IntEnum
from queue import Queue, Empty
import time

logger = logging.getLogger(__name__)


class EventType(IntEnum):
    WAKE_WORD_DETECTED = 1
    SPEECH_RECOGNIZED = 2
    RESPONSE_GENERATED = 3
    SPEECH_SYNTHESIZED = 4
    STATE_CHANGED = 5
    EXPRESSION_CHANGED = 6
    SERVO_MOVED = 7
    SENSOR_DATA_RECEIVED = 8
    FACE_DETECTED = 9
    GAZE_UPDATED = 10
    ERROR_OCCURRED = 11
    IDLE_TIMEOUT = 12
    CONNECTION_LOST = 13
    CONNECTION_RESTORED = 14


@dataclass
class Event:
    type: EventType
    data: Any = None
    timestamp: float = 0.0
    source: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class EventCallback:
    def __init__(self, callback: Callable[[Event], None], event_type: Optional[EventType] = None):
        self.callback = callback
        self.event_type = event_type
        self.id = id(callback)
    
    def __call__(self, event: Event):
        if self.event_type is None or self.event_type == event.type:
            try:
                self.callback(event)
            except Exception as e:
                logger.error(f"Error in event callback {self.id}: {e}")


class EventBus:
    _instance: Optional['EventBus'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._subscribers: Dict[EventType, List[EventCallback]] = {}
        self._all_subscribers: List[EventCallback] = []
        self._event_queue: Queue = Queue(maxsize=1000)
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._history: List[Event] = []
        self._max_history = 100
        self._initialized = True
        
        logger.info("EventBus initialized")
    
    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> int:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        cb = EventCallback(callback, event_type)
        self._subscribers[event_type].append(cb)
        
        logger.debug(f"Subscribed to {event_type.name}: callback {cb.id}")
        return cb.id
    
    def subscribe_all(self, callback: Callable[[Event], None]) -> int:
        cb = EventCallback(callback, None)
        self._all_subscribers.append(cb)
        
        logger.debug(f"Subscribed to all events: callback {cb.id}")
        return cb.id
    
    def unsubscribe(self, event_type: EventType, callback_id: int) -> bool:
        if event_type not in self._subscribers:
            return False
        
        for i, cb in enumerate(self._subscribers[event_type]):
            if cb.id == callback_id:
                self._subscribers[event_type].pop(i)
                logger.debug(f"Unsubscribed from {event_type.name}: callback {callback_id}")
                return True
        
        return False
    
    def unsubscribe_all(self, callback_id: int) -> bool:
        for i, cb in enumerate(self._all_subscribers):
            if cb.id == callback_id:
                self._all_subscribers.pop(i)
                logger.debug(f"Unsubscribed from all events: callback {callback_id}")
                return True
        
        return False
    
    def publish(self, event_type: EventType, data: Any = None, source: Optional[str] = None) -> bool:
        event = Event(type=event_type, data=data, source=source)
        
        try:
            self._event_queue.put(event, block=False)
            logger.debug(f"Event published: {event_type.name}")
            return True
        except Exception:
            logger.warning(f"Event queue full, dropping event: {event_type.name}")
            return False
    
    def publish_sync(self, event_type: EventType, data: Any = None, source: Optional[str] = None):
        event = Event(type=event_type, data=data, source=source)
        self._dispatch_event(event)
    
    def _dispatch_event(self, event: Event):
        self._add_to_history(event)
        
        subscribers = self._subscribers.get(event.type, [])
        all_subscribers = list(self._all_subscribers)
        
        for cb in subscribers + all_subscribers:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Error dispatching event to callback {cb.id}: {e}")
    
    def _add_to_history(self, event: Event):
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 10) -> List[Event]:
        if event_type is None:
            return self._history[-limit:]
        
        filtered = [e for e in self._history if e.type == event_type]
        return filtered[-limit:]
    
    def start(self):
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="EventBus-Worker")
        self._worker_thread.start()
        
        logger.info("EventBus worker started")
    
    def stop(self):
        if not self._running:
            return
        
        self._running = False
        
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)
        
        logger.info("EventBus worker stopped")
    
    def _worker_loop(self):
        while self._running:
            try:
                event = self._event_queue.get(timeout=0.1)
                self._dispatch_event(event)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error in event worker: {e}")
    
    def clear_queue(self):
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except Empty:
                break
    
    def clear_history(self):
        self._history.clear()
    
    def get_queue_size(self) -> int:
        return self._event_queue.qsize()
    
    def get_subscriber_count(self, event_type: Optional[EventType] = None) -> int:
        if event_type is None:
            return sum(len(subs) for subs in self._subscribers.values()) + len(self._all_subscribers)
        
        return len(self._subscribers.get(event_type, []))
    
    def wait_for_event(self, event_type: EventType, timeout: float = 5.0, condition: Optional[Callable[[Event], bool]] = None) -> Optional[Event]:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            history = self.get_history(event_type, limit=10)
            for event in reversed(history):
                if event.timestamp >= start_time:
                    if condition is None or condition(event):
                        return event
            
            time.sleep(0.05)
        
        return None
    
    @staticmethod
    def get_instance() -> 'EventBus':
        if EventBus._instance is None:
            EventBus._instance = EventBus()
        return EventBus._instance
    
    @staticmethod
    def reset():
        if EventBus._instance is not None:
            EventBus._instance.stop()
            EventBus._instance = None

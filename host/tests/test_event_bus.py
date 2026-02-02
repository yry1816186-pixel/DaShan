import pytest
import time
from host.core.event_bus import EventBus, EventType, Event


@pytest.fixture
def event_bus():
    bus = EventBus()
    bus.start()
    yield bus
    bus.stop()


def test_event_bus_initialization():
    bus = EventBus()
    assert bus is not None
    assert bus.get_subscriber_count() == 0


def test_subscribe_and_publish(event_bus):
    received_events = []
    
    def callback(event):
        received_events.append(event)
    
    callback_id = event_bus.subscribe(EventType.WAKE_WORD_DETECTED, callback)
    assert callback_id > 0
    
    event_bus.publish(EventType.WAKE_WORD_DETECTED, {"test": "data"})
    
    time.sleep(0.2)
    
    assert len(received_events) == 1
    assert received_events[0].type == EventType.WAKE_WORD_DETECTED
    assert received_events[0].data == {"test": "data"}


def test_subscribe_all(event_bus):
    received_events = []
    
    def callback(event):
        received_events.append(event)
    
    callback_id = event_bus.subscribe_all(callback)
    
    event_bus.publish(EventType.WAKE_WORD_DETECTED, {"type": 1})
    event_bus.publish(EventType.SPEECH_RECOGNIZED, {"type": 2})
    
    time.sleep(0.2)
    
    assert len(received_events) == 2


def test_unsubscribe(event_bus):
    received_events = []
    
    def callback(event):
        received_events.append(event)
    
    callback_id = event_bus.subscribe(EventType.WAKE_WORD_DETECTED, callback)
    
    event_bus.publish(EventType.WAKE_WORD_DETECTED, {"test": 1})
    time.sleep(0.2)
    assert len(received_events) == 1
    
    result = event_bus.unsubscribe(EventType.WAKE_WORD_DETECTED, callback_id)
    assert result is True
    
    event_bus.publish(EventType.WAKE_WORD_DETECTED, {"test": 2})
    time.sleep(0.2)
    assert len(received_events) == 1


def test_event_history(event_bus):
    event_bus.publish(EventType.WAKE_WORD_DETECTED, {"data": 1})
    event_bus.publish(EventType.SPEECH_RECOGNIZED, {"data": 2})
    event_bus.publish(EventType.RESPONSE_GENERATED, {"data": 3})
    
    time.sleep(0.1)
    
    history = event_bus.get_history(limit=10)
    assert len(history) == 3
    
    wake_history = event_bus.get_history(EventType.WAKE_WORD_DETECTED)
    assert len(wake_history) >= 1
    assert wake_history[0].type == EventType.WAKE_WORD_DETECTED


def test_wait_for_event(event_bus):
    def delayed_publish():
        time.sleep(0.1)
        event_bus.publish(EventType.WAKE_WORD_DETECTED, {"test": "delayed"})
    
    import threading
    thread = threading.Thread(target=delayed_publish)
    thread.start()
    
    event = event_bus.wait_for_event(EventType.WAKE_WORD_DETECTED, timeout=1.0)
    
    thread.join()
    
    assert event is not None
    assert event.type == EventType.WAKE_WORD_DETECTED


def test_queue_size(event_bus):
    initial_size = event_bus.get_queue_size()
    
    for i in range(10):
        event_bus.publish(EventType.WAKE_WORD_DETECTED, {"num": i})
    
    size = event_bus.get_queue_size()
    assert size > initial_size


def test_sync_publish(event_bus):
    received_events = []
    
    def callback(event):
        received_events.append(event)
    
    event_bus.subscribe(EventType.WAKE_WORD_DETECTED, callback)
    event_bus.publish_sync(EventType.WAKE_WORD_DETECTED, {"sync": True})
    
    assert len(received_events) == 1
    assert received_events[0].data == {"sync": True}


def test_event_bus_reset():
    bus = EventBus.get_instance()
    bus.start()
    
    bus.subscribe(EventType.WAKE_WORD_DETECTED, lambda e: None)
    assert bus.get_subscriber_count() > 0
    
    EventBus.reset()
    
    new_bus = EventBus.get_instance()
    assert new_bus.get_subscriber_count() == 0

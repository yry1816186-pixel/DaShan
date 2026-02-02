import logging
from typing import Callable, Optional
from enum import IntEnum
from dataclasses import dataclass
from .event_bus import EventBus, EventType, Event

logger = logging.getLogger(__name__)


class State(IntEnum):
    SLEEP = 0
    WAKE = 1
    LISTEN = 2
    THINK = 3
    TALK = 4
    ERROR = 5
    CHARGING = 6
    UPDATING = 7


@dataclass
class StateTransition:
    from_state: State
    to_state: State
    timestamp: float = 0.0
    trigger: Optional[str] = None


class StateMachine:
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._current_state = State.SLEEP
        self._previous_state = State.SLEEP
        self._transition_history: list[StateTransition] = []
        self._max_history = 50
        self._state_handlers: dict[State, Callable] = {}
        self._transition_callbacks: dict[tuple[State, State], list[Callable]] = {}
        self._event_bus = event_bus or EventBus.get_instance()
        self._state_timeout: dict[State, float] = {}
        self._state_start_time: dict[State, float] = {}
        
        self._init_state_timeouts()
        logger.info(f"StateMachine initialized in {self._current_state.name}")
    
    def _init_state_timeouts(self):
        self._state_timeout = {
            State.SLEEP: float('inf'),
            State.WAKE: 2.0,
            State.LISTEN: 30.0,
            State.THINK: 10.0,
            State.TALK: float('inf'),
            State.ERROR: 5.0,
            State.CHARGING: float('inf'),
            State.UPDATING: float('inf')
        }
    
    @property
    def current_state(self) -> State:
        return self._current_state
    
    @property
    def previous_state(self) -> State:
        return self._previous_state
    
    def register_handler(self, state: State, handler: Callable[[], None]):
        self._state_handlers[state] = handler
        logger.debug(f"Handler registered for state {state.name}")
    
    def register_transition_callback(self, from_state: State, to_state: State, callback: Callable[[State, State], None]):
        key = (from_state, to_state)
        if key not in self._transition_callbacks:
            self._transition_callbacks[key] = []
        self._transition_callbacks[key].append(callback)
        logger.debug(f"Transition callback registered: {from_state.name} -> {to_state.name}")
    
    def transition_to(self, new_state: State, trigger: Optional[str] = None) -> bool:
        if not self._can_transition(new_state):
            logger.warning(f"Invalid transition: {self._current_state.name} -> {new_state.name}")
            return False
        
        if new_state == self._current_state:
            logger.debug(f"Already in state {new_state.name}")
            return True
        
        logger.info(f"State transition: {self._current_state.name} -> {new_state.name}")
        
        transition = StateTransition(
            from_state=self._current_state,
            to_state=new_state,
            trigger=trigger
        )
        
        self._previous_state = self._current_state
        self._current_state = new_state
        
        self._record_transition(transition)
        self._execute_exit_handlers()
        self._execute_transition_callbacks(transition)
        self._execute_entry_handlers()
        self._publish_state_change(transition)
        
        return True
    
    def _can_transition(self, new_state: State) -> bool:
        valid_transitions = {
            State.SLEEP: [State.WAKE, State.CHARGING, State.UPDATING],
            State.WAKE: [State.LISTEN, State.SLEEP],
            State.LISTEN: [State.THINK, State.SLEEP],
            State.THINK: [State.TALK, State.SLEEP],
            State.TALK: [State.LISTEN, State.SLEEP],
            State.ERROR: [State.SLEEP, State.WAKE],
            State.CHARGING: [State.SLEEP],
            State.UPDATING: [State.SLEEP]
        }
        
        return new_state in valid_transitions.get(self._current_state, [])
    
    def _record_transition(self, transition: StateTransition):
        transition.timestamp = self._event_bus.get_history()[0].timestamp if self._event_bus.get_history() else 0
        self._transition_history.append(transition)
        
        if len(self._transition_history) > self._max_history:
            self._transition_history.pop(0)
    
    def _execute_exit_handlers(self):
        handler = self._state_handlers.get(f"exit_{self._previous_state.name}")
        if handler:
            try:
                handler()
            except Exception as e:
                logger.error(f"Error in exit handler: {e}")
    
    def _execute_entry_handlers(self):
        self._state_start_time[self._current_state] = self._event_bus.get_history()[0].timestamp if self._event_bus.get_history() else 0
        handler = self._state_handlers.get(f"enter_{self._current_state.name}")
        if handler:
            try:
                handler()
            except Exception as e:
                logger.error(f"Error in entry handler: {e}")
    
    def _execute_transition_callbacks(self, transition: StateTransition):
        key = (transition.from_state, transition.to_state)
        callbacks = self._transition_callbacks.get(key, [])
        
        for callback in callbacks:
            try:
                callback(transition.from_state, transition.to_state)
            except Exception as e:
                logger.error(f"Error in transition callback: {e}")
    
    def _publish_state_change(self, transition: StateTransition):
        self._event_bus.publish(EventType.STATE_CHANGED, {
            'from_state': transition.from_state,
            'to_state': transition.to_state,
            'trigger': transition.trigger
        }, source='StateMachine')
    
    def check_timeouts(self) -> Optional[State]:
        if self._current_state == State.SLEEP:
            return None
        
        timeout = self._state_timeout.get(self._current_state)
        if timeout == float('inf'):
            return None
        
        elapsed = self._get_state_elapsed_time()
        
        if elapsed >= timeout:
            logger.warning(f"State {self._current_state.name} timeout after {elapsed:.1f}s")
            
            timeout_transitions = {
                State.WAKE: State.LISTEN,
                State.LISTEN: State.SLEEP,
                State.THINK: State.SLEEP,
                State.ERROR: State.SLEEP
            }
            
            return timeout_transitions.get(self._current_state)
        
        return None
    
    def _get_state_elapsed_time(self) -> float:
        start_time = self._state_start_time.get(self._current_state, 0)
        return self._event_bus.get_history()[0].timestamp - start_time if self._event_bus.get_history() else 0
    
    def reset(self):
        self._current_state = State.SLEEP
        self._previous_state = State.SLEEP
        self._transition_history.clear()
        self._state_start_time.clear()
        logger.info("StateMachine reset to SLEEP")
    
    def get_transition_history(self, limit: int = 10) -> list[StateTransition]:
        return self._transition_history[-limit:]
    
    def get_state_info(self) -> dict:
        return {
            'current_state': self._current_state.name,
            'previous_state': self._previous_state.name,
            'elapsed_time': self._get_state_elapsed_time(),
            'timeout': self._state_timeout.get(self._current_state),
            'transitions_count': len(self._transition_history)
        }

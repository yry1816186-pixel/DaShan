import time
import random
import threading
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import IntEnum
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Expression(IntEnum):
    SLEEP = 0x00
    WAKE = 0x01
    LISTEN = 0x02
    THINK = 0x03
    TALK = 0x04
    HAPPY = 0x05
    SAD = 0x06
    SURPRISED = 0x07
    CONFUSED = 0x08
    CURIOUS = 0x09
    SHY = 0x0A
    ANGRY = 0x0C
    LOVE = 0x0C
    TIRED = 0x0D
    EXCITED = 0x0E
    BLANK = 0x0F


@dataclass
class Keyframe:
    expression: int
    brightness: int
    servo_h: int
    servo_v: int
    duration: float


@dataclass
class Animation:
    name: str
    keyframes: List[Keyframe]
    loop: bool = False


class AnimationEngine:
    def __init__(self):
        self.animations: Dict[str, Animation] = {}
        self.current_animation: Optional[Animation] = None
        self.current_keyframe_index = 0
        self.start_time = 0.0
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[callable] = None
        self._stop_event = threading.Event()
        self._init_animations()

    def _init_animations(self):
        self.animations["blink"] = self._create_blink_animation()
        self.animations["nod"] = self._create_nod_animation()
        self.animations["shake"] = self._create_shake_animation()
        self.animations["tilt"] = self._create_tilt_animation()
        self.animations["look_left"] = self._create_look_left_animation()
        self.animations["look_right"] = self._create_look_right_animation()
        self.animations["surprised"] = self._create_surprised_animation()
        self.animations["happy"] = self._create_happy_animation()
        self.animations["shy"] = self._create_shy_animation()
        self.animations["think"] = self._create_think_animation()

    def _create_blink_animation(self) -> Animation:
        return Animation(
            name="blink",
            keyframes=[
                Keyframe(Expression.BLANK, 255, 90, 90, 0.1),
                Keyframe(Expression.SLEEP, 255, 90, 90, 0.1),
                Keyframe(Expression.BLANK, 255, 90, 90, 0.1),
            ]
        )

    def _create_nod_animation(self) -> Animation:
        return Animation(
            name="nod",
            keyframes=[
                Keyframe(Expression.LISTEN, 255, 90, 80, 0.2),
                Keyframe(Expression.LISTEN, 255, 90, 100, 0.2),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.2),
            ]
        )

    def _create_shake_animation(self) -> Animation:
        return Animation(
            name="shake",
            keyframes=[
                Keyframe(Expression.CONFUSED, 255, 70, 90, 0.2),
                Keyframe(Expression.CONFUSED, 255, 110, 90, 0.2),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.2),
            ]
        )

    def _create_tilt_animation(self) -> Animation:
        return Animation(
            name="tilt",
            keyframes=[
                Keyframe(Expression.CURIOUS, 255, 90, 85, 0.3),
                Keyframe(Expression.CURIOUS, 255, 90, 85, 0.5),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.3),
            ]
        )

    def _create_look_left_animation(self) -> Animation:
        return Animation(
            name="look_left",
            keyframes=[
                Keyframe(Expression.LISTEN, 255, 70, 90, 0.3),
                Keyframe(Expression.LISTEN, 255, 70, 90, 0.5),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.3),
            ]
        )

    def _create_look_right_animation(self) -> Animation:
        return Animation(
            name="look_right",
            keyframes=[
                Keyframe(Expression.LISTEN, 255, 110, 90, 0.3),
                Keyframe(Expression.LISTEN, 255, 110, 90, 0.5),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.3),
            ]
        )

    def _create_surprised_animation(self) -> Animation:
        return Animation(
            name="surprised",
            keyframes=[
                Keyframe(Expression.SURPRISED, 255, 90, 80, 0.2),
                Keyframe(Expression.SURPRISED, 255, 90, 80, 0.5),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.3),
            ]
        )

    def _create_happy_animation(self) -> Animation:
        return Animation(
            name="happy",
            keyframes=[
                Keyframe(Expression.HAPPY, 255, 90, 90, 0.3),
                Keyframe(Expression.HAPPY, 255, 90, 90, 0.5),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.3),
            ]
        )

    def _create_shy_animation(self) -> Animation:
        return Animation(
            name="shy",
            keyframes=[
                Keyframe(Expression.SHY, 200, 90, 95, 0.5),
                Keyframe(Expression.SHY, 200, 90, 95, 0.3),
                Keyframe(Expression.LISTEN, 255, 90, 90, 0.3),
            ]
        )

    def _create_think_animation(self) -> Animation:
        return Animation(
            name="think",
            keyframes=[
                Keyframe(Expression.THINK, 255, 85, 85, 0.5),
                Keyframe(Expression.THINK, 255, 95, 95, 0.5),
                Keyframe(Expression.THINK, 255, 85, 85, 0.5),
            ]
        )

    def set_callback(self, callback: callable):
        self._callback = callback

    def play(self, animation_name: str):
        if animation_name not in self.animations:
            logger.warning(f"Animation not found: {animation_name}")
            return
        
        self.current_animation = self.animations[animation_name]
        self.current_keyframe_index = 0
        self.start_time = time.time()
        
        if not self.running:
            self.running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._animation_loop, daemon=True)
            self._thread.start()
        
        logger.debug(f"Playing animation: {animation_name}")

    def _animation_loop(self):
        while self.running and not self._stop_event.is_set():
            if self.current_animation is None:
                time.sleep(0.01)
                continue
            
            elapsed = time.time() - self.start_time
            
            if elapsed >= self.current_animation.keyframes[self.current_keyframe_index].duration:
                self._apply_keyframe(self.current_animation.keyframes[self.current_keyframe_index])
                self.current_keyframe_index += 1
                
                if self.current_keyframe_index >= len(self.current_animation.keyframes):
                    if self.current_animation.loop:
                        self.current_keyframe_index = 0
                        self.start_time = time.time()
                    else:
                        self.current_animation = None
                        self.current_keyframe_index = 0
            
            time.sleep(0.01)

    def _apply_keyframe(self, keyframe: Keyframe):
        if self._callback:
            self._callback(
                expression=keyframe.expression,
                brightness=keyframe.brightness,
                servo_h=keyframe.servo_h,
                servo_v=keyframe.servo_v
            )

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def is_playing(self) -> bool:
        return self.current_animation is not None

    def add_animation(self, animation: Animation):
        self.animations[animation.name] = animation
        logger.debug(f"Added animation: {animation.name}")

    def remove_animation(self, animation_name: str):
        if animation_name in self.animations:
            del self.animations[animation_name]
            logger.debug(f"Removed animation: {animation_name}")


class ExpressionMixer:
    def __init__(self):
        self.base_expression = Expression.BLANK
        self.overlay_expression: Optional[Expression] = None
        self.overlay_intensity = 0.0
        self.blink_timer = 0.0
        self.next_blink_interval = self._random_blink_interval()

    def _random_blink_interval(self) -> float:
        return random.uniform(2.0, 5.0)

    def update(self, dt: float) -> Tuple[int, int, int, int]:
        self.blink_timer += dt
        
        if self.blink_timer >= self.next_blink_interval:
            self.blink_timer = 0.0
            self.next_blink_interval = self._random_blink_interval()
            return Expression.SLEEP, 255, 90, 90
        
        if self.overlay_expression is not None:
            return self.overlay_expression, 255, 90, 90
        
        return self.base_expression, 255, 90, 90

    def set_base_expression(self, expression: Expression):
        self.base_expression = expression

    def set_overlay(self, expression: Expression, intensity: float = 1.0):
        self.overlay_expression = expression
        self.overlay_intensity = intensity

    def clear_overlay(self):
        self.overlay_expression = None
        self.overlay_intensity = 0.0


class RandomBehavior:
    def __init__(self):
        self.behaviors = []
        self._last_behavior_time = 0.0
        self._min_interval = 10.0
        self._max_interval = 30.0

    def add_behavior(self, name: str, weight: float = 1.0, condition: Optional[callable] = None):
        self.behaviors.append({
            "name": name,
            "weight": weight,
            "condition": condition
        })

    def update(self, current_time: float) -> Optional[str]:
        if current_time - self._last_behavior_time < self._min_interval:
            return None
        
        if random.random() < 0.01:
            self._last_behavior_time = current_time
            self._min_interval = random.uniform(self._min_interval, self._max_interval)
            
            available = [b for b in self.behaviors if b["condition"] is None or b["condition"]()]
            
            if available:
                weights = [b["weight"] for b in available]
                total = sum(weights)
                rand = random.uniform(0, total)
                
                for behavior, weight in zip(available, weights):
                    rand -= weight
                    if rand <= 0:
                        return behavior["name"]
        
        return None


if __name__ == "__main__":
    import sys
    
    def animation_callback(expression, brightness, servo_h, servo_v):
        print(f"Expression: {expression}, Brightness: {brightness}, "
              f"Servo H: {servo_h}, Servo V: {servo_v}")
    
    engine = AnimationEngine()
    engine.set_callback(animation_callback)
    
    mixer = ExpressionMixer()
    mixer.set_base_expression(Expression.LISTEN)
    
    print("Animation Engine Test")
    print("Available animations:", list(engine.animations.keys()))
    
    try:
        while True:
            cmd = input("\nEnter animation name (or 'quit'): ").strip().lower()
            
            if cmd == "quit":
                break
            
            if cmd in engine.animations:
                engine.play(cmd)
            else:
                print(f"Unknown animation: {cmd}")
                print(f"Available: {', '.join(engine.animations.keys())}")
    
    except KeyboardInterrupt:
        pass
    
    engine.stop()

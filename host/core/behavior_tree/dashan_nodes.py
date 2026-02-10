import logging
from typing import Optional, Dict, Any, List
from .behavior_tree import (
    ActionNode, ConditionNode, SequenceNode, SelectorNode,
    NodeContext, NodeStatus, ParallelNode
)

logger = logging.getLogger(__name__)


class WakeUpBehavior(SequenceNode):
    def __init__(
        self,
        name: str = "WakeUp",
        protocol_client = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        
        nodes = [
            LogAction("LogWake", "Waking up DaShan...", level="info"),
            ActionNode("SetStateWake", self._set_wake_state),
            WaitAction("WakeDelay", 0.5),
            ActionNode("PlayWakeAnim", self._play_wake_animation)
        ]
        
        super().__init__(name, nodes, **kwargs)
    
    def _set_wake_state(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_state("WAKE")
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to set wake state: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _play_wake_animation(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(1, brightness=200)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to play wake animation: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class SleepBehavior(SequenceNode):
    def __init__(
        self,
        name: str = "Sleep",
        protocol_client = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        
        nodes = [
            LogAction("LogSleep", "DaShan going to sleep...", level="info"),
            ActionNode("PlaySleepAnim", self._play_sleep_animation),
            WaitAction("SleepDelay", 1.0),
            ActionNode("SetStateSleep", self._set_sleep_state)
        ]
        
        super().__init__(name, nodes, **kwargs)
    
    def _play_sleep_animation(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(0, brightness=50)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to play sleep animation: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _set_sleep_state(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_state("SLEEP")
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to set sleep state: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class ListenBehavior(SequenceNode):
    def __init__(
        self,
        name: str = "Listen",
        protocol_client = None,
        voice_manager = None,
        timeout: float = 10.0,
        **kwargs
    ):
        self.protocol_client = protocol_client
        self.voice_manager = voice_manager
        self.timeout = timeout
        
        nodes = [
            ActionNode("SetListenState", self._set_listen_state),
            ActionNode("StartListening", self._start_listening),
            WaitAction("ListenWait", duration_key="listen_timeout"),
            ActionNode("ProcessInput", self._process_input),
            ActionNode("StopListening", self._stop_listening)
        ]
        
        super().__init__(name, nodes, **kwargs)
    
    def _set_listen_state(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(2, brightness=255)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to set listen state: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _start_listening(self, ctx: NodeContext) -> NodeStatus:
        if self.voice_manager:
            try:
                self.voice_manager.start_listening()
                ctx.set("listen_start_time", time.time())
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to start listening: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _process_input(self, ctx: NodeContext) -> NodeStatus:
        if self.voice_manager:
            try:
                text = self.voice_manager.get_recognized_text()
                
                if text:
                    ctx.set_var("user_input", text)
                    ctx.set("has_input", True)
                    return NodeStatus.SUCCESS
                else:
                    ctx.set("has_input", False)
                    return NodeStatus.FAILURE
            except Exception as e:
                logger.error(f"Failed to process input: {e}")
                return NodeStatus.FAILURE
        
        elapsed = time.time() - ctx.get("listen_start_time", time.time())
        if elapsed >= self.timeout:
            return NodeStatus.FAILURE
        
        return NodeStatus.RUNNING
    
    def _stop_listening(self, ctx: NodeContext) -> NodeStatus:
        if self.voice_manager:
            try:
                self.voice_manager.stop_listening()
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to stop listening: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class ThinkBehavior(SequenceNode):
    def __init__(
        self,
        name: str = "Think",
        protocol_client = None,
        agent = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        self.agent = agent
        
        nodes = [
            ActionNode("SetThinkState", self._set_think_state),
            ActionNode("ProcessWithAgent", self._process_with_agent),
            ActionNode("DisplayThinking", self._display_thinking)
        ]
        
        super().__init__(name, nodes, **kwargs)
    
    def _set_think_state(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(3, brightness=200)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to set think state: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _process_with_agent(self, ctx: NodeContext) -> NodeStatus:
        user_input = ctx.get_var("user_input")
        
        if not user_input:
            return NodeStatus.FAILURE
        
        if self.agent:
            try:
                import asyncio
                
                result = asyncio.run(self.agent.process(user_input))
                
                if result.get("success"):
                    ctx.set_var("agent_response", result.get("output", ""))
                    return NodeStatus.SUCCESS
                else:
                    ctx.set_var("agent_error", result.get("error", "Unknown error"))
                    return NodeStatus.FAILURE
            except Exception as e:
                logger.error(f"Agent processing failed: {e}")
                return NodeStatus.FAILURE
        
        return NodeStatus.FAILURE
    
    def _display_thinking(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.play_animation("thinking")
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to display thinking: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class RespondBehavior(SequenceNode):
    def __init__(
        self,
        name: str = "Respond",
        protocol_client = None,
        tts_engine = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        self.tts_engine = tts_engine
        
        nodes = [
            ActionNode("SetTalkState", self._set_talk_state),
            ActionNode("SynthesizeSpeech", self._synthesize_speech),
            ActionNode("PlayAudio", self._play_audio),
            ActionNode("DisplayResponse", self._display_response),
            WaitAction("ResponseWait", duration_key="response_duration")
        ]
        
        super().__init__(name, nodes, **kwargs)
    
    def _set_talk_state(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(4, brightness=255)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to set talk state: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _synthesize_speech(self, ctx: NodeContext) -> NodeStatus:
        response = ctx.get_var("agent_response")
        
        if not response:
            return NodeStatus.FAILURE
        
        if self.tts_engine:
            try:
                audio = self.tts_engine.synthesize(response)
                
                if audio:
                    ctx.set("audio_data", audio)
                    duration = self.tts_engine.estimate_duration(response)
                    ctx.set("response_duration", duration)
                    return NodeStatus.SUCCESS
                else:
                    return NodeStatus.FAILURE
            except Exception as e:
                logger.error(f"TTS synthesis failed: {e}")
                return NodeStatus.FAILURE
        
        return NodeStatus.FAILURE
    
    def _play_audio(self, ctx: NodeContext) -> NodeStatus:
        audio_data = ctx.get("audio_data")
        
        if not audio_data or not self.protocol_client:
            return NodeStatus.FAILURE
        
        try:
            self.protocol_client.play_audio(audio_data)
            return NodeStatus.SUCCESS
        except Exception as e:
            logger.error(f"Failed to play audio: {e}")
            return NodeStatus.FAILURE
    
    def _display_response(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.play_animation("talking")
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to display response: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class ExpressEmotion(ActionNode):
    def __init__(
        self,
        name: str = "ExpressEmotion",
        protocol_client = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        
        super().__init__(name, self._express, **kwargs)
    
    def _express(self, ctx: NodeContext) -> NodeStatus:
        emotion = ctx.get_var("emotion")
        intensity = ctx.get_var("emotion_intensity", 1.0)
        
        if not emotion:
            return NodeStatus.FAILURE
        
        emotion_map = {
            "happy": (5, 255),
            "sad": (6, 150),
            "surprised": (7, 255),
            "angry": (8, 200),
            "curious": (9, 220),
            "shy": (10, 180),
            "love": (11, 230)
        }
        
        if emotion not in emotion_map:
            logger.warning(f"Unknown emotion: {emotion}")
            return NodeStatus.FAILURE
        
        expression_id, brightness = emotion_map[emotion]
        brightness = int(brightness * intensity)
        
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(
                    expression_id,
                    brightness=brightness,
                    duration=0.5
                )
                logger.info(f"Expressed emotion: {emotion} (intensity={intensity})")
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to express emotion: {e}")
                return NodeStatus.FAILURE
        
        return NodeStatus.SUCCESS


class TrackFaceBehavior(SequenceNode):
    def __init__(
        self,
        name: str = "TrackFace",
        protocol_client = None,
        face_tracker = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        self.face_tracker = face_tracker
        
        nodes = [
            ActionNode("GetFacePosition", self._get_face_position),
            ActionNode("CalculateServoAngles", self._calculate_servo_angles),
            ActionNode("MoveServos", self._move_servos)
        ]
        
        super().__init__(name, nodes, **kwargs)
    
    def _get_face_position(self, ctx: NodeContext) -> NodeStatus:
        if self.face_tracker:
            try:
                face_data = self.face_tracker.get_current_face()
                
                if face_data:
                    ctx.set("face_x", face_data.x)
                    ctx.set("face_y", face_data.y)
                    ctx.set("face_width", face_data.width)
                    ctx.set("face_height", face_data.height)
                    ctx.set("face_detected", True)
                    return NodeStatus.SUCCESS
                else:
                    ctx.set("face_detected", False)
                    return NodeStatus.FAILURE
            except Exception as e:
                logger.error(f"Face tracking failed: {e}")
                return NodeStatus.FAILURE
        
        return NodeStatus.FAILURE
    
    def _calculate_servo_angles(self, ctx: NodeContext) -> NodeStatus:
        if not ctx.get("face_detected"):
            return NodeStatus.FAILURE
        
        face_x = ctx.get("face_x", 0)
        face_y = ctx.get("face_y", 0)
        face_width = ctx.get("face_width", 640)
        face_height = ctx.get("face_height", 480)
        
        center_x = face_width / 2
        center_y = face_height / 2
        
        diff_x = (face_x - center_x) / center_x
        diff_y = (face_y - center_y) / center_y
        
        servo_h_angle = int(diff_x * 45)
        servo_v_angle = int(diff_y * 30)
        
        servo_h_angle = max(-45, min(45, servo_h_angle))
        servo_v_angle = max(-30, min(30, servo_v_angle))
        
        ctx.set("servo_h_angle", 90 + servo_h_angle)
        ctx.set("servo_v_angle", 90 + servo_v_angle)
        
        return NodeStatus.SUCCESS
    
    def _move_servos(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                servo_h = ctx.get("servo_h_angle", 90)
                servo_v = ctx.get("servo_v_angle", 90)
                
                self.protocol_client.set_servo(1, servo_h)
                self.protocol_client.set_servo(2, servo_v)
                
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to move servos: {e}")
                return NodeStatus.FAILURE
        
        return NodeStatus.SUCCESS


class IdleBehavior(SelectorNode):
    def __init__(
        self,
        name: str = "Idle",
        protocol_client = None,
        **kwargs
    ):
        self.protocol_client = protocol_client
        
        behaviors = [
            SequenceNode("IdleAnimation", [
                ActionNode("PlayIdleAnim", self._play_idle_animation),
                WaitAction("IdleWait", 3.0)
            ], priority=1),
            
            SequenceNode("BlinkBehavior", [
                ActionNode("Blink", self._blink),
                WaitAction("BlinkWait", 2.0)
            ], priority=2),
            
            SequenceNode("LookAround", [
                ActionNode("LookLeft", lambda ctx: self._look(ctx, -15, 0)),
                WaitAction("LookLeftWait", 1.5),
                ActionNode("LookRight", lambda ctx: self._look(ctx, 15, 0)),
                WaitAction("LookRightWait", 1.5),
                ActionNode("LookCenter", lambda ctx: self._look(ctx, 0, 0))
            ], priority=3)
        ]
        
        super().__init__(name, behaviors, use_priority=True, **kwargs)
    
    def _play_idle_animation(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                import random
                expression = random.choice([1, 5, 9])
                brightness = random.randint(150, 200)
                self.protocol_client.set_expression(expression, brightness=brightness)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to play idle animation: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _blink(self, ctx: NodeContext) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_expression(0, brightness=100)
                import time
                time.sleep(0.1)
                self.protocol_client.set_expression(1, brightness=200)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to blink: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS
    
    def _look(self, ctx: NodeContext, h_angle: int, v_angle: int) -> NodeStatus:
        if self.protocol_client:
            try:
                self.protocol_client.set_servo(1, 90 + h_angle)
                self.protocol_client.set_servo(2, 90 + v_angle)
                return NodeStatus.SUCCESS
            except Exception as e:
                logger.error(f"Failed to look: {e}")
                return NodeStatus.FAILURE
        return NodeStatus.SUCCESS


class CheckWakeWord(ConditionNode):
    def __init__(
        self,
        name: str = "CheckWakeWord",
        wake_word_detector = None,
        **kwargs
    ):
        self.wake_word_detector = wake_word_detector
        
        def check_wake(ctx: NodeContext) -> bool:
            if self.wake_word_detector:
                return self.wake_word_detector.is_detected()
            return False
        
        super().__init__(name, check_wake, **kwargs)


class CheckProximity(ConditionNode):
    def __init__(
        self,
        name: str = "CheckProximity",
        threshold: float = 0.3,
        **kwargs
    ):
        self.threshold = threshold
        
        def check_prox(ctx: NodeContext) -> bool:
            distance = ctx.get("sensor_distance", 999.0)
            return distance < self.threshold
        
        super().__init__(name, check_prox, **kwargs)


class CheckIdleTimeout(ConditionNode):
    def __init__(
        self,
        name: str = "CheckIdleTimeout",
        timeout: float = 30.0,
        **kwargs
    ):
        self.timeout = timeout
        
        def check_timeout(ctx: NodeContext) -> bool:
            last_interaction = ctx.get("last_interaction_time", time.time())
            elapsed = time.time() - last_interaction
            return elapsed >= self.timeout
        
        super().__init__(name, check_timeout, **kwargs)


class UpdateInteractionTime(ActionNode):
    def __init__(self, name: str = "UpdateInteractionTime", **kwargs):
        def update_time(ctx: NodeContext) -> NodeStatus:
            ctx.set("last_interaction_time", time.time())
            return NodeStatus.SUCCESS
        
        super().__init__(name, update_time, **kwargs)


import time
from .leaf_nodes import LogAction, WaitAction, ActionNode, ConditionNode
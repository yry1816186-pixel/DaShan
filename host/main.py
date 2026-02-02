import os
import sys
import time
import logging
import threading
from typing import Optional
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.protocol.serial_com import SerialProtocol, STATE, CMD
from modules.voice.wake_word import WakeWordDetector, WakeWordConfig
from modules.voice.stt import SpeechToText, STTConfig, WhisperModelSize
from modules.voice.tts import TextToSpeech, TTSConfig
from modules.dialogue.llm import GLM4Client, LLMConfig, EmotionAnalyzer
from modules.dialogue.memory import MemoryManager
from modules.behavior.animation import AnimationEngine, Expression
from modules.behavior.emotion import EmotionPropagator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MainConfig:
    serial_port: Optional[str] = None
    serial_baudrate: int = 115200
    glm_api_key: Optional[str] = None
    idle_timeout: float = 30.0
    
    def __post_init__(self):
        if not self.glm_api_key:
            self.glm_api_key = os.getenv("GLM_API_KEY")


class DashanController:
    def __init__(self, config: MainConfig):
        self.config = config
        self.running = False
        self.current_state = STATE.SLEEP
        self.last_interaction_time = time.time()
        
        self.protocol = SerialProtocol(baudrate=config.serial_baudrate)
        self.wake_word_detector = WakeWordDetector()
        self.stt = SpeechToText()
        self.tts = TextToSpeech()
        self.llm_client: Optional[GLM4Client] = None
        self.memory_manager = MemoryManager()
        self.animation_engine = AnimationEngine()
        self.emotion_propagator = EmotionPropagator()
        self.emotion_analyzer = EmotionAnalyzer()
        
        self._stop_event = threading.Event()
        self._main_thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        logger.info("Initializing DaShan...")
        
        if not self.config.glm_api_key:
            logger.error("GLM API key not set")
            return False
        
        if not self._connect_serial():
            return False
        
        if not self._init_voice():
            return False
        
        self._init_llm()
        self._init_animation()
        self._register_callbacks()
        
        logger.info("DaShan initialized successfully")
        return True

    def _connect_serial(self) -> bool:
        if self.config.serial_port:
            return self.protocol.connect(self.config.serial_port)
        
        ports = self.protocol.list_ports()
        if not ports:
            logger.error("No serial ports available")
            return False
        
        logger.info(f"Available ports: {ports}")
        for port in ports:
            logger.info(f"Trying to connect to {port}...")
            if self.protocol.connect(port):
                logger.info(f"Connected to {port}")
                return True
        
        logger.error("Failed to connect to any serial port")
        return False

    def _init_voice(self) -> bool:
        if not self.stt.load_model(WhisperModelSize.BASE):
            logger.error("Failed to load Whisper model")
            return False
        
        if not self.stt.start_listening():
            logger.error("Failed to start STT")
            return False
        
        self.wake_word_detector.set_callback(self._on_wake_word)
        
        if not self.wake_word_detector.start():
            logger.error("Failed to start wake word detector")
            return False
        
        return True

    def _init_llm(self):
        config = LLMConfig(api_key=self.config.glm_api_key)
        self.llm_client = GLM4Client(config)
        logger.info("LLM client initialized")

    def _init_animation(self):
        self.animation_engine.set_callback(self._on_animation_keyframe)
        logger.info("Animation engine initialized")

    def _register_callbacks(self):
        self.protocol.register_callback(CMD.SENSOR_DATA, self._on_sensor_data)

    def start(self):
        if not self.initialize():
            logger.error("Failed to initialize DaShan")
            return False
        
        self.running = True
        self._stop_event.clear()
        
        self._main_thread = threading.Thread(target=self._main_loop, daemon=True)
        self._main_thread.start()
        
        logger.info("DaShan started")
        return True

    def stop(self):
        self.running = False
        self._stop_event.set()
        
        if self._main_thread:
            self._main_thread.join(timeout=2.0)
        
        self.wake_word_detector.stop()
        self.stt.stop_listening()
        self.animation_engine.stop()
        self.protocol.disconnect()
        
        logger.info("DaShan stopped")

    def _main_loop(self):
        while self.running and not self._stop_event.is_set():
            self._check_idle_timeout()
            self._update_emotion()
            time.sleep(0.1)

    def _check_idle_timeout(self):
        elapsed = time.time() - self.last_interaction_time
        
        if elapsed >= self.config.idle_timeout:
            if self.current_state != STATE.SLEEP:
                logger.info("Idle timeout, going to sleep")
                self.transition_to_state(STATE.SLEEP)

    def _update_emotion(self):
        emotion, expression_id, intensity = self.emotion_propagator.update()
        self.emotion_propagator.decay()

    def transition_to_state(self, new_state: STATE):
        if new_state == self.current_state:
            return
        
        logger.info(f"Transitioning from {self.current_state} to {new_state}")
        self.current_state = new_state
        
        if new_state == STATE.SLEEP:
            self.protocol.set_expression(Expression.SLEEP, brightness=100, duration=0)
            self.animation_engine.play("shy")
        elif new_state == STATE.WAKE:
            self.protocol.set_expression(Expression.WAKE, brightness=255, duration=0)
            self.animation_engine.play("surprised")
        elif new_state == STATE.LISTEN:
            self.protocol.set_expression(Expression.LISTEN, brightness=255, duration=0)
            self.animation_engine.play("tilt")
        elif new_state == STATE.THINK:
            self.protocol.set_expression(Expression.THINK, brightness=255, duration=0)
            self.animation_engine.play("think")
        elif new_state == STATE.TALK:
            self.protocol.set_expression(Expression.TALK, brightness=255, duration=0)
        
        self.protocol.set_state(new_state)

    def _on_wake_word(self):
        logger.info("Wake word detected!")
        self.last_interaction_time = time.time()
        self.transition_to_state(STATE.WAKE)
        
        time.sleep(1.0)
        
        self.transition_to_state(STATE.LISTEN)
        
        text = self._listen_for_speech()
        
        if text:
            self._process_user_input(text)
        else:
            logger.warning("No speech detected")
            self.transition_to_state(STATE.SLEEP)

    def _listen_for_speech(self, timeout: float = 10.0) -> Optional[str]:
        logger.info("Listening for speech...")
        self.stt.start_recording()
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.1)
        
        text = self.stt.stop_recording()
        
        if text:
            logger.info(f"Recognized: {text}")
            self.memory_manager.add_memory(text, "user_input")
        
        return text

    def _process_user_input(self, text: str):
        self.last_interaction_time = time.time()
        
        expression_id = self.emotion_propagator.process_text(text)
        if expression_id:
            self.protocol.set_expression(expression_id)
        
        self.transition_to_state(STATE.THINK)
        
        context = self.memory_manager.get_context_for_llm()
        full_prompt = f"{context}\n\n用户说: {text}"
        
        response = self._generate_response(full_prompt)
        
        if response:
            self.memory_manager.add_memory(response, "assistant_response", importance=1.5)
            self.memory_manager.increment_interaction()
            
            self.transition_to_state(STATE.TALK)
            self._speak(response)
        else:
            logger.error("Failed to generate response")
            self.transition_to_state(STATE.SLEEP)

    def _generate_response(self, prompt: str) -> Optional[str]:
        if not self.llm_client:
            logger.error("LLM client not initialized")
            return None
        
        try:
            response = self.llm_client.chat(prompt)
            
            if response:
                logger.info(f"Generated response: {response[:50]}...")
                return response
            else:
                logger.warning("Empty response from LLM")
                return None
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return None

    def _speak(self, text: str):
        logger.info(f"Speaking: {text[:50]}...")
        
        audio_data = self.tts.synthesize(text)
        
        if audio_data:
            self.protocol.play_audio(audio_data)
            
            duration = self.tts.estimate_duration(text)
            time.sleep(duration)
            
            self.last_interaction_time = time.time()
        else:
            logger.error("Failed to synthesize speech")

    def _on_animation_keyframe(self, expression: int, brightness: int, servo_h: int, servo_v: int):
        self.protocol.set_expression(expression, brightness, 0)
        self.protocol.set_servo(1, servo_h)
        self.protocol.set_servo(2, servo_v)

    def _on_sensor_data(self, sensor_data):
        distance = sensor_data.distance
        proximity = sensor_data.proximity
        light = sensor_data.light
        
        logger.debug(f"Sensor data: distance={distance}, proximity={proximity}, light={light}")
        
        if proximity and self.current_state == STATE.SLEEP:
            logger.info("Proximity detected, waking up")
            self.transition_to_state(STATE.WAKE)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="DaShan Desktop Pet Robot")
    parser.add_argument("--port", type=str, help="Serial port (e.g., COM3 or /dev/ttyUSB0)")
    parser.add_argument("--baudrate", type=int, default=115200, help="Serial baudrate")
    parser.add_argument("--api-key", type=str, help="GLM-4 API key")
    parser.add_argument("--idle-timeout", type=float, default=30.0, help="Idle timeout in seconds")
    
    args = parser.parse_args()
    
    config = MainConfig(
        serial_port=args.port,
        serial_baudrate=args.baudrate,
        glm_api_key=args.api_key,
        idle_timeout=args.idle_timeout
    )
    
    controller = DashanController(config)
    
    try:
        if controller.start():
            logger.info("DaShan is running. Press Ctrl+C to stop.")
            
            while controller.running:
                time.sleep(1)
        else:
            logger.error("Failed to start DaShan")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        controller.stop()


if __name__ == "__main__":
    main()

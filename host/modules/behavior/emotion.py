import random
import logging
from typing import Dict, List, Optional
from enum import IntEnum
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Emotion(IntEnum):
    NEUTRAL = 0
    HAPPY = 1
    SAD = 2
    SURPRISED = 3
    ANGRY = 4
    SHY = 5
    CURIOUS = 6
    EXCITED = 7
    CONFUSED = 8
    TIRED = 9


@dataclass
class EmotionState:
    emotion: Emotion
    intensity: float
    duration: float


class EmotionDetector:
    def __init__(self):
        self.emotion_keywords = {
            Emotion.HAPPY: [
                "开心", "高兴", "棒", "太好了", "喜欢", "爱", "哈哈", "快乐",
                "赞", "优秀", "不错", "好耶", "成功", "赢了"
            ],
            Emotion.SAD: [
                "难过", "伤心", "不好", "糟糕", "失望", "哭", "不开心",
                "失败", "可惜", "遗憾", "难过"
            ],
            Emotion.SURPRISED: [
                "哇", "天哪", "真的", "竟然", "惊讶", "不敢相信",
                "天啊", "什么", "不会吧", "真的吗"
            ],
            Emotion.ANGRY: [
                "生气", "讨厌", "烦", "气死", "愤怒", "讨厌",
                "烦人", "不行", "不可以"
            ],
            Emotion.SHY: [
                "嗯", "那个", "不好意思", "害羞", "脸红",
                "唔", "嗯哼"
            ],
            Emotion.CURIOUS: [
                "好奇", "想知道", "为什么", "怎么", "什么",
                "请问", "怎么回事", "为什么"
            ],
            Emotion.EXCITED: [
                "太棒了", "激动", "兴奋", "迫不及待", "好期待",
                "太好了", "厉害", "牛"
            ],
            Emotion.CONFUSED: [
                "不懂", "不明白", "什么意思", "为什么", "困惑",
                "疑惑", "搞不懂", "不明白"
            ],
            Emotion.TIRED: [
                "累", "疲惫", "困", "想睡觉", "好累",
                "没精神", "不想动"
            ]
        }

    def detect(self, text: str) -> Emotion:
        text = text.lower()
        emotion_scores = {}
        
        for emotion, keywords in self.emotion_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text)
            if score > 0:
                emotion_scores[emotion] = score
        
        if not emotion_scores:
            return Emotion.NEUTRAL
        
        return max(emotion_scores.items(), key=lambda x: x[1])[0]

    def detect_with_intensity(self, text: str) -> tuple[Emotion, float]:
        emotion = self.detect(text)
        keywords = self.emotion_keywords.get(emotion, [])
        
        count = sum(1 for keyword in keywords if keyword in text)
        intensity = min(1.0, count * 0.3 + 0.4)
        
        return emotion, intensity


class EmotionManager:
    def __init__(self):
        self.current_emotion = Emotion.NEUTRAL
        self.current_intensity = 0.0
        self.target_emotion = Emotion.NEUTRAL
        self.target_intensity = 0.0
        self.transition_speed = 0.1
        self.emotion_history: List[EmotionState] = []
        self.max_history = 100

    def set_emotion(self, emotion: Emotion, intensity: float = 1.0):
        self.target_emotion = emotion
        self.target_intensity = max(0.0, min(1.0, intensity))
        logger.debug(f"Set emotion: {emotion} (intensity: {intensity})")

    def update(self, dt: float) -> Emotion:
        diff = self.target_intensity - self.current_intensity
        self.current_intensity += diff * self.transition_speed
        
        if abs(diff) < 0.01:
            self.current_emotion = self.target_emotion
            self.current_intensity = self.target_intensity
        
        if self.current_intensity > 0.1:
            self._record_emotion_state()
        
        return self.current_emotion

    def _record_emotion_state(self):
        state = EmotionState(
            emotion=self.current_emotion,
            intensity=self.current_intensity,
            duration=0.0
        )
        
        if self.emotion_history:
            self.emotion_history[-1].duration += 0.016
        
        self.emotion_history.append(state)
        
        if len(self.emotion_history) > self.max_history:
            self.emotion_history.pop(0)

    def get_dominant_emotion(self, time_window: float = 5.0) -> Emotion:
        if not self.emotion_history:
            return Emotion.NEUTRAL
        
        emotion_durations = {}
        
        for state in self.emotion_history:
            if state.duration > 0:
                if state.emotion not in emotion_durations:
                    emotion_durations[state.emotion] = 0.0
                emotion_durations[state.emotion] += state.duration
        
        if not emotion_durations:
            return Emotion.NEUTRAL
        
        return max(emotion_durations.items(), key=lambda x: x[1])[0]

    def get_current_intensity(self) -> float:
        return self.current_intensity

    def decay(self, decay_rate: float = 0.01):
        if self.current_intensity > 0:
            self.current_intensity -= decay_rate
            if self.current_intensity <= 0:
                self.current_intensity = 0
                self.target_emotion = Emotion.NEUTRAL
                self.target_intensity = 0

    def reset(self):
        self.current_emotion = Emotion.NEUTRAL
        self.current_intensity = 0.0
        self.target_emotion = Emotion.NEUTRAL
        self.target_intensity = 0.0


class EmotionToExpressionMapper:
    def __init__(self):
        self.mapping = {
            Emotion.NEUTRAL: 0x02,
            Emotion.HAPPY: 0x05,
            Emotion.SAD: 0x06,
            Emotion.SURPRISED: 0x07,
            Emotion.ANGRY: 0x0B,
            Emotion.SHY: 0x0A,
            Emotion.CURIOUS: 0x09,
            Emotion.EXCITED: 0x0E,
            Emotion.CONFUSED: 0x08,
            Emotion.TIRED: 0x0D
        }

    def map(self, emotion: Emotion) -> int:
        return self.mapping.get(emotion, 0x02)


class EmotionPropagator:
    def __init__(self):
        self.detector = EmotionDetector()
        self.manager = EmotionManager()
        self.mapper = EmotionToExpressionMapper()

    def process_text(self, text: str) -> Optional[int]:
        emotion, intensity = self.detector.detect_with_intensity(text)
        
        if emotion != Emotion.NEUTRAL:
            self.manager.set_emotion(emotion, intensity)
        
        expression_id = self.mapper.map(emotion)
        return expression_id

    def update(self, dt: float = 0.016) -> tuple[Emotion, int, float]:
        emotion = self.manager.update(dt)
        expression_id = self.mapper.map(emotion)
        intensity = self.manager.get_current_intensity()
        
        return emotion, expression_id, intensity

    def decay(self, decay_rate: float = 0.01):
        self.manager.decay(decay_rate)

    def reset(self):
        self.manager.reset()


if __name__ == "__main__":
    detector = EmotionDetector()
    
    test_texts = [
        "今天真开心！",
        "我不喜欢这个",
        "哇，真的吗？",
        "我好累啊",
        "这个是什么？",
        "不好意思",
        "太棒了！",
        "我不明白"
    ]
    
    print("Emotion Detection Test")
    print("-" * 50)
    
    for text in test_texts:
        emotion, intensity = detector.detect_with_intensity(text)
        print(f"Text: {text}")
        print(f"Emotion: {emotion.name}, Intensity: {intensity:.2f}")
        print()

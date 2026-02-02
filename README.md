# DaShan 桌宠机器人系统

一个高性能、可扩展的AI桌面宠物机器人，具备语音交互、人脸追踪、情感表达等特性。

## 项目概述

DaShan是一个基于"表演层+大脑层"双架构的桌宠机器人系统，采用瓦力风格的"害羞、好奇、温柔"设计理念。

### 核心特性

- 🎯 **低延迟唤醒** <200ms响应时间
- 👁️ **自然注视** 实时人脸追踪
- 😊 **情感表达** 15+表情动画
- 🧠 **AI大脑** 集成GLM-4.7大语言模型
- 🔊 **离线语音** openWakeWord + Whisper + Piper
- 📷 **视觉感知** 摄像头 + 红外距离传感器
- 🔌 **可扩展** 模块化设计，易于升级
- 💰 **低成本** 总成本 <500元

## 系统架构

```
┌─────────────────────────────────────┐
│      表演层（机器人端）               │
│  - ESP32-S3微控制器                  │
│  - WS2812B LED矩阵 8x8 (眼睛)       │
│  - SG90舵机 x2 (水平/垂直转头)      │
│  - OV2640摄像头模块                 │
│  - I2S麦克风 + 扬声器               │
│  - HC-SR04超声波传感器               │
└─────────────────────────────────────┘
              ↓ UART/USB
┌─────────────────────────────────────┐
│      大脑层（主机端）                 │
│  - openWakeWord 唤醒检测            │
│  - Whisper 语音识别                 │
│  - GLM-4.7 对话生成                 │
│  - Piper 语音合成                   │
│  - OpenCV 人脸追踪                  │
│  - 表情动画生成器                    │
│  - 长期记忆管理                      │
└─────────────────────────────────────┘
```

## 交互流程

```
1. SLEEP (休眠) 
   └─ 眼睛半闭，呼吸灯效果
   
2. 唤醒词检测
   └─ openWakeWord识别唤醒词
   
3. WAKE (唤醒)
   └─ 亮眼睛，抬头，看向用户
   
4. LISTEN (倾听)
   └─ 录音 → Whisper转文字
   
5. THINK (思考)
   └─ 歪头，瞳孔上望
   
6. TALK (说话)
   └─ GLM-4.7生成回复 → Piper合成语音 → 播放+表情动画
   
7. 30s无交互 → 回到SLEEP
```

## 快速开始

### 硬件准备

详见 [HARDWARE.md](docs/HARDWARE.md)

### 软件安装

详见 [INSTALLATION.md](docs/INSTALLATION.md)

### 运行

```bash
# 主机端
cd host
python main.py

# 机器人端 (使用ESP-IDF)
cd robot
idf.py flash monitor
```

## 项目结构

```
DaShan/
├── docs/                    # 文档
│   ├── HARDWARE.md         # 硬件清单
│   ├── INSTALLATION.md     # 安装指南
│   └── ARCHITECTURE.md     # 架构设计
├── robot/                   # 机器人端 (ESP32-S3)
│   ├── main/               # 主程序
│   │   ├── CMakeLists.txt
│   │   ├── main.c
│   │   ├── driver/         # 驱动层
│   │   ├── state_machine/  # 状态机
│   │   └── protocol/       # 通信协议
│   ├── components/         # 组件库
│   │   ├── led_matrix/
│   │   ├── servo/
│   │   ├── camera/
│   │   └── audio/
│   └── config/             # 配置文件
├── host/                    # 主机端 (Python)
│   ├── main.py             # 主程序
│   ├── modules/            # 功能模块
│   │   ├── voice/          # 语音处理
│   │   │   ├── wake_word.py
│   │   │   ├── stt.py       # 语音识别
│   │   │   └── tts.py       # 语音合成
│   │   ├── dialogue/        # 对话引擎
│   │   │   ├── llm.py       # GLM-4.7
│   │   │   ├── memory.py    # 记忆管理
│   │   │   └── prompt.py    # 提示词
│   │   ├── vision/          # 视觉模块
│   │   │   ├── face_tracker.py
│   │   │   └── camera.py
│   │   ├── behavior/        # 行为编排
│   │   │   ├── animation.py
│   │   │   └── emotion.py
│   │   └── protocol/        # 通信协议
│   │       └── serial_com.py
│   ├── config/             # 配置文件
│   └── utils/              # 工具函数
└── models/                  # 模型文件
    └── whisper/            # Whisper模型
```

## 技术栈

### 机器人端
- **MCU**: ESP32-S3-WROOM-1 (双核240MHz)
- **框架**: ESP-IDF v5.0
- **显示**: WS2812B LED矩阵 8x8
- **执行**: SG90舵机 x2
- **视觉**: OV2640摄像头
- **音频**: I2S麦克风 + 扬声器

### 主机端
- **语言**: Python 3.10+
- **唤醒**: openWakeWord
- **ASR**: Whisper (base模型)
- **TTS**: Piper
- **LLM**: GLM-4.7 (智谱AI)
- **视觉**: OpenCV + face_recognition
- **通信**: PySerial

## 配置

### GLM-4.7 API密钥

在 `host/config/api_keys.yaml` 中配置：

```yaml
glm:
  api_key: "your_glm4_api_key_here"
  model: "glm-4"
  base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"
```

### 唤醒词

在 `host/config/wake_word.yaml` 中配置：

```yaml
wake_word: "瓦力"
```

## 开发计划

详见 [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 致谢

本项目借鉴了以下优秀的开源项目：

- [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) - AI语音助手
- [openWakeWord](https://github.com/dscrianja/openWakeWord) - 唤醒词检测
- [Wall-E Robot Replica](https://github.com/) - 瓦力机器人
- [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) - 实时语音识别

## 联系方式

- Issues: [GitHub Issues](https://github.com/yourusername/DaShan/issues)

---

**DaShan** - 你的桌面智能伙伴 🤖

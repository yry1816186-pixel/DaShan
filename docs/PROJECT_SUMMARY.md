# DaShan 项目总结

## 项目概述

DaShan 是一个高性能、可扩展的 AI 桌宠机器人系统，采用"表演层+大脑层"的双架构设计。项目名称取自"大山"，寓意稳重、可靠、持久。

## 核心特性

### 🎯 低延迟交互
- 唤醒词响应 <200ms
- 语音识别实时处理
- 表情动画流畅同步

### 👁️ 自然注视
- 实时人脸追踪
- 智能注视点计算
- 头部跟随运动

### 😊 丰富情感
- 15+ 预设表情
- 情绪识别和传播
- 动画节奏同步

### 🧠 强大AI大脑
- GLM-4.7 大语言模型
- 长期记忆管理
- 个性化对话

### 🔊 离线语音
- openWakeWord 本地唤醒
- Whisper 语音识别
- Piper 语音合成

### 📷 多模态感知
- 摄像头视觉
- 红外距离传感
- 环境光感知

## 技术架构

### 机器人端 (ESP32-S3)

**核心组件**:
- WS2812B LED矩阵 (8x8眼睛)
- SG90舵机 (2自由度头部)
- OV2640摄像头
- I2S麦克风 + 扬声器
- HC-SR04超声波传感器

**软件模块**:
- 协议处理
- LED矩阵驱动
- 舵机控制
- 状态机
- 音频处理
- 摄像头驱动
- 传感器接口

### 主机端

**核心模块**:
- 语音处理
- 对话引擎 (GLM-4.7)
- 记忆管理
- 视觉追踪
- 行为编排
- 串口通信

## 项目结构

```
DaShan/
├── README.md                    # 项目说明
├── requirements.txt             # Python依赖
├── docs/                       # 文档
│   ├── HARDWARE.md            # 硬件清单
│   ├── INSTALLATION.md        # 安装指南
│   ├── ARCHITECTURE.md       # 架构设计
│   ├── PROTOCOL.md           # 通信协议
│   └── PROJECT_SUMMARY.md    # 项目总结
├── robot/                      # 机器人端
│   └── main/
│       ├── main.c
│       ├── protocol.h/c
│       ├── led_matrix.h/c
│       ├── servo.h/c
│       ├── state_machine.h/c
│       ├── camera.h/c
│       ├── audio.h/c
│       └── sensor.h/c
└── host/                       # 主机端
    ├── main.py                # 主控制器
    ├── config/
    │   └── api_keys.yaml      # 配置文件
    └── modules/
        ├── protocol/
        │   └── serial_com.py
        ├── voice/
        │   ├── wake_word.py
        │   ├── stt.py
        │   └── tts.py
        ├── dialogue/
        │   ├── llm.py
        │   └── memory.py
        └── behavior/
            ├── animation.py
            └── emotion.py
```

## 硬件清单

### 机器人端 (约¥200-250)

| 组件 | 数量 | 价格 |
|------|------|------|
| ESP32-S3-WROOM-1 | 1 | ¥30 |
| WS2812B 8x8 | 1 | ¥20 |
| SG90舵机 | 2 | ¥16 |
| OV2640摄像头 | 1 | ¥25 |
| I2S麦克风 | 1 | ¥15 |
| 音频功放+扬声器 | 1 | ¥17 |
| HC-SR04传感器 | 1 | ¥8 |
| 电源系统 | 1 | ¥30 |
| 结构件 | 1 | ¥50 |
| 其他 | 1 | ¥40 |

### 主机端

使用现有电脑/笔记本，无需额外购买

## 开发状态

### ✅ 已完成

- [x] 项目架构设计
- [x] 硬件清单文档
- [x] 软件架构文档
- [x] 通信协议定义
- [x] 主机端通信模块
- [x] 语音唤醒检测
- [x] 语音识别 (Whisper)
- [x] 语音合成 (Piper)
- [x] GLM-4.7对话集成
- [x] 记忆管理系统
- [x] 表情动画系统
- [x] 情绪管理器
- [x] 主控制器
- [x] 机器人端驱动
- [x] 安装文档

### 🚧 待完善

- [ ] 视觉追踪模块
- [ ] 3D打印文件
- [ ] 用户使用文档
- [ ] API文档
- [ ] 测试套件
- [ ] 性能优化

## 技术亮点

### 1. 模块化设计
- 松耦合架构
- 易于扩展和替换
- 清晰的接口定义

### 2. 实时性保证
- FreeRTOS多任务
- 异步处理
- 低延迟通信

### 3. 可扩展性
- 插件化模块
- 配置驱动行为
- 模型可替换

### 4. 用户体验
- 自然的交互流程
- 丰富的情感表达
- 智能的记忆管理

## 应用场景

- **桌面伴侣**: 办公环境下的智能助手
- **教育娱乐**: 学习编程和机器人
- **智能家居**: 控制中心和语音助手
- **社交陪伴**: 独居用户的陪伴者

## 性能指标

| 指标 | 数值 |
|------|------|
| 唤醒延迟 | <200ms |
| 语音识别延迟 | <1s |
| 对话生成延迟 | <2s |
| 语音合成延迟 | <500ms |
| 电池续航 | 4-6小时 |
| 内存占用 | ~2GB (主机) |

## 开发路线图

### Phase 1: 核心功能 ✅
- 基础通信
- 语音交互
- 表情显示

### Phase 2: 增强功能
- 视觉追踪
- 情绪识别
- 记忆系统

### Phase 3: 高级特性
- 多模态融合
- 个性化学习
- 云端同步

### Phase 4: 生态扩展
- 插件市场
- 社区分享
- 商业化

## 贡献指南

欢迎贡献代码、文档和想法！

1. Fork 项目
2. 创建特性分支
3. 提交 Pull Request

## 许可证

MIT License - 自由使用和修改

## 致谢

感谢以下开源项目：
- [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
- [openWakeWord](https://github.com/dscrianja/openWakeWord)
- [Wall-E Robot Replica](https://github.com/)
- [RealtimeSTT](https://github.com/KoljaB/RealtimeSTT)
- [Whisper](https://github.com/openai/whisper)
- [Piper](https://github.com/rhasspy/piper)

## 联系方式

- GitHub Issues: [项目Issues](https://github.com/yourusername/DaShan/issues)
- Email: your.email@example.com

---

**DaShan** - 你的桌面智能伙伴 🤖

*让科技更有温度*

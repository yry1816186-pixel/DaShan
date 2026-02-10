# DaShan V2.0 系统架构文档

## 概述

DaShan V2.0 采用分布式架构，分为主机端（Python）和机器人端（ESP32-S3固件），通过串口/USB-C/BLE通信。V2.0版本引入了多项工程级改进，包括LangGraph Agent框架、RAG知识库、行为树系统、实时语音交互、Web仪表板、多模态融合、BLE/OTA固件升级和插件系统。

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              主机端 V2.0                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    主程序 (main_v2.py)                        │   │
│  └────────────────────┬────────────────────────────────────────────┘   │
│                     │                                             │
│  ┌──────────────────┴──────────────────────────────────────────────┐   │
│  │                   行为树系统 (Behavior Tree)                  │   │
│  │  - Sequence/Selector/Parallel/Decorator Nodes                 │   │
│  │  - Tick-based Execution (60Hz)                                │   │
│  └──────────────────┬──────────────────────────────────────────────┘   │
│                     │                                             │
│       ┌─────────────┼─────────────┐                              │
│       │             │             │                              │
│  ┌────┴────┐   ┌───┴────┐   ┌───┴────┐                      │
│  │Agent框架 │   │RAG系统 │   │多模态融合│                    │
│  │-LangGraph│   │-ChromaDB│   │-CLIP编码│                    │
│  │-StateGraph│   │-FAISS  │   │-Vision-L│                    │
│  │-Tools    │   │-Embedding│   │-Emotion│                    │
│  └────┬────┘   └───┬────┘   └───┬────┘                      │
│       │             │             │                              │
│  ┌────┴────┐   ┌───┴────┐   ┌───┴────┐                      │
│  │实时语音 │   │Web仪表板│   │插件系统│                      │
│  │-VAD     │   │-FastAPI │   │-Plugin │                    │
│  │-Realtime│   │-WebSocket│   │-Manager│                    │
│  │-Streaming│   │-Dashboard│   │-Loader │                    │
│  └────┬────┘   └───┬────┘   └───┬────┘                      │
│       │             │             │                              │
│  ┌────┴─────────────┴─────────────┴────┐                      │
│  │              协议客户端            │                      │
│  │   - Serial/UART                   │                      │
│  │   - Bluetooth Low Energy (BLE)     │                      │
│  └────────────────┬───────────────────┘                      │
└───────────────────┬─────────────────────────────────────────────────┘
                    │ USB-C / BLE / UART
┌───────────────────┬─────────────────────────────────────────────────┐
│                   │                                              │
│  ┌────────────────┴─────────────────────────────────────────────┐   │
│  │               ESP32-S3 固件 V2.0                          │   │
│  └────────────────┬────────────────────────────────────────────┘   │
│                   │                                               │
│       ┌───────────┼───────────┐                                  │
│       │           │           │                                  │
│  ┌────┴────┐ ┌───┴────┐  ┌───┴────┐                           │
│  │BLE管理器 │ │OTA管理器 │ │状态机  │                           │
│  │-GATT    │ │-HTTP    │ │-FreeRTOS│                           │
│  │-Character│ │-Partition│ │-Tasks  │                           │
│  └──────────┘ └──────────┘  └───┬────┘                           │
│                              │                                   │
│  ┌─────────────────────────────┼─────────────────────────────┐   │
│  │              硬件驱动层    │                             │   │
│  │  - LED矩阵 (WS2812B)      │                             │   │
│  │  - 舵机控制 (PWM)         │                             │   │
│  │  - 音频 I2S               │                             │   │
│  │  - 摄像头 OV5640          │                             │   │
│  │  - 传感器 (VL53L0X, etc.)  │                             │   │
│  └─────────────────────────────┴─────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

## 主机端架构 V2.0

### 核心模块

#### 1. Agent框架 (LangGraph)

```python
host/core/agent/
├── agent_graph.py      # DashanAgent with StateGraph
├── agent_state.py      # AgentState, AgentMessage
├── agent_config.py    # AgentConfig
└── tool_registry.py   # ToolRegistry, BaseTool
```

**特性：**
- LangGraph StateGraph多步推理
- 工具调用和知识检索集成
- 意图分类和响应生成
- 可扩展的工具系统

**处理流程：**
```
input_processing → intent_classification → tool_selection 
→ tool_execution → knowledge_retrieval → reasoning 
→ response_generation → output_formatting
```

#### 2. RAG系统 (知识检索)

```python
host/core/rag/
├── knowledge_manager.py  # KnowledgeManager
├── vector_store.py       # VectorStore (ChromaDB/FAISS)
├── embedding_service.py  # EmbeddingService (SentenceTransformers)
└── document_processor.py # DocumentProcessor
```

**特性：**
- ChromaDB持久化向量数据库
- FAISS高性能向量搜索
- 中文文本嵌入 (shibing624/text2vec-base-chinese)
- 文档分块和预处理

#### 3. 行为树系统

```python
host/core/behavior_tree/
├── behavior_tree.py    # BehaviorTree, BaseNode
├── nodes.py            # Sequence, Selector, Parallel
├── decorators.py       # Retry, TimeLimit, Inverter
├── leaf_nodes.py       # Action, Condition, Wait
└── dashan_nodes.py     # DaShan-specific nodes
```

**节点类型：**
- **Composite**: Sequence, Selector, Parallel
- **Decorator**: Retry, TimeLimit, Inverter, Cooldown, Throttle
- **Leaf**: Action, Condition, Wait, Random

**行为树结构：**
```
Root
├─ Emergency Sequence (紧急处理)
│  ├─ Low Battery Condition
│  └─ Sleep Action
├─ Interaction Sequence (交互)
│  ├─ User Detected Condition
│  ├─ Wake Action
│  ├─ Listen Sequence
│  ├─ Think Sequence
│  └─ Talk Sequence
├─ Tracking Sequence (追踪)
│  ├─ Face Detected Condition
│  └─ Track Face Action
├─ Idle Sequence (待机)
│  ├─ Random Animation
│  └─ Blink Eyes
└─ Sleep Sequence (睡眠)
   └─ Power Down
```

#### 4. 实时语音系统

```python
host/modules/voice/
├── realtime_stt.py    # RealtimeSTT with VAD
└── streaming_tts.py   # StreamingTTS
```

**特性：**
- RealtimeSTT流式语音识别
- WebRTC VAD语音活动检测
- Edge-TTS/Piper流式语音合成
- 回声消除和降噪

#### 5. Web仪表板

```python
host/web/
├── api.py           # FastAPI应用
└── websocket.py     # WebSocket处理
```

**特性：**
- FastAPI + WebSocket实时通信
- 内嵌HTML仪表板
- 实时日志和系统状态
- 远程控制和配置

#### 6. 多模态融合

```python
host/core/multimodal/
├── clip_encoder.py       # CLIPEncoder
├── multimodal_fusion.py  # MultimodalFusion
├── vision_language.py    # VisionLanguage
└── emotion_recognition.py # EmotionRecognition
```

**特性：**
- CLIP文本-图像编码
- 加权求和融合
- 注意力机制融合
- 情感识别

#### 7. 插件系统

```python
host/plugins/
├── plugin_base.py      # Plugin, PluginInfo, PluginContext
├── plugin_manager.py   # PluginManager
├── plugin_loader.py    # PluginLoader
└── examples/
   ├─ hello_plugin.py   # 示例命令插件
   ├─ memory_plugin.py  # 示例提供者插件
   └─ content_filter.py # 示例过滤器插件
```

**插件类型：**
- **Command**: 命令执行插件
- **Filter**: 内容过滤插件
- **Provider**: 数据提供插件
- **Extension**: 扩展功能插件

### 功能模块

#### 1. 语音模块

```python
voice/
├── wake_word.py    # 唤醒词检测
│   └── OpenWakeWord
├── stt.py         # 语音识别
│   └── Whisper
├── tts.py         # 语音合成
│   └── Piper TTS
└── emotion_tts.py  # 情感TTS
```

**工作流程：**
1. 唤醒词检测 -> 触发LISTEN状态
2. 语音录制 + STT -> 识别文本
3. 发送到LLM -> 生成响应
4. TTS合成 -> 播放音频

#### 2. 视觉模块

```python
vision/
├── camera.py         # 摄像头管理
├── face_tracker.py   # 人脸追踪
│   ├── 检测
│   ├── 追踪
│   └── 平滑
└── gaze_tracking.py  # 注视追踪
    ├── 注视点计算
    ├── 预测
    └── 舵机角度计算
```

**工作流程：**
1. 摄像头采集图像
2. 人脸检测 -> 获取人脸位置
3. 注视计算 -> 计算注视点
4. 舵机控制 -> 转向用户

#### 3. 对话模块

```python
dialogue/
├── llm.py           # LLM接口
│   ├── 智谱GLM
│   ├── OpenAI
│   └── 本地模型
├── memory.py        # 记忆管理
│   ├── 短期记忆
│   ├── 长期记忆
│   └── RAG检索
└── prompt_manager.py # 提示词管理
```

**工作流程：**
1. 接收用户输入
2. 检索相关记忆
3. 构建提示词
4. 调用LLM API
5. 保存响应到记忆

#### 4. 行为模块

```python
behavior/
├── animation.py     # 动画管理
├── emotion.py      # 情感分析
└── behavior_planner.py  # 行为规划
    ├── 随机行为
    ├── 上下文感知
    └── 状态驱动
```

**行为类型：**
- 表情切换
- 眨眼动画
- 头部移动
- 随机微动
- 待机动画

#### 5. 通信模块

```python
protocol/
└── serial_com.py
    ├── 协议帧构建
    ├── CRC校验
    ├── 串口通信
    └── 消息处理
```

## 机器人端架构 V2.0

### 固件模块

```
robot/main/
├── main.c              # 主程序
├── driver/             # 驱动层
│   ├── led.c/h        # LED/OLED驱动
│   ├── servo.c/h      # 舵机驱动
│   ├── camera.c/h     # 摄像头驱动
│   ├── audio.c/h      # 音频驱动
│   └── sensor.c/h     # 传感器驱动
├── components/         # 组件层
│   ├── protocol.c/h    # 协议处理
│   └── state_machine.c/h  # 状态机
├── ble_manager.c/h    # BLE GATT服务
└── ota_manager.c/h    # OTA固件更新
```

### FreeRTOS任务

```c
// 任务优先级（数值越小优先级越高）
TASK_PRIORITY_PROTOCOL    (1)  // 协议处理
TASK_PRIORITY_BLE         (2)  // BLE通信
TASK_PRIORITY_CAMERA     (3)  // 摄像头采集
TASK_PRIORITY_AUDIO      (4)  // 音频处理
TASK_PRIORITY_SENSOR     (5)  // 传感器读取
TASK_PRIORITY_OTA        (6)  // OTA更新
TASK_PRIORITY_DISPLAY    (7)  // 显示更新
TASK_PRIORITY_SERVO     (8)  // 舵机控制
```

### BLE GATT服务

```c
// 特征定义
CHARACTERISTIC_COMMAND     (0x2A01)  // 命令特征
CHARACTERISTIC_STATUS      (0x2A02)  // 状态特征
CHARACTERISTIC_DATA        (0x2A03)  // 数据特征
CHARACTERISTIC_CONFIG      (0x2A04)  // 配置特征

// 命令类型
CMD_PING           (0x01)  // 心跳
CMD_SET_EXPRESSION  (0x10)  // 设置表情
CMD_SET_SERVO      (0x20)  // 设置舵机
CMD_GET_STATUS     (0x30)  // 获取状态
CMD_START_OTA      (0x40)  // 开始OTA
CMD_RESTART        (0x50)  // 重启
CMD_PLAY_AUDIO     (0x60)  // 播放音频
```

### OTA固件更新

```c
// OTA状态
OTA_STATE_IDLE        (0x00)
OTA_STATE_DOWNLOADING (0x01)
OTA_STATE_WRITING    (0x02)
OTA_STATE_VERIFYING  (0x03)
OTA_STATE_REBOOTING  (0x04)
OTA_STATE_ERROR      (0x05)

// OTA错误码
OTA_ERROR_INVALID_URL    (0x01)
OTA_ERROR_CONNECT_FAILED (0x02)
OTA_ERROR_DOWNLOAD_FAILED (0x03)
OTA_ERROR_WRITE_FAILED   (0x04)
OTA_ERROR_VERIFY_FAILED (0x05)
```

### 状态机

```c
RobotState {
    SLEEP,      // 睡眠
    WAKE,       // 唤醒
    LISTEN,     // 听取
    THINK,      // 思考
    TALK,       // 说话
    ERROR,      // 错误
    CHARGING,   // 充电
    UPDATING,   // OTA更新
    BLE_CONNECTING, // BLE连接中
    BLE_CONNECTED    // BLE已连接
}
```

## 通信协议

### 协议帧格式

```
+--------+--------+--------+--------+--------+--------+--------+--------+
|  Sync  |  Sync  | Length |  Type  |  Seq   | Payload|  CRC   |
|  0xAA  |  0x55  | 2 bytes| 1 byte | 1 byte | N bytes| 1 byte |
+--------+--------+--------+--------+--------+--------+--------+--------+
```

### 消息类型

| 类型 | 值 | 方向 | 说明 |
|------|-----|------|------|
| MSG_ACK | 0x00 | 双向 | 确认 |
| MSG_PING | 0x01 | 双向 | 心跳 |
| MSG_SET_EXPRESSION | 0x10 | 主->机 | 设置表情 |
| MSG_SET_BRIGHTNESS | 0x11 | 主->机 | 设置亮度 |
| MSG_SERVO_MOVE | 0x20 | 主->机 | 移动舵机 |
| MSG_SERVO_STOP | 0x21 | 主->机 | 停止舵机 |
| MSG_AUDIO_PLAY | 0x30 | 主->机 | 播放音频 |
| MSG_CAMERA_GET_FRAME | 0x42 | 主->机 | 获取图像 |
| MSG_SENSOR_GET_DATA | 0x50 | 机->主 | 传感器数据 |
| MSG_GET_STATUS | 0x60 | 双向 | 获取状态 |

### CRC计算

```python
def calc_crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = (crc << 1) ^ 0x07
            else:
                crc = crc << 1
    return crc & 0xFF
```

## 数据流

### 语音交互流程

```
用户说话 -> 麦克风(I2S) -> ESP32 -> 串口 -> 主机
         -> 唤醒词检测 -> 识别(STT) -> LLM -> TTS -> 播放
         -> ESP32 -> 舵机转向用户
```

### 视觉追踪流程

```
摄像头 -> OV5640 -> ESP32 -> DVP -> 图像缓存
       -> 串口 -> 主机
       -> OpenCV人脸检测 -> 追踪 -> 注视计算
       -> 舵机角度 -> ESP32 -> 舵机控制
```

### 状态同步流程

```
主机状态机 --事件--> 机器人状态机
      |                     |
      v                     v
  行为决策           硬件响应
      |                     |
      v                     v
  表情显示 <--协议帧-- 硬件控制
```

## 扩展性设计

### 添加新模块

1. 在`host/modules/`创建新模块
2. 继承事件订阅者接口
3. 在`host/main.py`中注册
4. 添加配置项

### 添加新硬件

1. 在`robot/main/driver/`添加驱动
2. 实现初始化和控制接口
3. 在协议中添加消息类型
4. 更新硬件配置文档

### 添加新LLM

1. 在`host/modules/dialogue/llm.py`添加新接口
2. 实现统一的LLM接口
3. 在配置中添加模型选项

## 性能优化

### 主机端

- 使用多线程处理并发任务
- 事件队列缓存高负载
- 图像处理使用GPU加速
- LLM响应流式输出

### 机器人端

- FreeRTOS任务优先级调度
- DMA传输减少CPU占用
- PSRAM缓存大块数据
- 硬件PWM/ADC减少软件开销

## 安全性

### 数据安全

- API密钥加密存储
- 串口通信加密（可选）
- 本地记忆数据脱敏

### 硬件安全

- 电池过充/过放保护
- 舵机限位保护
- 传感器异常检测
- 看门狗定时器

## 故障处理

### 主机端

- 异常捕获与恢复
- 自动重连机制
- 降级模式（无视觉/无LLM）
- 错误日志记录

### 机器人端

- 看门狗复位
- 状态异常恢复
- 硬件错误上报
- 安全模式（限制运动）

## 未来扩展

- 多机器人协作
- 云端语音识别
- 远程控制接口
- 自定义表情编辑器
- 语音克隆技术
- 情感识别
- 个性化训练

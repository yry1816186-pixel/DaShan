# 通信协议文档

## 概述

本文档定义了机器人端(ESP32)与主机端(PC/Raspberry Pi)之间的串口通信协议。

## 通信参数

- **接口**: UART / USB-CDC
- **波特率**: 115200
- **数据位**: 8
- **停止位**: 1
- **校验位**: None
- **流控**: None

## 帧格式

### 基本帧结构

```
┌──────┬──────┬──────┬──────┬──────┐
| HEAD | CMD  | LEN  | DATA | CRC  |
└──────┴──────┴──────┴──────┴──────┘
 1字节  1字节  2字节  N字节  1字节
```

| 字段 | 大小 | 说明 |
|------|------|------|
| HEAD | 1字节 | 帧头标识，固定值0xAA |
| CMD | 1字节 | 命令码 |
| LEN | 2字节 | 数据长度(小端序)，0-65535 |
| DATA | N字节 | 数据内容 |
| CRC | 1字节 | CRC8校验和 |

### CRC8计算

```c
uint8_t calc_crc8(const uint8_t *data, size_t len) {
    uint8_t crc = 0;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : crc << 1;
        }
    }
    return crc;
}
```

## 命令定义

### 心跳命令 (0x01)

#### 主机 → 机器人 (PING)

```
HEAD: 0xAA
CMD:  0x01
LEN:  0x0000
DATA: (空)
CRC:  (计算)
```

#### 机器人 → 主机 (PONG)

```
HEAD: 0xAA
CMD:  0x01
LEN:  0x0008
DATA: 
  - uptime: uint32_t (运行时间，秒)
  - free_heap: uint32_t (空闲内存，字节)
CRC:  (计算)
```

### 设置表情 (0x02)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x02
LEN:  0x0004
DATA:
  - expression_id: uint8_t (表情ID，0-15)
  - brightness: uint8_t (亮度，0-255)
  - duration: uint16_t (持续时间，毫秒，0表示永久)
CRC:  (计算)
```

**表情ID定义**:
- 0x00: SLEEP (休眠)
- 0x01: WAKE (唤醒)
- 0x02: LISTEN (倾听)
- 0x03: THINK (思考)
- 0x04: TALK (说话)
- 0x05: HAPPY (开心)
- 0x06: SAD (伤心)
- 0x07: SURPRISED (惊讶)
- 0x08: CONFUSED (困惑)
- 0x09: CURIOUS (好奇)
- 0x0A: SHY (害羞)
- 0x0B: ANGRY (生气)
- 0x0C: LOVE (喜爱)
- 0x0D: TIRED (疲惫)
- 0x0E: EXCITED (兴奋)
- 0x0F: BLANK (空白)

### 控制舵机 (0x03)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x03
LEN:  0x0005
DATA:
  - servo_id: uint8_t (舵机ID: 1=水平, 2=垂直)
  - angle: uint16_t (角度，0-180，1000表示0度，2000表示180度)
  - speed: uint16_t (速度，1-100，1最慢，100最快)
CRC:  (计算)
```

#### 机器人 → 主机 (响应)

```
HEAD: 0xAA
CMD:  0x03
LEN:  0x0001
DATA:
  - status: uint8_t (0=成功, 1=失败)
CRC:  (计算)
```

### 播放音频 (0x04)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x04
LEN:  0x0004 + N
DATA:
  - format: uint8_t (音频格式: 1=PCM 16bit, 2=MP3, 3=OPUS)
  - sample_rate: uint16_t (采样率: 8000/16000/44100)
  - channels: uint8_t (声道数: 1=单声道, 2=立体声)
  - audio_data: N字节 (音频数据)
CRC:  (计算)
```

#### 机器人 → 主机 (响应)

```
HEAD: 0xAA
CMD:  0x04
LEN:  0x0001
DATA:
  - status: uint8_t (0=播放中, 1=完成, 2=错误)
CRC:  (计算)
```

### 录音数据 (0x05)

#### 机器人 → 主机

```
HEAD: 0xAA
CMD:  0x05
LEN:  0x0006 + N
DATA:
  - timestamp: uint32_t (时间戳，毫秒)
  - sample_rate: uint16_t (采样率)
  - audio_data: N字节 (PCM 16bit音频数据)
CRC:  (计算)
```

### 发送图像 (0x06)

#### 机器人 → 主机

```
HEAD: 0xAA
CMD:  0x06
LEN:  0x0008 + N
DATA:
  - width: uint16_t (图像宽度)
  - height: uint16_t (图像高度)
  - format: uint8_t (格式: 1=JPEG, 2=RGB565)
  - quality: uint8_t (JPEG质量，1-100)
  - image_data: N字节 (图像数据)
CRC:  (计算)
```

### 切换状态 (0x07)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x07
LEN:  0x0001
DATA:
  - state: uint8_t (状态ID: 1=SLEEP, 2=WAKE, 3=LISTEN, 4=THINK, 5=TALK)
CRC:  (计算)
```

#### 机器人 → 主机 (响应)

```
HEAD: 0xAA
CMD:  0x07
LEN:  0x0001
DATA:
  - status: uint8_t (0=成功, 1=失败)
CRC:  (计算)
```

### 获取状态 (0x08)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x08
LEN:  0x0000
DATA: (空)
CRC:  (计算)
```

#### 机器人 → 主机

```
HEAD: 0xAA
CMD:  0x08
LEN:  0x0009
DATA:
  - state: uint8_t (当前状态)
  - battery: uint8_t (电池电量，0-100)
  - expression: uint8_t (当前表情)
  - servo_h: uint16_t (水平舵机角度)
  - servo_v: uint16_t (垂直舵机角度)
CRC:  (计算)
```

### 传感器数据 (0x09)

#### 机器人 → 主机

```
HEAD: 0xAA
CMD:  0x09
LEN:  0x0004
DATA:
  - distance: uint16_t (距离，厘米，0xFFFF=无效)
  - proximity: uint8_t (接近检测，0=无物体, 1=有物体)
  - light: uint8_t (光强，0-255)
CRC:  (计算)
```

### 录音控制 (0x0A)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x0A
LEN:  0x0002
DATA:
  - action: uint8_t (1=开始录音, 2=停止录音)
  - duration: uint8_t (最大录音时长，秒，0表示无限制)
CRC:  (计算)
```

#### 机器人 → 主机 (响应)

```
HEAD: 0xAA
CMD:  0x0A
LEN:  0x0001
DATA:
  - status: uint8_t (0=成功, 1=失败)
CRC:  (计算)
```

### 摄像头控制 (0x0B)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x0B
LEN:  0x0002
DATA:
  - action: uint8_t (1=开启, 2=关闭, 3=捕获单帧)
  - interval: uint8_t (捕获间隔，秒，仅持续捕获有效)
CRC:  (计算)
```

#### 机器人 → 主机 (响应)

```
HEAD: 0xAA
CMD:  0x0B
LEN:  0x0001
DATA:
  - status: uint8_t (0=成功, 1=失败)
CRC:  (计算)
```

### 设置注视点 (0x0C)

#### 主机 → 机器人

```
HEAD: 0xAA
CMD:  0x0C
LEN:  0x0004
DATA:
  - x: int16_t (X坐标，-100到100，0为中心)
  - y: int16_t (Y坐标，-100到100，0为中心)
CRC:  (计算)
```

#### 机器人 → 主机 (响应)

```
HEAD: 0xAA
CMD:  0x0C
LEN:  0x0001
DATA:
  - status: uint8_t (0=成功, 1=失败)
CRC:  (计算)
```

### 错误报告 (0xFF)

#### 机器人 → 主机

```
HEAD: 0xAA
CMD:  0xFF
LEN:  0x0003
DATA:
  - error_code: uint8_t (错误码)
  - component: uint8_t (组件ID)
  - detail: uint8_t (详细错误信息)
CRC:  (计算)
```

**错误码定义**:
- 0x01: 内存不足
- 0x02: 通信超时
- 0x03: 传感器故障
- 0x04: 执行器故障
- 0x05: 电池电量低
- 0x06: 过热保护
- 0x07: 参数错误

**组件ID定义**:
- 0x01: LED
- 0x02: 舵机
- 0x03: 摄像头
- 0x04: 音频
- 0x05: 传感器

## 通信流程

### 初始化流程

```
主机                        机器人
 │                            │
 ├────── PING ──────────────>│
 │                            │
 │<───── PONG ───────────────┤
 │                            │
 ├────── GET_STATUS ────────>│
 │                            │
 │<───── STATUS ──────────────┤
 │                            │
 ├────── SET_STATE(WAKE) ───>│
 │                            │
 │<───── STATUS(OK) ─────────┤
 │                            │
```

### 语音交互流程

```
主机                        机器人
 │                            │
 ├────── SET_STATE(LISTEN) ─>│
 │                            │
 ├────── RECORD(START) ─────>│
 │                            │
 │<───── AUDIO_DATA ─────────┤
 │<───── AUDIO_DATA ─────────┤
 │<───── ... ────────────────┤
 │                            │
 ├────── RECORD(STOP) ─────>│
 │                            │
 │  (Whisper STT)             │
 │  (GLM-4.7生成)            │
 │  (Piper TTS)              │
 │                            │
 ├────── SET_STATE(THINK) ──>│
 │                            │
 ├────── SET_STATE(TALK) ───>│
 │                            │
 ├────── PLAY_AUDIO ────────>│
 │                            │
 ├────── SET_EXPRESSION ────>│
 │                            │
 │<───── STATUS(DONE) ──────┤
 │                            │
 │  (等待30s超时)             │
 │                            │
 ├────── SET_STATE(SLEEP) ──>│
 │                            │
```

### 视觉追踪流程

```
主机                        机器人
 │                            │
 ├────── CAMERA(START) ─────>│
 │                            │
 │<───── STATUS(OK) ─────────┤
 │                            │
 │<───── IMAGE_DATA ─────────┤
 │  (OpenCV人脸检测)          │
 │  (计算注视点)              │
 │                            │
 ├────── SET_GAZE ──────────>│
 │                            │
 │<───── STATUS(OK) ─────────┤
 │                            │
 │<───── IMAGE_DATA ─────────┤
 │  (循环...)                 │
 │                            │
 ├────── CAMERA(STOP) ──────>│
 │                            │
```

## 错误处理

### 超时处理

- 心跳超时: 5秒无响应 → 重连
- 命令响应超时: 2秒 → 重试3次
- 数据传输超时: 根据数据量动态调整

### 错误恢复

```
检测到错误
  ↓
记录错误日志
  ↓
发送错误报告
  ↓
尝试恢复
  ↓
恢复成功?
  ├─ 是 → 继续运行
  └─ 否 → 进入安全模式
```

### 安全模式

- 停止所有运动
- 关闭非必要外设
- 保持心跳连接
- 等待恢复命令

## 性能优化

### 批量传输

对于大量数据(如音频、图像)，使用分包传输:

```
┌──────┬──────┬──────┬──────┬──────┐
| HEAD | CMD  | LEN  | DATA | CRC  |
└──────┴──────┴──────┴──────┴──────┘
  - packet_id: uint16_t (包序号)
  - total_packets: uint16_t (总包数)
  - current_packet: uint16_t (当前包)
  - data: N字节 (实际数据)
```

### 压缩

- 图像数据: JPEG压缩
- 音频数据: OPUS压缩
- 减少传输延迟

## 安全机制

### 认证

可选的简单认证机制:

```
主机 → 机器人: AUTH(挑战码)
机器人 → 主机: AUTH_RESPONSE(哈希值)
```

### 加密

可选的AES加密:

```
加密(HEAD + CMD + LEN + DATA) → 加密数据
解密(加密数据) → HEAD + CMD + LEN + DATA
```

### 校验

- CRC8校验所有帧
- 序列号检测丢包
- 超时重传机制

## 调试

### 调试模式

启用调试输出，打印所有通信帧:

```
[2024-02-02 10:30:15] TX: AA 01 00 00 01
[2024-02-02 10:30:15] RX: AA 01 00 08 00 00 00 10 00 00 01 42
```

### 工具

提供协议调试工具:

- `protocol_test.py`: 协议测试脚本
- `protocol_analyzer.py`: 协议分析工具

---

## 版本历史

- v1.0.0 (2026-02-02): 初始协议定义

---

**DaShan** - 你的桌面智能伙伴 🤖

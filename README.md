# DaShan 桌宠机器人系统

> 一款智能交互式桌面宠物机器人，支持语音对话、视觉追踪、情感表达等功能

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange)]()

## 功能特性

- 语音交互：自定义唤醒词、语音识别、TTS语音合成
- 视觉追踪：人脸检测与追踪、注视点计算
- 情感表达：多种表情动画、LED/OLED显示
- 对话系统：支持多种LLM模型（智谱GLM、OpenAI等）
- 智能行为：状态机驱动的智能行为规划
- 模块化设计：松耦合架构，易于扩展和维护

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         主机端                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  语音模块    │  │  视觉模块    │  │  对话模块    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 行为模块    │  │ 事件总线    │  │ 配置管理    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │ USB-C / 串口
┌──────────────────────────┼──────────────────────────────────┐
│                          │                                  │
│  ┌──────────────┐  ┌────┴────┐  ┌──────────────┐         │
│  │  显示系统    │  │ 控制核心 │  │ 传感器      │         │
│  │  (OLED/LED)  │  │(ESP32-S3)│  │ (TOF/光敏)  │         │
│  └──────────────┘  └─────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  运动系统    │  │ 音频系统    │  │ 摄像头      │    │
│  │ (MG996R舵机) │  │ (I2S音频)   │  │  (OV5640)   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 硬件配置

### 推荐硬件列表

| 组件 | 型号 | 说明 |
|------|------|------|
| 主控制器 | ESP32-S3-WROOM-1-N8R8 | 8MB PSRAM，支持视频处理 |
| 显示 | 1.3寸圆形OLED SSD1306 x2 | 双眼显示，支持动画 |
| 舵机 | MG996R金属齿轮舵机 x2 | 更大扭矩，更精确 |
| 麦克风 | ICS-43432 I2S麦克风 | 高质量音频输入 |
| 扬声器 | 3W扬声器+音频功放 | 高质量音频输出 |
| 摄像头 | OV5640 (500万像素) | 人脸检测与追踪 |
| 距离传感器 | VL53L0X TOF | 精确距离检测 |
| 电源 | 3.7V锂电池+TP4056 | 2000mAh续航 |
| 通信 | USB-C | 数据传输+充电 |

### 硬件接线

详细接线图请参考 [docs/HARDWARE.md](docs/HARDWARE.md)

## 快速开始

### 环境要求

- Python 3.9+
- ESP-IDF 5.0+
- Windows/Linux/macOS

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/yourusername/DaShan.git
cd DaShan
```

2. 安装Python依赖
```bash
pip install -r requirements.txt
```

3. 配置API密钥
```bash
cp host/config/api_keys.template.yaml host/config/api_keys.yaml
# 编辑api_keys.yaml，填入你的LLM API密钥
```

4. 配置串口
```bash
# 编辑 host/config/settings.yaml，设置serial.port
serial:
  port: COM3  # Windows: COMx, Linux: /dev/ttyUSBx
```

5. 运行系统
```bash
python -m host.main
```

### 编译Robot固件

```bash
cd robot
idf.py set-target esp32s3
idf.py build
idf.py -p COM3 flash monitor
```

## 项目结构

```
DaShan/
├── host/              # 主机端Python代码
│   ├── core/         # 核心模块
│   │   ├── config.py      # 配置管理
│   │   ├── event_bus.py   # 事件总线
│   │   └── state_machine.py # 状态机
│   ├── modules/      # 功能模块
│   │   ├── voice/        # 语音模块
│   │   ├── vision/       # 视觉模块
│   │   ├── dialogue/     # 对话模块
│   │   ├── behavior/     # 行为模块
│   │   └── protocol/     # 协议通信
│   ├── config/       # 配置文件
│   └── tests/        # 单元测试
├── robot/             # 机器人端固件
│   └── main/         # ESP32主程序
├── docs/              # 文档
└── scripts/           # 脚本工具
```

## 配置说明

### 语音配置

编辑 `host/config/settings.yaml`:

```yaml
voice:
  wake_word: "瓦力"           # 唤醒词
  wake_threshold: 0.5        # 唤醒阈值
  sample_rate: 16000         # 采样率
  language: zh               # 语言
```

### 视觉配置

```yaml
vision:
  enabled: true
  camera_index: 0            # 摄像头索引
  width: 640
  height: 480
  fps: 15
  face_detection_model: hog   # 人脸检测模型
  gaze_tracking: true        # 启用注视追踪
```

### LLM配置

```yaml
llm:
  api_key: "your_api_key"
  model: "glm-4"
  base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"
  temperature: 0.7
  max_tokens: 1000
```

## 开发指南

### 运行测试

```bash
pytest host/tests/ -v
pytest host/tests/ --cov=host --cov-report=html
```

### 代码格式化

```bash
pip install black flake8 mypy
black host/
flake8 host/
mypy host/
```

### 添加新模块

1. 在 `host/modules/` 创建新模块目录
2. 实现模块功能
3. 在事件总线注册事件
4. 编写单元测试

### 扩展协议

编辑 `host/modules/protocol/serial_com.py` 和 `robot/main/components/protocol.c`:

```python
# 添加新消息类型
MSG_NEW_FEATURE = 0x70

# 构建协议帧
def build_new_feature_frame(self, param1, param2):
    payload = struct.pack('<BB', param1, param2)
    return self._build_frame(MSG_NEW_FEATURE, payload)
```

## 故障排除

### 常见问题

1. **串口连接失败**
   - 检查串口号是否正确
   - 确认USB驱动已安装
   - 尝试不同的波特率

2. **摄像头无法打开**
   - 检查摄像头索引
   - 确认摄像头未被其他程序占用
   - 尝试使用不同的后端 (cv2.CAP_DSHOW, cv2.CAP_V4L2)

3. **语音唤醒不灵敏**
   - 调整wake_threshold值
   - 确保麦克风工作正常
   - 在安静环境中测试

4. **LLM响应超时**
   - 检查API密钥是否正确
   - 确认网络连接正常
   - 增加timeout配置值

## 贡献指南

欢迎贡献代码！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [OpenWakeWord](https://github.com/dscrianka/openWakeWord) - 语音唤醒词检测
- [Whisper](https://github.com/openai/whisper) - 语音识别
- [Piper TTS](https://github.com/rhasspy/piper) - 语音合成
- [OpenCV](https://opencv.org/) - 计算机视觉
- [ESP-IDF](https://github.com/espressif/esp-idf) - ESP32开发框架

## 联系方式

- 项目主页: [https://github.com/yourusername/DaShan](https://github.com/yourusername/DaShan)
- 问题反馈: [Issues](https://github.com/yourusername/DaShan/issues)

---

**DaShan** - 让桌面生活更有趣

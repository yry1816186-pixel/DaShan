# 安装指南

本文档介绍如何安装和配置 DaShan 桌宠机器人系统。

## 系统要求

### 主机端

- **操作系统**: Windows 10/11 或 Linux (Ubuntu 22.04+)
- **Python**: 3.10 或更高版本
- **内存**: 至少 8GB RAM
- **存储**: 至少 50GB 可用空间
- **GPU**: 可选，用于加速 Whisper (CUDA 11.8+)

### 机器人端

- **开发板**: ESP32-S3-WROOM-1
- **开发环境**: ESP-IDF v5.0 或更高
- **操作系统**: Windows/Linux/macOS

## 主机端安装

### 1. 克隆项目

```bash
git clone https://github.com/yourusername/DaShan.git
cd DaShan
```

### 2. 安装 Python 依赖

#### Windows

```bash
pip install -r requirements.txt
```

#### Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 安装系统依赖

#### Windows

下载并安装以下软件：
- [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- [PortAudio](http://www.portaudio.com/)

#### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv
sudo apt-get install -y portaudio19-dev python3-pyaudio
sudo apt-get install -y espeak-ng libespeak1
sudo apt-get install -y ffmpeg libavcodec-extra
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
sudo apt-get install -y git wget curl
```

### 4. 安装 PyTorch (用于 Whisper)

#### CPU 版本

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

#### GPU 版本 (CUDA 11.8)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 5. 下载模型文件

#### Whisper 模型

```bash
cd models
wget https://huggingface.co/ggerganov/whisper-small/resolve/main/whisper-small.pt
```

或让 Whisper 自动下载（首次运行时）：

```python
from whisper import load_model
model = load_model("base")
```

#### Piper TTS 模型

```bash
cd models/tts
wget https://huggingface.co/rhasspy/piper-voice-zh_CN-xiaoyan-low/resolve/main/zh_CN-xiaoyan-low.onnx
wget https://huggingface.co/rhasspy/piper-voice-zh_CN-xiaoyan-low/resolve/main/zh_CN-xiaoyan-low.onnx.json
```

#### openWakeWord 模型

```bash
cd models/wakeword
wget https://github.com/dscrianja/openWakeWord/releases/download/v0.5.0/wakeword_models.tar.gz
tar -xzf wakeword_models.tar.gz
```

### 6. 配置 API 密钥

编辑 `host/config/api_keys.yaml`:

```yaml
glm:
  api_key: "your_glm4_api_key_here"
  model: "glm-4"
  base_url: "https://open.bigmodel.cn/api/paas/v4/chat/completions"
```

或设置环境变量：

```bash
# Windows
set GLM_API_KEY=your_glm4_api_key_here

# Linux/Mac
export GLM_API_KEY=your_glm4_api_key_here
```

### 7. 连接机器人

使用 USB 线将 ESP32-S3 连接到电脑。

在 Windows 上查看 COM 端口：
- 设备管理器 → 端口(COM 和 LPT)

在 Linux 上查看设备：
```bash
ls /dev/ttyUSB*
```

### 8. 运行主机端

```bash
cd host
python main.py --port COM3  # Windows
# 或
python main.py --port /dev/ttyUSB0  # Linux
```

## 机器人端安装

### 1. 安装 ESP-IDF

#### Windows

```bash
# 下载并运行 ESP-IDF 安装器
# https://dl.espressif.com/dl/esp-idf/
```

#### Linux

```bash
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
git checkout v5.0
./install.sh esp32s3
source ./export.sh
```

### 2. 配置项目

```bash
cd robot
idf.py set-target esp32s3
idf.py menuconfig
```

在 menuconfig 中配置：

```
Component config → ESP32S3-Specific
  → Support for external, SPI-connected RAM
    → (X) Support for SPI RAM (set_spi_ram=yes)

Component config → Camera configuration
  → Camera module
    → (X) ESP32-S3 Eye Camera

Component config → ESP32S3-Specific
  → Main XTAL frequency
    → 40MHz

Component config → Wi-Fi
  → (X) Enable WiFi
```

### 3. 编译和烧录

```bash
idf.py build
idf.py flash
idf.py monitor
```

### 4. 查看串口输出

```bash
idf.py monitor -p /dev/ttyUSB0  # Linux
idf.py monitor -p COM3           # Windows
```

## 故障排除

### 主机端问题

#### 问题：找不到串口

**解决方案**:
- 检查 USB 线是否连接
- 安装 CP2102/CH340 驱动
- 尝试不同的 USB 端口

#### 问题：PyAudio 安装失败

**解决方案**:
```bash
# Windows
pip install pipwin
pipwin install pyaudio

# Linux
sudo apt-get install python3-dev portaudio19-dev
pip install pyaudio
```

#### 问题：Whisper 模型加载慢

**解决方案**:
- 使用较小的模型 (tiny/base)
- 启用 GPU 加速
- 使用代理加速下载

#### 问题：GLM-4 API 调用失败

**解决方案**:
- 检查 API 密钥是否正确
- 检查网络连接
- 查看账户余额

### 机器人端问题

#### 问题：编译错误

**解决方案**:
```bash
idf.py fullclean
idf.py reconfigure
idf.py build
```

#### 问题：烧录失败

**解决方案**:
- 检查串口权限 (Linux)
- 按住 BOOT 按钮再上电
- 降低波特率

#### 问题：程序启动失败

**解决方案**:
- 检查电源供电
- 检查引脚连接
- 查看串口日志

## 性能优化

### 主机端

1. **启用 GPU 加速**
   - 安装 CUDA 版本的 PyTorch
   - 设置环境变量: `CUDA_VISIBLE_DEVICES=0`

2. **降低 Whisper 模型大小**
   - 使用 `tiny` 或 `base` 模型
   - 在 `STTConfig` 中配置

3. **启用多线程**
   - 在 Python 代码中设置线程池

### 机器人端

1. **降低采样率**
   - 减少音频采样率
   - 降低摄像头分辨率

2. **优化电源管理**
   - 启用低功耗模式
   - 合理配置睡眠时间

## 升级

### 主机端

```bash
git pull
pip install -r requirements.txt --upgrade
```

### 机器人端

```bash
cd robot
git pull
idf.py build flash monitor
```

## 卸载

### 主机端

```bash
deactivate  # 如果使用虚拟环境
rm -rf venv
```

### 机器人端

```bash
idf.py erase-flash
```

## 下一步

安装完成后，请查看：
- [使用指南](docs/USAGE.md)
- [API 文档](docs/API.md)
- [开发指南](docs/DEVELOPMENT.md)

---

**DaShan** - 你的桌面智能伙伴 🤖

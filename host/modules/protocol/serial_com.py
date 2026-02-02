import serial
import serial.tools.list_ports
import threading
import queue
import time
import logging
from typing import Optional, Callable, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CMD(IntEnum):
    HEARTBEAT = 0x01
    SET_EXPRESSION = 0x02
    SET_SERVO = 0x03
    PLAY_AUDIO = 0x04
    RECORD_AUDIO = 0x05
    SEND_IMAGE = 0x06
    SET_STATE = 0x07
    GET_STATUS = 0x08
    SENSOR_DATA = 0x09
    RECORD_CONTROL = 0x0A
    CAMERA_CONTROL = 0x0B
    SET_GAZE = 0x0C
    ERROR = 0xFF


class STATE(IntEnum):
    SLEEP = 1
    WAKE = 2
    LISTEN = 3
    THINK = 4
    TALK = 5


@dataclass
class Status:
    state: int
    battery: int
    expression: int
    servo_h: int
    servo_v: int


@dataclass
class SensorData:
    distance: int
    proximity: int
    light: int


class SerialProtocol:
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        self.response_event = threading.Event()
        self.response_data: Optional[bytes] = None
        self.timeout = 2.0
        
        self.callbacks = {
            CMD.HEARTBEAT: None,
            CMD.SET_EXPRESSION: None,
            CMD.SET_SERVO: None,
            CMD.PLAY_AUDIO: None,
            CMD.RECORD_AUDIO: None,
            CMD.SEND_IMAGE: None,
            CMD.SET_STATE: None,
            CMD.GET_STATUS: None,
            CMD.SENSOR_DATA: None,
            CMD.ERROR: None
        }
        
        self._stop_event = threading.Event()
        self._read_thread: Optional[threading.Thread] = None
        self._write_thread: Optional[threading.Thread] = None

    @staticmethod
    def calc_crc8(data: bytes) -> int:
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : crc << 1
        return crc & 0xFF

    @staticmethod
    def build_frame(cmd: int, data: bytes = b'') -> bytes:
        frame = bytearray()
        frame.append(0xAA)
        frame.append(cmd)
        length = len(data)
        frame.extend(length.to_bytes(2, 'little'))
        frame.extend(data)
        frame.append(SerialProtocol.calc_crc8(frame[:-1]))
        return bytes(frame)

    def parse_frame(self, frame: bytes) -> Tuple[int, bytes]:
        if len(frame) < 5:
            raise ValueError("Frame too short")
        
        if frame[0] != 0xAA:
            raise ValueError("Invalid header")
        
        cmd = frame[1]
        length = int.from_bytes(frame[2:4], 'little')
        
        if len(frame) != 5 + length:
            raise ValueError(f"Length mismatch: expected {5 + length}, got {len(frame)}")
        
        data = frame[4:4 + length]
        crc = frame[4 + length]
        
        calculated_crc = self.calc_crc8(frame[:-1])
        if crc != calculated_crc:
            raise ValueError(f"CRC mismatch: expected {calculated_crc}, got {crc}")
        
        return cmd, data

    def list_ports(self) -> list:
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self, port: Optional[str] = None) -> bool:
        if port:
            self.port = port
        
        if not self.port:
            available_ports = self.list_ports()
            if not available_ports:
                logger.error("No serial ports available")
                return False
            self.port = available_ports[0]
            logger.info(f"Using port: {self.port}")
        
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0
            )
            self.connected = True
            self._stop_event.clear()
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._write_thread = threading.Thread(target=self._write_loop, daemon=True)
            self._read_thread.start()
            self._write_thread.start()
            logger.info(f"Connected to {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        self._stop_event.set()
        if self._read_thread:
            self._read_thread.join(timeout=1.0)
        if self._write_thread:
            self._write_thread.join(timeout=1.0)
        if self.serial:
            self.serial.close()
            self.connected = False
        logger.info("Disconnected")

    def _read_loop(self):
        buffer = bytearray()
        while not self._stop_event.is_set() and self.connected:
            try:
                if self.serial.in_waiting > 0:
                    data = self.serial.read(self.serial.in_waiting)
                    buffer.extend(data)
                    
                    while len(buffer) >= 5:
                        if buffer[0] != 0xAA:
                            buffer = buffer[1:]
                            continue
                        
                        length = int.from_bytes(buffer[2:4], 'little')
                        frame_len = 5 + length
                        
                        if len(buffer) < frame_len:
                            break
                        
                        frame = bytes(buffer[:frame_len])
                        buffer = buffer[frame_len:]
                        
                        try:
                            cmd, data = self.parse_frame(frame)
                            self._handle_frame(cmd, data)
                        except ValueError as e:
                            logger.warning(f"Frame parsing error: {e}")
                
                time.sleep(0.001)
            except Exception as e:
                logger.error(f"Read error: {e}")
                break

    def _write_loop(self):
        while not self._stop_event.is_set() and self.connected:
            try:
                frame = self.tx_queue.get(timeout=0.1)
                if self.serial and self.serial.is_open:
                    self.serial.write(frame)
                    logger.debug(f"TX: {frame.hex()}")
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Write error: {e}")

    def _handle_frame(self, cmd: int, data: bytes):
        logger.debug(f"RX: CMD={cmd:02X}, DATA={data.hex()}")
        
        if cmd == CMD.HEARTBEAT:
            if len(data) >= 8:
                uptime = int.from_bytes(data[0:4], 'little')
                free_heap = int.from_bytes(data[4:8], 'little')
                logger.debug(f"Heartbeat: uptime={uptime}s, heap={free_heap}B")
        
        elif cmd == CMD.GET_STATUS:
            if len(data) >= 9:
                status = Status(
                    state=data[0],
                    battery=data[1],
                    expression=data[2],
                    servo_h=int.from_bytes(data[3:5], 'little'),
                    servo_v=int.from_bytes(data[5:7], 'little')
                )
                self.response_data = data
                self.response_event.set()
                
                if self.callbacks[CMD.GET_STATUS]:
                    self.callbacks[CMD.GET_STATUS](status)
        
        elif cmd == CMD.SENSOR_DATA:
            if len(data) >= 4:
                sensor_data = SensorData(
                    distance=int.from_bytes(data[0:2], 'little'),
                    proximity=data[2],
                    light=data[3]
                )
                if self.callbacks[CMD.SENSOR_DATA]:
                    self.callbacks[CMD.SENSOR_DATA](sensor_data)
        
        elif cmd == CMD.RECORD_AUDIO:
            if self.callbacks[CMD.RECORD_AUDIO]:
                self.callbacks[CMD.RECORD_AUDIO](data)
        
        elif cmd == CMD.SEND_IMAGE:
            if self.callbacks[CMD.SEND_IMAGE]:
                self.callbacks[CMD.SEND_IMAGE](data)
        
        elif cmd == CMD.ERROR:
            if len(data) >= 3:
                error_code = data[0]
                component = data[1]
                detail = data[2]
                logger.error(f"Error from robot: code={error_code}, component={component}, detail={detail}")
                if self.callbacks[CMD.ERROR]:
                    self.callbacks[CMD.ERROR](error_code, component, detail)
        
        elif cmd in self.callbacks and self.callbacks[cmd]:
            self.callbacks[cmd](data)

    def send_command(self, cmd: int, data: bytes = b'', wait_response: bool = False, timeout: float = 2.0) -> Optional[bytes]:
        if not self.connected:
            logger.error("Not connected")
            return None
        
        frame = self.build_frame(cmd, data)
        self.tx_queue.put(frame)
        
        if wait_response:
            self.response_event.clear()
            self.response_data = None
            if self.response_event.wait(timeout=timeout):
                return self.response_data
            else:
                logger.warning(f"Command {cmd:02X} timeout")
                return None
        return None

    def register_callback(self, cmd: int, callback: Callable[[bytes], None]):
        self.callbacks[cmd] = callback

    def ping(self) -> bool:
        response = self.send_command(CMD.HEARTBEAT, wait_response=True, timeout=self.timeout)
        return response is not None

    def set_expression(self, expression_id: int, brightness: int = 255, duration: int = 0) -> bool:
        data = bytes([expression_id, brightness]) + duration.to_bytes(2, 'little')
        response = self.send_command(CMD.SET_EXPRESSION, data, wait_response=True, timeout=self.timeout)
        return response is not None

    def set_servo(self, servo_id: int, angle: int, speed: int = 50) -> bool:
        data = bytes([servo_id]) + angle.to_bytes(2, 'little') + speed.to_bytes(2, 'little')
        response = self.send_command(CMD.SET_SERVO, data, wait_response=True, timeout=self.timeout)
        return response is not None

    def play_audio(self, audio_data: bytes, format: int = 1, sample_rate: int = 16000, channels: int = 1) -> bool:
        data = bytes([format]) + sample_rate.to_bytes(2, 'little') + bytes([channels]) + audio_data
        self.send_command(CMD.PLAY_AUDIO, data)
        return True

    def set_state(self, state: int) -> bool:
        data = bytes([state])
        response = self.send_command(CMD.SET_STATE, data, wait_response=True, timeout=self.timeout)
        return response is not None

    def get_status(self) -> Optional[Status]:
        response = self.send_command(CMD.GET_STATUS, wait_response=True, timeout=self.timeout)
        if response and len(response) >= 9:
            return Status(
                state=response[0],
                battery=response[1],
                expression=response[2],
                servo_h=int.from_bytes(response[3:5], 'little'),
                servo_v=int.from_bytes(response[5:7], 'little')
            )
        return None

    def record_control(self, action: int, duration: int = 0) -> bool:
        data = bytes([action, duration])
        response = self.send_command(CMD.RECORD_CONTROL, data, wait_response=True, timeout=self.timeout)
        return response is not None

    def camera_control(self, action: int, interval: int = 0) -> bool:
        data = bytes([action, interval])
        response = self.send_command(CMD.CAMERA_CONTROL, data, wait_response=True, timeout=self.timeout)
        return response is not None

    def set_gaze(self, x: int, y: int) -> bool:
        data = x.to_bytes(2, 'little', signed=True) + y.to_bytes(2, 'little', signed=True)
        response = self.send_command(CMD.SET_GAZE, data, wait_response=True, timeout=self.timeout)
        return response is not None


if __name__ == "__main__":
    import sys
    
    protocol = SerialProtocol()
    
    ports = protocol.list_ports()
    print("Available ports:")
    for i, port in enumerate(ports):
        print(f"{i}: {port}")
    
    if not ports:
        print("No serial ports found")
        sys.exit(1)
    
    port_index = int(input("Select port index: ")) if len(ports) > 1 else 0
    port = ports[port_index]
    
    if protocol.connect(port):
        print("Connected successfully")
        
        def on_status(status: Status):
            print(f"Status: state={status.state}, battery={status.battery}, expr={status.expression}")
        
        protocol.register_callback(CMD.GET_STATUS, on_status)
        
        try:
            while True:
                cmd = input("\nEnter command (ping/status/expr/servo/state/exit): ").strip().lower()
                
                if cmd == "exit":
                    break
                elif cmd == "ping":
                    if protocol.ping():
                        print("Ping successful")
                    else:
                        print("Ping failed")
                elif cmd == "status":
                    status = protocol.get_status()
                    if status:
                        print(f"State: {status.state}, Battery: {status.battery}%, "
                              f"Expression: {status.expression}, "
                              f"Servo H: {status.servo_h}, Servo V: {status.servo_v}")
                elif cmd == "expr":
                    expr_id = int(input("Expression ID (0-15): "))
                    protocol.set_expression(expr_id)
                elif cmd == "servo":
                    servo_id = int(input("Servo ID (1=H, 2=V): "))
                    angle = int(input("Angle (0-180): "))
                    protocol.set_servo(servo_id, angle)
                elif cmd == "state":
                    state = int(input("State (1=SLEEP, 2=WAKE, 3=LISTEN, 4=THINK, 5=TALK): "))
                    protocol.set_state(state)
        
        except KeyboardInterrupt:
            pass
        
        protocol.disconnect()
    else:
        print("Failed to connect")

import serial
import time

def test_serial(port, baudrate=115200):
    print(f"Testing serial port: {port} @ {baudrate}")
    
    try:
        ser = serial.Serial(port, baudrate, timeout=2.0)
        print(f"Serial port opened successfully: {port}")
        
        ser.write(b'\xAA\x55\x00\x01\x00\x01\x55')
        print("Sent ping message")
        
        response = ser.read(10)
        if response:
            print(f"Received response: {response.hex()}")
        else:
            print("No response received")
        
        ser.close()
        print("Serial test passed")
        return True
        
    except serial.SerialException as e:
        print(f"Serial test failed: {e}")
        return False

def list_serial_ports():
    print("Available serial ports:")
    ports = serial.tools.list_ports.comports()
    
    for i, port in enumerate(ports):
        print(f"  {i}: {port.device} - {port.description}")
    
    return ports

def main():
    print("=" * 50)
    print("DaShan Hardware Test")
    print("=" * 50)
    
    print("\n1. List available serial ports")
    ports = list_serial_ports()
    
    if not ports:
        print("\nNo serial ports found!")
        return
    
    print("\n2. Test serial communication")
    choice = input("Enter port number or device name (e.g., COM3): ").strip()
    
    if choice.isdigit():
        port = ports[int(choice)].device
    else:
        port = choice
    
    baudrate = input("Enter baudrate (default: 115200): ").strip()
    baudrate = int(baudrate) if baudrate else 115200
    
    test_serial(port, baudrate)

if __name__ == '__main__':
    import serial.tools.list_ports
    main()

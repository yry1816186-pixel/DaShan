import pytest
from host.modules.protocol.serial_com import SerialCommunication, ProtocolFrame


@pytest.fixture
def serial_com():
    com = SerialCommunication(port=None, baudrate=115200)
    yield com


def test_serial_com_initialization(serial_com):
    assert serial_com is not None
    assert serial_com.baudrate == 115200
    assert serial_com.timeout == 2.0


def test_calc_crc8():
    crc = SerialCommunication.calc_crc8(bytes([0x01, 0x02, 0x03]))
    assert isinstance(crc, int)
    assert 0 <= crc <= 255


def test_calc_crc8_same_data():
    data = bytes([0xAA, 0x55, 0x01, 0x02])
    crc1 = SerialCommunication.calc_crc8(data)
    crc2 = SerialCommunication.calc_crc8(data)
    assert crc1 == crc2


def test_build_set_expression_frame(serial_com):
    frame = serial_com.build_set_expression(0x01, 0x05, 100)
    
    assert frame is not None
    assert len(frame) >= 6
    assert frame[0] == 0xAA
    assert frame[1] == 0x55
    assert frame[4] == 0x10


def test_build_servo_move_frame(serial_com):
    frame = serial_com.build_servo_move(0x00, 90, 50)
    
    assert frame is not None
    assert len(frame) >= 6
    assert frame[0] == 0xAA
    assert frame[1] == 0x55
    assert frame[4] == 0x20


def test_build_ping_frame(serial_com):
    frame = serial_com.build_ping()
    
    assert frame is not None
    assert len(frame) >= 6
    assert frame[0] == 0xAA
    assert frame[1] == 0x55
    assert frame[4] == 0x01


def test_build_get_status_frame(serial_com):
    frame = serial_com.build_get_status()
    
    assert frame is not None
    assert len(frame) >= 6
    assert frame[0] == 0xAA
    assert frame[1] == 0x55
    assert frame[4] == 0x60


def test_protocol_frame_dataclass():
    frame = ProtocolFrame(
        sync=bytes([0xAA, 0x55]),
        length=6,
        type=0x10,
        seq=0,
        payload=bytes([0x01, 0x05, 0x64]),
        crc=0x00
    )
    
    assert frame.sync == bytes([0xAA, 0x55])
    assert frame.length == 6
    assert frame.type == 0x10
    assert frame.payload == bytes([0x01, 0x05, 0x64])


def test_crc_calculation_consistency():
    test_data = [
        bytes([0x01, 0x02, 0x03]),
        bytes([0xAA, 0x55, 0xFF, 0x00]),
        bytes([0x00, 0x00, 0x00, 0x00]),
    ]
    
    for data in test_data:
        crc1 = SerialCommunication.calc_crc8(data)
        crc2 = SerialCommunication.calc_crc8(data)
        assert crc1 == crc2


def test_crc_different_data():
    data1 = bytes([0x01, 0x02, 0x03])
    data2 = bytes([0x01, 0x02, 0x04])
    
    crc1 = SerialCommunication.calc_crc8(data1)
    crc2 = SerialCommunication.calc_crc8(data2)
    
    assert crc1 != crc2

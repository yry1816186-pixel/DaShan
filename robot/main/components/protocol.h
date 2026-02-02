#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PROTOCOL_MAX_PAYLOAD    128
#define PROTOCOL_HEADER_SIZE    6
#define PROTOCOL_CRC_SIZE       1
#define PROTOCOL_FRAME_MAX_SIZE (PROTOCOL_HEADER_SIZE + PROTOCOL_MAX_PAYLOAD + PROTOCOL_CRC_SIZE)

#define PROTOCOL_SYNC_BYTE_0    0xAA
#define PROTOCOL_SYNC_BYTE_1    0x55

typedef enum {
    MSG_ACK = 0x00,
    MSG_PING = 0x01,
    MSG_SET_EXPRESSION = 0x10,
    MSG_SET_BRIGHTNESS = 0x11,
    MSG_SERVO_MOVE = 0x20,
    MSG_SERVO_STOP = 0x21,
    MSG_SERVO_CENTER = 0x22,
    MSG_AUDIO_PLAY = 0x30,
    MSG_AUDIO_STOP = 0x31,
    MSG_AUDIO_SET_VOLUME = 0x32,
    MSG_CAMERA_START = 0x40,
    MSG_CAMERA_STOP = 0x41,
    MSG_CAMERA_GET_FRAME = 0x42,
    MSG_SENSOR_GET_DATA = 0x50,
    MSG_SENSOR_START = 0x51,
    MSG_SENSOR_STOP = 0x52,
    MSG_GET_STATUS = 0x60,
    MSG_SET_MODE = 0x61,
    MSG_ERROR = 0xFF
} MessageType;

typedef struct __attribute__((packed)) {
    uint8_t sync[2];
    uint16_t length;
    uint8_t type;
    uint8_t seq;
    uint8_t payload[PROTOCOL_MAX_PAYLOAD];
    uint8_t crc;
} ProtocolFrame;

typedef struct {
    uint8_t expression;
    uint8_t brightness;
} PayloadSetExpression;

typedef struct {
    uint8_t servo_id;
    uint16_t angle;
    uint16_t speed;
} PayloadServoMove;

typedef struct {
    uint16_t length;
    uint8_t data[PROTOCOL_MAX_PAYLOAD];
} PayloadAudioPlay;

typedef struct {
    uint8_t volume;
} PayloadSetVolume;

typedef struct {
    uint16_t distance;
    uint8_t light_level;
    uint8_t touch_state;
    uint8_t battery_level;
} PayloadSensorData;

typedef struct {
    uint8_t mode;
} PayloadSetMode;

typedef enum {
    PROTO_OK = 0,
    PROTO_ERROR_SYNC,
    PROTO_ERROR_CRC,
    PROTO_ERROR_LENGTH,
    PROTO_ERROR_UNKNOWN_MSG
} ProtocolStatus;

typedef struct {
    ProtocolStatus status;
    MessageType msg_type;
    uint16_t payload_length;
    uint8_t seq;
} ProtocolResult;

void protocol_init(void);
uint8_t protocol_calc_crc8(const uint8_t* data, uint16_t length);
ProtocolStatus protocol_parse_frame(const uint8_t* buffer, uint16_t length, ProtocolFrame* frame);
ProtocolStatus protocol_build_frame(ProtocolFrame* frame, MessageType type, const uint8_t* payload, uint16_t payload_len, uint8_t seq);
ProtocolStatus protocol_handle_message(const ProtocolFrame* frame);
void protocol_send_ack(uint8_t seq);
void protocol_send_error(uint8_t seq, uint8_t error_code);

#ifdef __cplusplus
}
#endif

#endif

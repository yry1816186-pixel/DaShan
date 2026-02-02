#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stdbool.h>
#include "freertos/queue.h"

#define FRAME_HEAD 0xAA
#define MAX_DATA_LEN 1024

typedef enum {
    CMD_HEARTBEAT = 0x01,
    CMD_SET_EXPRESSION = 0x02,
    CMD_SET_SERVO = 0x03,
    CMD_PLAY_AUDIO = 0x04,
    CMD_RECORD_AUDIO = 0x05,
    CMD_SEND_IMAGE = 0x06,
    CMD_SET_STATE = 0x07,
    CMD_GET_STATUS = 0x08,
    CMD_SENSOR_DATA = 0x09,
    CMD_RECORD_CONTROL = 0x0A,
    CMD_CAMERA_CONTROL = 0x0B,
    CMD_SET_GAZE = 0x0C,
    CMD_ERROR = 0xFF
} CommandID;

typedef enum {
    STATE_SLEEP = 1,
    STATE_WAKE = 2,
    STATE_LISTEN = 3,
    STATE_THINK = 4,
    STATE_TALK = 5
} RobotState;

typedef enum {
    ERROR_OK = 0,
    ERROR_MEMORY = 1,
    ERROR_TIMEOUT = 2,
    ERROR_SENSOR = 3,
    ERROR_ACTUATOR = 4,
    ERROR_BATTERY_LOW = 5,
    ERROR_OVERHEAT = 6,
    ERROR_INVALID_PARAM = 7
} ErrorCode;

typedef enum {
    COMPONENT_LED = 1,
    COMPONENT_SERVO = 2,
    COMPONENT_CAMERA = 3,
    COMPONENT_AUDIO = 4,
    COMPONENT_SENSOR = 5
} ComponentID;

typedef struct {
    uint8_t head;
    uint8_t cmd;
    uint16_t len;
    uint8_t data[MAX_DATA_LEN];
    uint8_t crc;
} ProtocolFrame;

typedef void (*CommandCallback)(const uint8_t *data, uint16_t len);

typedef struct {
    ProtocolFrame rx_frame;
    uint16_t rx_index;
    bool rx_receiving;
    QueueHandle_t tx_queue;
    CommandCallback callbacks[256];
} ProtocolHandler;

void protocol_init(ProtocolHandler *handler);
uint8_t calc_crc8(const uint8_t *data, uint16_t len);
void protocol_process_data(ProtocolHandler *handler, const uint8_t *data, uint16_t len);
void protocol_send_frame(ProtocolHandler *handler, const ProtocolFrame *frame);
void protocol_send_queued(ProtocolHandler *handler);
void protocol_register_callback(ProtocolHandler *handler, uint8_t cmd, CommandCallback callback);
void protocol_send_response(ProtocolHandler *handler, uint8_t cmd, const uint8_t *data, uint16_t len);
void protocol_send_heartbeat(ProtocolHandler *handler);
void protocol_send_status(ProtocolHandler *handler, RobotState state, uint8_t battery, uint8_t expression, uint16_t servo_h, uint16_t servo_v);
void protocol_send_sensor_data(ProtocolHandler *handler, uint16_t distance, uint8_t proximity, uint8_t light);

#endif

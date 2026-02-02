#include "protocol.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "PROTOCOL";

void protocol_init(ProtocolHandler *handler)
{
    memset(handler, 0, sizeof(ProtocolHandler));
    handler->tx_queue = xQueueCreate(10, sizeof(ProtocolFrame));
    
    for (int i = 0; i < 256; i++) {
        handler->callbacks[i] = NULL;
    }
    
    ESP_LOGI(TAG, "Protocol handler initialized");
}

uint8_t calc_crc8(const uint8_t *data, uint16_t len)
{
    uint8_t crc = 0;
    for (uint16_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : crc << 1;
        }
    }
    return crc & 0xFF;
}

void protocol_process_data(ProtocolHandler *handler, const uint8_t *data, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++) {
        uint8_t byte = data[i];
        
        if (!handler->rx_receiving) {
            if (byte == FRAME_HEAD) {
                handler->rx_receiving = true;
                handler->rx_index = 0;
                handler->rx_frame.head = byte;
            }
            continue;
        }
        
        handler->rx_index++;
        
        switch (handler->rx_index) {
            case 1:
                handler->rx_frame.cmd = byte;
                break;
            case 2:
                handler->rx_frame.len = byte;
                break;
            case 3:
                handler->rx_frame.len |= (byte << 8);
                break;
            default:
                if (handler->rx_index < 4 + handler->rx_frame.len) {
                    handler->rx_frame.data[handler->rx_index - 4] = byte;
                } else if (handler->rx_index == 4 + handler->rx_frame.len) {
                    handler->rx_frame.crc = byte;
                    
                    uint8_t calc_crc = calc_crc8((uint8_t *)&handler->rx_frame, 4 + handler->rx_frame.len);
                    
                    if (calc_crc == handler->rx_frame.crc) {
                        ESP_LOGD(TAG, "Received frame: CMD=0x%02X, LEN=%d", 
                                  handler->rx_frame.cmd, handler->rx_frame.len);
                        
                        if (handler->callbacks[handler->rx_frame.cmd]) {
                            handler->callbacks[handler->rx_frame.cmd](
                                handler->rx_frame.data, 
                                handler->rx_frame.len
                            );
                        } else {
                            ESP_LOGW(TAG, "No callback for CMD: 0x%02X", handler->rx_frame.cmd);
                        }
                    } else {
                        ESP_LOGW(TAG, "CRC mismatch: expected 0x%02X, got 0x%02X", 
                                  calc_crc, handler->rx_frame.crc);
                    }
                    
                    handler->rx_receiving = false;
                    handler->rx_index = 0;
                }
                break;
        }
        
        if (handler->rx_index >= 4 + MAX_DATA_LEN + 1) {
            ESP_LOGW(TAG, "Frame too long, resetting");
            handler->rx_receiving = false;
            handler->rx_index = 0;
        }
    }
}

void protocol_send_frame(ProtocolHandler *handler, const ProtocolFrame *frame)
{
    xQueueSend(handler->tx_queue, frame, pdMS_TO_TICKS(100));
}

void protocol_send_queued(ProtocolHandler *handler)
{
    ProtocolFrame frame;
    while (xQueueReceive(handler->tx_queue, &frame, 0) == pdTRUE) {
        uint16_t total_len = 5 + frame.len;
        uint8_t buffer[5 + MAX_DATA_LEN];
        
        buffer[0] = frame.head;
        buffer[1] = frame.cmd;
        buffer[2] = frame.len & 0xFF;
        buffer[3] = (frame.len >> 8) & 0xFF;
        memcpy(&buffer[4], frame.data, frame.len);
        buffer[4 + frame.len] = frame.crc;
        
        uart_write_bytes(UART_NUM, (const char *)buffer, total_len);
        
        ESP_LOGD(TAG, "Sent frame: CMD=0x%02X, LEN=%d", frame.cmd, frame.len);
    }
}

void protocol_register_callback(ProtocolHandler *handler, uint8_t cmd, CommandCallback callback)
{
    handler->callbacks[cmd] = callback;
    ESP_LOGD(TAG, "Registered callback for CMD: 0x%02X", cmd);
}

void protocol_send_response(ProtocolHandler *handler, uint8_t cmd, const uint8_t *data, uint16_t len)
{
    ProtocolFrame frame;
    frame.head = FRAME_HEAD;
    frame.cmd = cmd;
    frame.len = len;
    memcpy(frame.data, data, len);
    frame.crc = calc_crc8((uint8_t *)&frame, 4 + len);
    
    protocol_send_frame(handler, &frame);
}

void protocol_send_heartbeat(ProtocolHandler *handler)
{
    uint8_t data[8];
    uint32_t uptime = esp_timer_get_time() / 1000000;
    uint32_t free_heap = esp_get_free_heap_size();
    
    memcpy(&data[0], &uptime, 4);
    memcpy(&data[4], &free_heap, 4);
    
    protocol_send_response(handler, CMD_HEARTBEAT, data, 8);
}

void protocol_send_status(ProtocolHandler *handler, RobotState state, uint8_t battery, 
                         uint8_t expression, uint16_t servo_h, uint16_t servo_v)
{
    uint8_t data[9];
    data[0] = state;
    data[1] = battery;
    data[2] = expression;
    memcpy(&data[3], &servo_h, 2);
    memcpy(&data[5], &servo_v, 2);
    
    protocol_send_response(handler, CMD_GET_STATUS, data, 9);
}

void protocol_send_sensor_data(ProtocolHandler *handler, uint16_t distance, 
                             uint8_t proximity, uint8_t light)
{
    uint8_t data[4];
    memcpy(&data[0], &distance, 2);
    data[2] = proximity;
    data[3] = light;
    
    protocol_send_response(handler, CMD_SENSOR_DATA, data, 4);
}

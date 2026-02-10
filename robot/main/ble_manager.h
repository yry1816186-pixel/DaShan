#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_gap_ble_api.h"
#include "esp_gatts_api.h"

#define BLE_DEVICE_NAME "DaShan-Robot"
#define BLE_MTU_SIZE 512
#define BLE_MAX_CONNECTIONS 1

typedef enum {
    BLE_SERVICE_MAIN = 0x1800,
    BLE_SERVICE_CUSTOM = 0x180A
} ble_service_t;

typedef enum {
    BLE_CHAR_COMMAND = 0x2A00,
    BLE_CHAR_STATUS = 0x2A01,
    BLE_CHAR_DATA = 0x2A02,
    BLE_CHAR_CONFIG = 0x2A03
} ble_char_t;

typedef enum {
    BLE_CMD_PING = 0x00,
    BLE_CMD_SET_EXPRESSION = 0x01,
    BLE_CMD_SET_SERVO = 0x02,
    BLE_CMD_GET_STATUS = 0x03,
    BLE_CMD_START_OTA = 0x04,
    BLE_CMD_RESTART = 0x05,
    BLE_CMD_PLAY_AUDIO = 0x06
} ble_command_t;

typedef struct {
    ble_command_t cmd;
    uint8_t *data;
    uint16_t data_len;
} ble_packet_t;

typedef void (*ble_data_callback_t)(const uint8_t *data, uint16_t len);
typedef void (*ble_connected_callback_t)(bool connected);

typedef struct {
    bool initialized;
    bool connected;
    uint16_t conn_id;
    uint16_t mtu;
    
    ble_data_callback_t data_callback;
    ble_connected_callback_t connected_callback;
} ble_manager_t;

esp_err_t ble_manager_init(void);
esp_err_t ble_manager_deinit(void);
esp_err_t ble_manager_start(void);
esp_err_t ble_manager_stop(void);
esp_err_t ble_manager_send_data(uint16_t char_handle, const uint8_t *data, uint16_t len);
esp_err_t ble_manager_send_status(const char *status_msg);
esp_err_t ble_manager_notify(const uint8_t *data, uint16_t len);

void ble_manager_set_data_callback(ble_data_callback_t callback);
void ble_manager_set_connected_callback(ble_connected_callback_t callback);
bool ble_manager_is_connected(void);
uint16_t ble_manager_get_mtu(void);

#endif

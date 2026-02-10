#ifndef OTA_MANAGER_H
#define OTA_MANAGER_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_http_client.h"
#include "esp_ota_ops.h"

#define OTA_URL_MAX_LEN 256
#define OTA_BUFFER_SIZE 4096
#define OTA_TIMEOUT_MS 10000

typedef enum {
    OTA_STATE_IDLE = 0,
    OTA_STATE_DOWNLOADING,
    OTA_STATE_WRITING,
    OTA_STATE_VERIFYING,
    OTA_STATE_REBOOTING,
    OTA_STATE_ERROR
} ota_state_t;

typedef enum {
    OTA_SUCCESS = 0,
    OTA_ERROR_INVALID_URL,
    OTA_ERROR_CONNECT_FAILED,
    OTA_ERROR_DOWNLOAD_FAILED,
    OTA_ERROR_WRITE_FAILED,
    OTA_ERROR_VERIFY_FAILED,
    OTA_ERROR_INSUFFICIENT_SPACE,
    OTA_ERROR_PARTITION_ERROR
} ota_error_t;

typedef struct {
    ota_state_t state;
    ota_error_t last_error;
    uint32_t bytes_received;
    uint32_t total_bytes;
    uint32_t percent_complete;
    char current_url[OTA_URL_MAX_LEN];
    bool auto_reboot;
    bool verify_checksum;
    uint32_t expected_checksum;
    uint32_t calculated_checksum;
} ota_status_t;

typedef void (*ota_progress_callback_t)(ota_status_t *status);
typedef void (*ota_complete_callback_t)(ota_error_t result);

typedef struct {
    bool initialized;
    const esp_partition_t *update_partition;
    esp_ota_handle_t update_handle;
    ota_status_t status;
    ota_progress_callback_t progress_callback;
    ota_complete_callback_t complete_callback;
} ota_manager_t;

esp_err_t ota_manager_init(void);
esp_err_t ota_manager_deinit(void);
esp_err_t ota_manager_start_update(const char *firmware_url, bool auto_reboot);
esp_err_t ota_manager_cancel_update(void);
ota_state_t ota_manager_get_state(void);
ota_status_t ota_manager_get_status(void);
const char *ota_manager_get_state_string(ota_state_t state);
const char *ota_manager_get_error_string(ota_error_t error);
void ota_manager_set_progress_callback(ota_progress_callback_t callback);
void ota_manager_set_complete_callback(ota_complete_callback_t callback);
bool ota_manager_is_updating(void);
uint32_t ota_manager_get_free_space(void);
bool ota_manager_check_url(const char *url);

#endif

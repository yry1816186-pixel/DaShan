#include "ota_manager.h"
#include <string.h>
#include <sys/param.h>
#include "esp_log.h"
#include "esp_http_client.h"
#include "esp_ota_ops.h"
#include "esp_app_format.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_crc.h"

static const char *TAG = "OTA_MGR";

static ota_manager_t ota_mgr = {0};
static TaskHandle_t ota_task_handle = NULL;

static const char *ota_state_strings[] = {
    "IDLE",
    "DOWNLOADING",
    "WRITING",
    "VERIFYING",
    "REBOOTING",
    "ERROR"
};

static const char *ota_error_strings[] = {
    "SUCCESS",
    "INVALID_URL",
    "CONNECT_FAILED",
    "DOWNLOAD_FAILED",
    "WRITE_FAILED",
    "VERIFY_FAILED",
    "INSUFFICIENT_SPACE",
    "PARTITION_ERROR"
};

static void ota_task(void *pvParameters);
static esp_err_t http_event_handler(esp_http_client_event_t evt);

static esp_err_t http_event_handler(esp_http_client_event_t evt) {
    switch (evt) {
        case HTTP_EVENT_ERROR:
            ESP_LOGE(TAG, "HTTP_EVENT_ERROR");
            break;
            
        case HTTP_EVENT_ON_CONNECTED:
            ESP_LOGI(TAG, "HTTP_EVENT_ON_CONNECTED");
            break;
            
        case HTTP_EVENT_HEADER_SENT:
            ESP_LOGI(TAG, "HTTP_EVENT_HEADER_SENT");
            break;
            
        case HTTP_EVENT_ON_HEADER:
            ESP_LOGD(TAG, "HTTP_EVENT_ON_HEADER, key=%s, value=%s",
                     evt->header_key, evt->header_value);
            
            if (strcmp(evt->header_key, "Content-Length") == 0) {
                ota_mgr.status.total_bytes = atoi(evt->header_value);
            }
            break;
            
        case HTTP_EVENT_ON_DATA:
            ota_mgr.status.bytes_received += evt->data_len;
            ota_mgr.status.percent_complete = 
                (ota_mgr.status.bytes_received * 100) / ota_mgr.status.total_bytes;
            
            if (ota_mgr.progress_callback) {
                ota_mgr.progress_callback(&ota_mgr.status);
            }
            
            if (ota_mgr.update_handle != NULL) {
                esp_err_t err = esp_ota_write(ota_mgr.update_handle, 
                                               evt->data, evt->data_len);
                if (err != ESP_OK) {
                    ESP_LOGE(TAG, "OTA write failed: %d", err);
                    ota_mgr.status.last_error = OTA_ERROR_WRITE_FAILED;
                    ota_mgr.status.state = OTA_STATE_ERROR;
                }
            }
            break;
            
        case HTTP_EVENT_ON_FINISH:
            ESP_LOGI(TAG, "HTTP_EVENT_ON_FINISH");
            break;
            
        case HTTP_EVENT_DISCONNECTED:
            ESP_LOGI(TAG, "HTTP_EVENT_DISCONNECTED");
            break;
            
        case HTTP_EVENT_REDIRECT:
            ESP_LOGI(TAG, "HTTP_EVENT_REDIRECT");
            break;
    }
    return ESP_OK;
}

static void ota_task(void *pvParameters) {
    char *firmware_url = (char *)pvParameters;
    esp_err_t err;
    
    ESP_LOGI(TAG, "Starting OTA update from: %s", firmware_url);
    
    ota_mgr.update_partition = esp_ota_get_next_update_partition(NULL);
    if (ota_mgr.update_partition == NULL) {
        ESP_LOGE(TAG, "No OTA update partition found");
        ota_mgr.status.last_error = OTA_ERROR_PARTITION_ERROR;
        ota_mgr.status.state = OTA_STATE_ERROR;
        goto ota_end;
    }
    
    ESP_LOGI(TAG, "Writing to partition: %s", ota_mgr.update_partition->label);
    
    err = esp_ota_begin(ota_mgr.update_partition, OTA_SIZE_UNKNOWN, &ota_mgr.update_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "OTA begin failed: %d", err);
        ota_mgr.status.last_error = OTA_ERROR_WRITE_FAILED;
        ota_mgr.status.state = OTA_STATE_ERROR;
        goto ota_end;
    }
    
    esp_http_client_config_t http_config = {
        .url = firmware_url,
        .event_handler = http_event_handler,
        .timeout_ms = OTA_TIMEOUT_MS,
        .buffer_size = OTA_BUFFER_SIZE,
        .buffer_size_tx = OTA_BUFFER_SIZE,
        .user_agent = "DaShan-Robot-OTA/1.0",
        .disable_auto_redirect = false,
        .max_redirections = 5,
        .keep_alive_enable = true,
        .keep_alive_idle = 5,
        .keep_alive_interval = 5,
        .crt_bundle_attach = NULL,
        .is_async = false,
        .use_global_ca_store = true,
    };
    
    ota_mgr.status.state = OTA_STATE_DOWNLOADING;
    ota_mgr.status.bytes_received = 0;
    ota_mgr.status.total_bytes = 0;
    ota_mgr.status.percent_complete = 0;
    
    esp_http_client_handle_t client = esp_http_client_init(&http_config);
    if (client == NULL) {
        ESP_LOGE(TAG, "Failed to initialize HTTP client");
        ota_mgr.status.last_error = OTA_ERROR_CONNECT_FAILED;
        ota_mgr.status.state = OTA_STATE_ERROR;
        goto ota_end;
    }
    
    err = esp_http_client_perform(client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "HTTP perform failed: %d", err);
        ota_mgr.status.last_error = OTA_ERROR_DOWNLOAD_FAILED;
        ota_mgr.status.state = OTA_STATE_ERROR;
        esp_http_client_cleanup(client);
        goto ota_end;
    }
    
    esp_http_client_cleanup(client);
    
    ota_mgr.status.state = OTA_STATE_WRITING;
    
    err = esp_ota_end(ota_mgr.update_handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "OTA end failed: %d", err);
        ota_mgr.status.last_error = OTA_ERROR_WRITE_FAILED;
        ota_mgr.status.state = OTA_STATE_ERROR;
        goto ota_end;
    }
    
    ota_mgr.status.state = OTA_STATE_VERIFYING;
    
    err = esp_ota_set_boot_partition(ota_mgr.update_partition);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Set boot partition failed: %d", err);
        ota_mgr.status.last_error = OTA_ERROR_VERIFY_FAILED;
        ota_mgr.status.state = OTA_STATE_ERROR;
        goto ota_end;
    }
    
    ESP_LOGI(TAG, "OTA update successful!");
    ota_mgr.status.state = OTA_STATE_REBOOTING;
    
    if (ota_mgr.complete_callback) {
        ota_mgr.complete_callback(OTA_SUCCESS);
    }
    
    if (ota_mgr.status.auto_reboot) {
        ESP_LOGI(TAG, "Rebooting in 3 seconds...");
        vTaskDelay(pdMS_TO_TICKS(3000));
        esp_restart();
    }
    
ota_end:
    if (ota_mgr.complete_callback && ota_mgr.status.state == OTA_STATE_ERROR) {
        ota_mgr.complete_callback(ota_mgr.status.last_error);
    }
    
    ota_mgr.update_handle = NULL;
    ota_task_handle = NULL;
    vTaskDelete(NULL);
}

esp_err_t ota_manager_init(void) {
    if (ota_mgr.initialized) {
        ESP_LOGW(TAG, "OTA manager already initialized");
        return ESP_OK;
    }
    
    memset(&ota_mgr, 0, sizeof(ota_manager_t));
    
    const esp_partition_t *running = esp_ota_get_running_partition();
    ESP_LOGI(TAG, "Running partition: %s", running->label);
    
    ota_mgr.update_partition = esp_ota_get_next_update_partition(NULL);
    if (ota_mgr.update_partition) {
        ESP_LOGI(TAG, "Next update partition: %s, size: %d bytes",
                 ota_mgr.update_partition->label,
                 ota_mgr.update_partition->size);
    }
    
    ota_mgr.initialized = true;
    ota_mgr.status.state = OTA_STATE_IDLE;
    
    ESP_LOGI(TAG, "OTA manager initialized");
    return ESP_OK;
}

esp_err_t ota_manager_deinit(void) {
    if (!ota_mgr.initialized) {
        return ESP_OK;
    }
    
    if (ota_mgr.status.state == OTA_STATE_DOWNLOADING ||
        ota_mgr.status.state == OTA_STATE_WRITING) {
        ota_manager_cancel_update();
    }
    
    ota_mgr.initialized = false;
    
    ESP_LOGI(TAG, "OTA manager deinitialized");
    return ESP_OK;
}

esp_err_t ota_manager_start_update(const char *firmware_url, bool auto_reboot) {
    if (!ota_mgr.initialized) {
        ESP_LOGE(TAG, "OTA manager not initialized");
        return ESP_ERR_INVALID_STATE;
    }
    
    if (ota_mgr.status.state != OTA_STATE_IDLE) {
        ESP_LOGW(TAG, "OTA update already in progress");
        return ESP_ERR_INVALID_STATE;
    }
    
    if (!ota_manager_check_url(firmware_url)) {
        ESP_LOGE(TAG, "Invalid OTA URL: %s", firmware_url);
        return ESP_ERR_INVALID_ARG;
    }
    
    uint32_t free_space = ota_manager_get_free_space();
    if (free_space < 100000) {
        ESP_LOGE(TAG, "Insufficient space for OTA: %d bytes", free_space);
        return ESP_ERR_NO_MEM;
    }
    
    strncpy(ota_mgr.status.current_url, firmware_url, OTA_URL_MAX_LEN - 1);
    ota_mgr.status.current_url[OTA_URL_MAX_LEN - 1] = '\0';
    ota_mgr.status.auto_reboot = auto_reboot;
    
    BaseType_t ret = xTaskCreate(ota_task, "ota_task", 8192, 
                                  (void *)firmware_url, 5, &ota_task_handle);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create OTA task");
        return ESP_ERR_NO_MEM;
    }
    
    ESP_LOGI(TAG, "OTA update task started");
    return ESP_OK;
}

esp_err_t ota_manager_cancel_update(void) {
    if (ota_task_handle == NULL) {
        return ESP_ERR_INVALID_STATE;
    }
    
    ESP_LOGI(TAG, "Cancelling OTA update");
    
    if (ota_mgr.update_handle != NULL) {
        esp_ota_abort(ota_mgr.update_handle);
        ota_mgr.update_handle = NULL;
    }
    
    ota_mgr.status.state = OTA_STATE_IDLE;
    ota_mgr.status.last_error = OTA_ERROR_DOWNLOAD_FAILED;
    
    vTaskDelay(pdMS_TO_TICKS(100));
    
    return ESP_OK;
}

ota_state_t ota_manager_get_state(void) {
    return ota_mgr.status.state;
}

ota_status_t ota_manager_get_status(void) {
    return ota_mgr.status;
}

const char *ota_manager_get_state_string(ota_state_t state) {
    if (state >= sizeof(ota_state_strings) / sizeof(ota_state_strings[0])) {
        return "UNKNOWN";
    }
    return ota_state_strings[state];
}

const char *ota_manager_get_error_string(ota_error_t error) {
    if (error >= sizeof(ota_error_strings) / sizeof(ota_error_strings[0])) {
        return "UNKNOWN";
    }
    return ota_error_strings[error];
}

void ota_manager_set_progress_callback(ota_progress_callback_t callback) {
    ota_mgr.progress_callback = callback;
}

void ota_manager_set_complete_callback(ota_complete_callback_t callback) {
    ota_mgr.complete_callback = callback;
}

bool ota_manager_is_updating(void) {
    return (ota_mgr.status.state == OTA_STATE_DOWNLOADING ||
            ota_mgr.status.state == OTA_STATE_WRITING ||
            ota_mgr.status.state == OTA_STATE_VERIFYING);
}

uint32_t ota_manager_get_free_space(void) {
    if (ota_mgr.update_partition == NULL) {
        return 0;
    }
    return ota_mgr.update_partition->size;
}

bool ota_manager_check_url(const char *url) {
    if (url == NULL || strlen(url) == 0) {
        return false;
    }
    
    if (strlen(url) > OTA_URL_MAX_LEN - 1) {
        return false;
    }
    
    if (strncmp(url, "http://", 7) != 0 && strncmp(url, "https://", 8) != 0) {
        return false;
    }
    
    const char *bin_ext = strstr(url, ".bin");
    if (bin_ext == NULL) {
        return false;
    }
    
    return true;
}

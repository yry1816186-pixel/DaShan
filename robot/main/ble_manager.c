#include "ble_manager.h"
#include <string.h>
#include "esp_log.h"
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gap_ble_api.h"
#include "esp_gatts_api.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "BLE_MGR";

static ble_manager_t ble_mgr = {0};

static uint16_t ble_service_handle = 0;
static uint16_t ble_char_handles[4] = {0};

static uint8_t adv_config_flags = ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_BREDR_NOT_SPT;

static esp_ble_adv_params_t adv_params = {
    .adv_int_min = 0x20,
    .adv_int_max = 0x40,
    .adv_type = ADV_TYPE_IND,
    .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
    .peer_addr_type = BLE_ADDR_TYPE_PUBLIC,
    .channel_map = ADV_CHNL_ALL,
    .adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
};

static uint8_t adv_data_raw[31] = {
    0x02, 0x01, 0x06,
    0x03, 0x03, 0x0A, 0x18,
    0x0A, strlen(BLE_DEVICE_NAME)
};
static uint8_t scan_rsp_data[31] = {0};

static esp_ble_adv_data_t adv_data = {
    .set_scan_rsp = true,
    .include_name = true,
    .include_txpower = true,
    .min_interval = 0x20,
    .max_interval = 0x40,
    .appearance = 0x0000,
    .manufacturer_len = 0,
    .p_manufacturer_data = NULL,
    .service_data_len = 0,
    .p_service_data = NULL,
    .service_uuid_len = sizeof(uint16_t),
    .p_service_uuid = (uint8_t *)&ble_service_t,
    .flag = adv_config_flags
};

static const uint8_t SERVICE_UUID128[16] = {
    0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
    0x88, 0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF
};

static void gap_event_handler(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param) {
    switch (event) {
        case ESP_GAP_BLE_ADV_DATA_SET_COMPLETE_EVT:
            ESP_LOGI(TAG, "BLE advertising data set complete");
            break;
            
        case ESP_GAP_BLE_SCAN_PARAM_SET_COMPLETE_EVT:
            ESP_LOGI(TAG, "BLE scan parameters set complete");
            break;
            
        case ESP_GAP_BLE_SCAN_RESULT_EVT:
            break;
            
        case ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT:
            ESP_LOGI(TAG, "BLE raw advertising data set complete");
            break;
            
        case ESP_GAP_BLE_SCAN_START_COMPLETE_EVT:
            ESP_LOGI(TAG, "BLE scan started");
            break;
            
        case ESP_GAP_BLE_SCAN_STOP_COMPLETE_EVT:
            ESP_LOGI(TAG, "BLE scan stopped");
            break;
            
        case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
            if (param->adv_start_cmpl.status != ESP_BT_STATUS_SUCCESS) {
                ESP_LOGE(TAG, "Advertising start failed: %d", param->adv_start_cmpl.status);
            } else {
                ESP_LOGI(TAG, "Advertising started successfully");
            }
            break;
            
        case ESP_GAP_BLE_ADV_STOP_COMPLETE_EVT:
            if (param->adv_stop_cmpl.status != ESP_BT_STATUS_SUCCESS) {
                ESP_LOGE(TAG, "Advertising stop failed: %d", param->adv_stop_cmpl.status);
            } else {
                ESP_LOGI(TAG, "Advertising stopped successfully");
            }
            break;
            
        case ESP_GAP_BLE_UPDATE_CONN_PARAMS_EVT:
            ESP_LOGI(TAG, "Connection parameters updated");
            break;
            
        case ESP_GAP_BLE_SET_LOCAL_PRIVACY_COMPLETE_EVT:
            ESP_LOGI(TAG, "Local privacy set complete");
            break;
            
        case ESP_GAP_BLE_REMOVE_BOND_DEV_COMPLETE_EVT:
            ESP_LOGI(TAG, "Bond device removed");
            break;
            
        case ESP_GAP_BLE_CLEAR_BOND_DEV_COMPLETE_EVT:
            ESP_LOGI(TAG, "All bonds cleared");
            break;
            
        case ESP_GAP_BLE_CONNECTION_PARAM_UPDATE_EVT:
            ESP_LOGI(TAG, "Connection parameter update request");
            break;
            
        case ESP_GAP_BLE_GET_BOND_DEV_COMPLETE_EVT:
            ESP_LOGI(TAG, "Get bonded devices complete");
            break;
            
        default:
            break;
    }
}

static void gatts_profile_event_handler(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                                     esp_ble_gatts_cb_param_t *param) {
    switch (event) {
        case ESP_GATTS_REG_EVT: {
            if (param->reg.status == ESP_GATT_OK) {
                ble_service_handle = param->reg.app_id;
                ESP_LOGI(TAG, "GATTS app registered, app_id %d", ble_service_handle);
            } else {
                ESP_LOGE(TAG, "GATTS register failed, error %d", param->reg.status);
            }
            break;
        }
        
        case ESP_GATTS_READ_EVT: {
            ESP_LOGD(TAG, "GATTS read event, handle %d", param->read.handle);
            break;
        }
        
        case ESP_GATTS_WRITE_EVT: {
            ESP_LOGI(TAG, "GATTS write event, handle %d, len %d", 
                     param->write.handle, param->write.len);
            
            if (ble_mgr.data_callback) {
                ble_mgr.data_callback(param->write.value, param->write.len);
            }
            break;
        }
        
        case ESP_GATTS_EXEC_WRITE_EVT: {
            ESP_LOGI(TAG, "GATTS execute write event");
            break;
        }
        
        case ESP_GATTS_MTU_EVT: {
            ble_mgr.mtu = param->mtu;
            ESP_LOGI(TAG, "MTU updated: %d", ble_mgr.mtu);
            break;
        }
        
        case ESP_GATTS_CONF_EVT: {
            ESP_LOGI(TAG, "GATTS configuration confirmed");
            break;
        }
        
        case ESP_GATTS_UNREG_EVT: {
            ESP_LOGI(TAG, "GATTS unregistered");
            break;
        }
        
        case ESP_GATTS_CREATE_EVT: {
            ESP_LOGI(TAG, "GATTS service created");
            break;
        }
        
        case ESP_GATTS_ADD_CHAR_EVT: {
            if (param->add_char.status == ESP_GATT_OK) {
                ble_char_handles[param->add_char.attr_handle] = param->add_char.char_handle;
                ESP_LOGI(TAG, "Characteristic added, handle %d", param->add_char.char_handle);
            }
            break;
        }
        
        case ESP_GATTS_START_EVT: {
            ESP_LOGI(TAG, "GATTS service started");
            break;
        }
        
        case ESP_GATTS_CONNECT_EVT: {
            ble_mgr.connected = true;
            ble_mgr.conn_id = param->connect.conn_id;
            ble_mgr.mtu = param->connect.mtu;
            
            ESP_LOGI(TAG, "Device connected, conn_id %d, MTU %d", ble_mgr.conn_id, ble_mgr.mtu);
            
            if (ble_mgr.connected_callback) {
                ble_mgr.connected_callback(true);
            }
            break;
        }
        
        case ESP_GATTS_DISCONNECT_EVT: {
            ble_mgr.connected = false;
            ble_mgr.conn_id = 0;
            
            ESP_LOGI(TAG, "Device disconnected");
            
            if (ble_mgr.connected_callback) {
                ble_mgr.connected_callback(false);
            }
            break;
        }
        
        case ESP_GATTS_OPEN_EVT: {
            ESP_LOGI(TAG, "GATTS connection opened");
            break;
        }
        
        case ESP_GATTS_CANCEL_OPEN_EVT: {
            ESP_LOGI(TAG, "GATTS connection cancelled");
            break;
        }
        
        case ESP_GATTS_CLOSE_EVT: {
            ESP_LOGI(TAG, "GATTS connection closed");
            break;
        }
        
        default:
            break;
    }
}

esp_err_t ble_manager_init(void) {
    esp_err_t ret;
    
    if (ble_mgr.initialized) {
        ESP_LOGW(TAG, "BLE already initialized");
        return ESP_OK;
    }
    
    ESP_LOGI(TAG, "Initializing BLE manager");
    
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ret = esp_bt_controller_init(&bt_cfg);
    if (ret) {
        ESP_LOGE(TAG, "BT controller init failed: %d", ret);
        return ret;
    }
    
    ret = esp_bt_controller_enable(ESP_BT_MODE_BLE);
    if (ret) {
        ESP_LOGE(TAG, "BT controller enable failed: %d", ret);
        return ret;
    }
    
    ret = esp_bluedroid_init();
    if (ret) {
        ESP_LOGE(TAG, "Bluedroid init failed: %d", ret);
        return ret;
    }
    
    ret = esp_bluedroid_enable();
    if (ret) {
        ESP_LOGE(TAG, "Bluedroid enable failed: %d", ret);
        return ret;
    }
    
    esp_ble_gatts_register_callback(gatts_profile_event_handler);
    esp_ble_gap_register_callback(gap_event_handler);
    
    memcpy(&adv_data_raw[5], BLE_DEVICE_NAME, strlen(BLE_DEVICE_NAME));
    
    ret = esp_ble_gap_config_adv_data_raw(&adv_data_raw[0], sizeof(adv_data_raw));
    if (ret) {
        ESP_LOGE(TAG, "Config raw adv data failed: %d", ret);
        return ret;
    }
    
    ret = esp_ble_gap_config_adv_data_raw(scan_rsp_data, sizeof(scan_rsp_data));
    if (ret) {
        ESP_LOGE(TAG, "Config raw scan response data failed: %d", ret);
        return ret;
    }
    
    esp_gatt_srvc_id_t gatts_service_id = {
        .is_primary = true,
        .inst_id = 0,
        .app_id = 0
    };
    
    ble_char_t char_uuids[] = {BLE_CHAR_COMMAND, BLE_CHAR_STATUS, BLE_CHAR_DATA, BLE_CHAR_CONFIG};
    
    esp_gatts_incl_svc_desc_t incl_svc = {0};
    
    for (int i = 0; i < 4; i++) {
        esp_bt_uuid_t char_uuid = {
            .len = ESP_UUID_LEN_16,
            .uuid.uuid16 = char_uuids[i]
        };
        
        esp_gatt_char_prop_t char_props = {
            .bit = 0,
            .read = true,
            .write = true,
            .notify = (i == BLE_CHAR_STATUS) ? true : false,
            .indicate = false
        };
        
        ret = esp_ble_gatts_add_char(
            ble_service_handle,
            &gatts_service_id,
            &char_uuid,
            &char_props,
            NULL,
            NULL
        );
        
        if (ret) {
            ESP_LOGE(TAG, "Add characteristic failed: %d", ret);
            return ret;
        }
    }
    
    ble_mgr.initialized = true;
    ESP_LOGI(TAG, "BLE manager initialized successfully");
    
    return ESP_OK;
}

esp_err_t ble_manager_deinit(void) {
    if (!ble_mgr.initialized) {
        return ESP_OK;
    }
    
    esp_err_t ret = esp_ble_gatts_stop_service(ble_service_handle);
    if (ret) {
        ESP_LOGE(TAG, "Stop service failed: %d", ret);
    }
    
    ret = esp_bluedroid_disable();
    if (ret) {
        ESP_LOGE(TAG, "Bluedroid disable failed: %d", ret);
    }
    
    ret = esp_bluedroid_deinit();
    if (ret) {
        ESP_LOGE(TAG, "Bluedroid deinit failed: %d", ret);
    }
    
    ret = esp_bt_controller_disable();
    if (ret) {
        ESP_LOGE(TAG, "BT controller disable failed: %d", ret);
    }
    
    ret = esp_bt_controller_deinit();
    if (ret) {
        ESP_LOGE(TAG, "BT controller deinit failed: %d", ret);
    }
    
    ble_mgr.initialized = false;
    ble_mgr.connected = false;
    
    ESP_LOGI(TAG, "BLE manager deinitialized");
    return ESP_OK;
}

esp_err_t ble_manager_start(void) {
    if (!ble_mgr.initialized) {
        ESP_LOGE(TAG, "BLE not initialized");
        return ESP_ERR_INVALID_STATE;
    }
    
    esp_err_t ret = esp_ble_gap_start_advertising(&adv_params);
    if (ret) {
        ESP_LOGE(TAG, "Start advertising failed: %d", ret);
        return ret;
    }
    
    ESP_LOGI(TAG, "BLE advertising started");
    return ESP_OK;
}

esp_err_t ble_manager_stop(void) {
    esp_err_t ret = esp_ble_gap_stop_advertising();
    if (ret) {
        ESP_LOGE(TAG, "Stop advertising failed: %d", ret);
        return ret;
    }
    
    ESP_LOGI(TAG, "BLE advertising stopped");
    return ESP_OK;
}

esp_err_t ble_manager_send_data(uint16_t char_handle, const uint8_t *data, uint16_t len) {
    if (!ble_mgr.connected) {
        ESP_LOGW(TAG, "BLE not connected");
        return ESP_ERR_INVALID_STATE;
    }
    
    if (len > ble_mgr.mtu - 3) {
        len = ble_mgr.mtu - 3;
    }
    
    esp_err_t ret = esp_ble_gatts_send_indicate(
        ble_service_handle,
        ble_mgr.conn_id,
        char_handle,
        len,
        data,
        false
    );
    
    if (ret) {
        ESP_LOGE(TAG, "Send data failed: %d", ret);
        return ret;
    }
    
    return ESP_OK;
}

esp_err_t ble_manager_send_status(const char *status_msg) {
    uint16_t len = strlen(status_msg);
    return ble_manager_send_data(ble_char_handles[BLE_CHAR_STATUS], 
                                   (const uint8_t *)status_msg, len);
}

esp_err_t ble_manager_notify(const uint8_t *data, uint16_t len) {
    if (!ble_mgr.connected) {
        return ESP_ERR_INVALID_STATE;
    }
    
    esp_err_t ret = esp_ble_gatts_send_indicate(
        ble_service_handle,
        ble_mgr.conn_id,
        ble_char_handles[BLE_CHAR_STATUS],
        len,
        data,
        false
    );
    
    return ret;
}

void ble_manager_set_data_callback(ble_data_callback_t callback) {
    ble_mgr.data_callback = callback;
}

void ble_manager_set_connected_callback(ble_connected_callback_t callback) {
    ble_mgr.connected_callback = callback;
}

bool ble_manager_is_connected(void) {
    return ble_mgr.connected;
}

uint16_t ble_manager_get_mtu(void) {
    return ble_mgr.mtu;
}

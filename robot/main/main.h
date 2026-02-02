#ifndef MAIN_H
#define MAIN_H

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifdef __cplusplus
extern "C" {
#endif

#define APP_NAME    "DaShan Robot"
#define APP_VERSION "1.0.0"
#define TAG         APP_NAME

#define ESP_OK_CHECK(x) do { \
    esp_err_t __err = (x); \
    if (__err != ESP_OK) { \
        ESP_LOGE(TAG, "Error at %s:%d: %s", __FILE__, __LINE__, esp_err_to_name(__err)); \
        return __err; \
    } \
} while(0)

void app_main(void);

#ifdef __cplusplus
}
#endif

#endif

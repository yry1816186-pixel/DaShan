#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/i2s.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"

#include "protocol.h"
#include "led_matrix.h"
#include "servo.h"
#include "state_machine.h"
#include "camera.h"
#include "audio.h"
#include "sensor.h"

#define UART_NUM UART_NUM_0
#define UART_BAUD_RATE 115200
#define UART_TX_PIN GPIO_NUM_1
#define UART_RX_PIN GPIO_NUM_3

static const char *TAG = "DASHAN";

QueueHandle_t uart_queue;
ProtocolHandler protocol_handler;

void app_main(void)
{
    ESP_LOGI(TAG, "DaShan Robot Starting...");
    
    protocol_init(&protocol_handler);
    
    led_matrix_init();
    servo_init();
    state_machine_init();
    audio_init();
    sensor_init();
    
    uart_config_t uart_config = {
        .baud_rate = UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM, 4096, 4096, 10, &uart_queue, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM, &uart_config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM, UART_TX_PIN, UART_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    
    ESP_LOGI(TAG, "UART initialized");
    
    state_machine_start();
    
    uint8_t *data = (uint8_t *)malloc(4096);
    
    while (1) {
        int len = uart_read_bytes(UART_NUM, data, 4096, pdMS_TO_TICKS(100));
        
        if (len > 0) {
            protocol_process_data(&protocol_handler, data, len);
        }
        
        protocol_send_queued(&protocol_handler);
        
        state_machine_update();
        led_matrix_update();
        servo_update();
        audio_update();
        sensor_update();
        
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    
    free(data);
}

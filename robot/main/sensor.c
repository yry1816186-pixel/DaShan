#include "sensor.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "SENSOR";
static SensorController sensor_controller;

void sensor_init(void)
{
    memset(&sensor_controller, 0, sizeof(SensorController));
    
    sensor_controller.data.distance = 0xFFFF;
    sensor_controller.data.proximity = 0;
    sensor_controller.data.light_level = 0;
    sensor_controller.data.enabled = true;
    sensor_controller.update_interval = 100;
    
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << HCSR04_TRIG_PIN),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    
    ESP_ERROR_CHECK(gpio_config(&io_conf));
    gpio_set_level(HCSR04_TRIG_PIN, 0);
    
    io_conf.pin_bit_mask = (1ULL << HCSR04_ECHO_PIN);
    io_conf.mode = GPIO_MODE_INPUT;
    
    ESP_ERROR_CHECK(gpio_config(&io_conf));
    
    ESP_LOGI(TAG, "Sensor controller initialized");
}

uint16_t sensor_read_distance(void)
{
    gpio_set_level(HCSR04_TRIG_PIN, 0);
    vTaskDelay(pdMS_TO_TICKS(2));
    
    gpio_set_level(HCSR04_TRIG_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(HCSR04_TRIG_PIN, 0);
    
    uint32_t start_time = esp_timer_get_time();
    uint32_t timeout = start_time + 30000;
    
    while (gpio_get_level(HCSR04_ECHO_PIN) == 0) {
        if (esp_timer_get_time() > timeout) {
            return 0xFFFF;
        }
    }
    
    uint32_t pulse_start = esp_timer_get_time();
    
    while (gpio_get_level(HCSR04_ECHO_PIN) == 1) {
        if (esp_timer_get_time() > timeout) {
            return 0xFFFF;
        }
    }
    
    uint32_t pulse_end = esp_timer_get_time();
    uint32_t pulse_duration = pulse_end - pulse_start;
    
    uint16_t distance = pulse_duration * 34 / 2 / 1000;
    
    ESP_LOGD(TAG, "Distance: %d cm", distance);
    
    return distance;
}

uint8_t sensor_read_proximity(void)
{
    uint16_t distance = sensor_read_distance();
    
    if (distance != 0xFFFF && distance < PROXIMITY_THRESHOLD) {
        return 1;
    }
    
    return 0;
}

uint8_t sensor_read_light_level(void)
{
    uint32_t adc_value = 0;
    const int samples = 10;
    
    for (int i = 0; i < samples; i++) {
        adc_value += 0;
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    
    adc_value /= samples;
    
    uint8_t light_level = (uint8_t)(adc_value / 4096.0 * 255);
    
    ESP_LOGD(TAG, "Light level: %d", light_level);
    
    return light_level;
}

void sensor_update(void)
{
    if (!sensor_controller.data.enabled) {
        return;
    }
    
    uint32_t now = esp_timer_get_time() / 1000;
    
    if (now - sensor_controller.data.last_update_time >= sensor_controller.update_interval) {
        sensor_controller.data.distance = sensor_read_distance();
        sensor_controller.data.proximity = sensor_read_proximity();
        sensor_controller.data.light_level = sensor_read_light_level();
        sensor_controller.data.last_update_time = now;
        
        ESP_LOGD(TAG, "Sensor update: distance=%d, proximity=%d, light=%d",
                  sensor_controller.data.distance,
                  sensor_controller.data.proximity,
                  sensor_controller.data.light_level);
    }
}

uint16_t sensor_get_distance(void)
{
    return sensor_controller.data.distance;
}

uint8_t sensor_get_proximity(void)
{
    return sensor_controller.data.proximity;
}

uint8_t sensor_get_light_level(void)
{
    return sensor_controller.data.light_level;
}

void sensor_set_update_interval(uint32_t interval)
{
    sensor_controller.update_interval = interval;
}

bool sensor_is_enabled(void)
{
    return sensor_controller.data.enabled;
}

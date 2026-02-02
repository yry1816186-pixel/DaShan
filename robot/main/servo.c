#include "servo.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <math.h>

static const char *TAG = "SERVO";
static ServoController servo_controller;

void servo_init(void)
{
    memset(&servo_controller, 0, sizeof(ServoController));
    
    servo_controller.horizontal.pin = SERVO_H_PIN;
    servo_controller.vertical.pin = SERVO_V_PIN;
    servo_controller.horizontal.current_angle = 90;
    servo_controller.vertical.current_angle = 90;
    servo_controller.enabled = true;
    
    ledc_timer_config_t timer_conf = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_16_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = SERVO_FREQ,
        .clk_cfg = LEDC_AUTO_CLK
    };
    
    ESP_ERROR_CHECK(ledc_timer_config(&timer_conf));
    
    ledc_channel_config_t channel_conf_h = {
        .gpio_num = SERVO_H_PIN,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0
    };
    
    ledc_channel_config_t channel_conf_v = {
        .gpio_num = SERVO_V_PIN,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_1,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0
    };
    
    ESP_ERROR_CHECK(ledc_channel_config(&channel_conf_h));
    ESP_ERROR_CHECK(ledc_channel_config(&channel_conf_v));
    
    servo_set_home();
    
    ESP_LOGI(TAG, "Servo controller initialized");
}

uint16_t servo_angle_to_pulse(uint16_t angle)
{
    if (angle > 180) {
        angle = 180;
    }
    
    return SERVO_MIN_PULSE + (SERVO_MAX_PULSE - SERVO_MIN_PULSE) * angle / 180;
}

uint16_t servo_pulse_to_angle(uint16_t pulse)
{
    if (pulse < SERVO_MIN_PULSE) {
        pulse = SERVO_MIN_PULSE;
    }
    if (pulse > SERVO_MAX_PULSE) {
        pulse = SERVO_MAX_PULSE;
    }
    
    return (pulse - SERVO_MIN_PULSE) * 180 / (SERVO_MAX_PULSE - SERVO_MIN_PULSE);
}

void servo_set_angle(uint8_t servo_id, uint16_t angle, uint8_t speed)
{
    if (!servo_controller.enabled) {
        return;
    }
    
    if (angle > 180) {
        angle = 180;
    }
    
    Servo *servo = (servo_id == 1) ? &servo_controller.horizontal : &servo_controller.vertical;
    
    servo->target_angle = angle;
    servo->target_pulse = servo_angle_to_pulse(angle);
    servo->speed = speed;
    servo->moving = true;
    
    ESP_LOGD(TAG, "Servo %d: angle=%d, speed=%d", servo_id, angle, speed);
}

void servo_set_pulse(uint8_t servo_id, uint16_t pulse)
{
    if (!servo_controller.enabled) {
        return;
    }
    
    Servo *servo = (servo_id == 1) ? &servo_controller.horizontal : &servo_controller.vertical;
    
    servo->current_pulse = pulse;
    servo->current_angle = servo_pulse_to_angle(pulse);
    
    ledc_channel_t channel = (servo_id == 1) ? LEDC_CHANNEL_0 : LEDC_CHANNEL_1;
    uint32_t duty = pulse * 65535 / 20000;
    
    ESP_ERROR_CHECK(ledc_set_duty(LEDC_LOW_SPEED_MODE, channel, duty));
    ESP_ERROR_CHECK(ledc_update_duty(LEDC_LOW_SPEED_MODE, channel));
}

void servo_stop(uint8_t servo_id)
{
    Servo *servo = (servo_id == 1) ? &servo_controller.horizontal : &servo_controller.vertical;
    servo->moving = false;
}

void servo_stop_all(void)
{
    servo_controller.horizontal.moving = false;
    servo_controller.vertical.moving = false;
}

void servo_update(void)
{
    if (!servo_controller.enabled) {
        return;
    }
    
    uint32_t now = xTaskGetTickCount();
    
    for (int i = 0; i < 2; i++) {
        Servo *servo = (i == 0) ? &servo_controller.horizontal : &servo_controller.vertical;
        
        if (servo->moving) {
            uint16_t diff = abs(servo->target_pulse - servo->current_pulse);
            
            if (diff <= 1) {
                servo->current_pulse = servo->target_pulse;
                servo->current_angle = servo->target_angle;
                servo->moving = false;
                servo_set_pulse(i + 1, servo->current_pulse);
            } else {
                uint16_t step = (servo->speed + 1) * 10 / 100;
                
                if (step < 1) {
                    step = 1;
                }
                if (step > diff) {
                    step = diff;
                }
                
                if (servo->target_pulse > servo->current_pulse) {
                    servo->current_pulse += step;
                } else {
                    servo->current_pulse -= step;
                }
                
                servo->current_angle = servo_pulse_to_angle(servo->current_pulse);
                servo_set_pulse(i + 1, servo->current_pulse);
                
                servo->last_update = now;
            }
        }
    }
}

void servo_set_home(void)
{
    servo_set_angle(1, 90, 50);
    servo_set_angle(2, 90, 50);
}

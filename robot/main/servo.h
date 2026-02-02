#ifndef SERVO_H
#define SERVO_H

#include <stdint.h>
#include <stdbool.h>

#define SERVO_H_PIN GPIO_NUM_6
#define SERVO_V_PIN GPIO_NUM_7
#define SERVO_MIN_PULSE 500
#define SERVO_MAX_PULSE 2500
#define SERVO_FREQ 50

typedef struct {
    uint8_t pin;
    uint16_t current_angle;
    uint16_t target_angle;
    uint16_t current_pulse;
    uint16_t target_pulse;
    uint8_t speed;
    bool moving;
    uint32_t last_update;
} Servo;

typedef struct {
    Servo horizontal;
    Servo vertical;
    bool enabled;
} ServoController;

void servo_init(void);
void servo_set_angle(uint8_t servo_id, uint16_t angle, uint8_t speed);
void servo_set_pulse(uint8_t servo_id, uint16_t pulse);
void servo_stop(uint8_t servo_id);
void servo_stop_all(void);
void servo_update(void);
uint16_t servo_angle_to_pulse(uint16_t angle);
uint16_t servo_pulse_to_angle(uint16_t pulse);
void servo_set_home(void);

#endif

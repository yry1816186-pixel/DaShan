#ifndef SERVO_H
#define SERVO_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SERVO_H_MIN_ANGLE    30
#define SERVO_H_MAX_ANGLE    150
#define SERVO_V_MIN_ANGLE    30
#define SERVO_V_MAX_ANGLE    150
#define SERVO_H_CENTER       90
#define SERVO_V_CENTER       90

typedef enum {
    SERVO_H,
    SERVO_V,
    SERVO_COUNT
} ServoId;

typedef struct {
    uint8_t gpio;
    uint16_t min_angle;
    uint16_t max_angle;
    uint16_t center_angle;
    uint16_t current_angle;
    uint8_t min_pulse;
    uint8_t max_pulse;
} ServoConfig;

void servo_init(void);
void servo_deinit(void);
esp_err_t servo_set_angle(ServoId id, uint16_t angle);
uint16_t servo_get_angle(ServoId id);
esp_err_t servo_set_angle_smooth(ServoId id, uint16_t angle, uint16_t speed);
void servo_center_all(void);
void servo_stop_all(void);

#ifdef __cplusplus
}
#endif

#endif

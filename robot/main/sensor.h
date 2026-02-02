#ifndef SENSOR_H
#define SENSOR_H

#include <stdint.h>
#include <stdbool.h>

#define HCSR04_TRIG_PIN GPIO_NUM_9
#define HCSR04_ECHO_PIN GPIO_NUM_10

#define PROXIMITY_THRESHOLD 30
#define LIGHT_SENSOR_PIN GPIO_NUM_11

typedef struct {
    uint16_t distance;
    uint8_t proximity;
    uint8_t light_level;
    bool enabled;
    uint32_t last_update_time;
} SensorData;

typedef struct {
    SensorData data;
    uint32_t update_interval;
} SensorController;

void sensor_init(void);
void sensor_update(void);
uint16_t sensor_get_distance(void);
uint8_t sensor_get_proximity(void);
uint8_t sensor_get_light_level(void);
void sensor_set_update_interval(uint32_t interval);
bool sensor_is_enabled(void);

#endif

#ifndef SENSOR_H
#define SENSOR_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SENSOR_DISTANCE_MAX   2000
#define SENSOR_DISTANCE_MIN   30
#define SENSOR_LIGHT_MAX      255
#define SENSOR_TOUCH_THRESHOLD 500

typedef enum {
    SENSOR_OK = 0,
    SENSOR_ERROR_INIT,
    SENSOR_ERROR_I2C,
    SENSOR_ERROR_ADC
} SensorStatus;

typedef enum {
    SENSOR_DISTANCE,
    SENSOR_LIGHT,
    SENSOR_TOUCH,
    SENSOR_BATTERY,
    SENSOR_COUNT
} SensorType;

typedef struct {
    uint16_t distance;
    uint8_t light_level;
    uint8_t touch_state;
    uint8_t battery_level;
    uint32_t timestamp;
} SensorData;

SensorStatus sensor_init(void);
SensorStatus sensor_deinit(void);
SensorStatus sensor_start(void);
SensorStatus sensor_stop(void);
SensorStatus sensor_read_all(SensorData* data);
SensorStatus sensor_read_distance(uint16_t* distance);
SensorStatus sensor_read_light(uint8_t* level);
SensorStatus sensor_read_touch(uint8_t* state);
SensorStatus sensor_read_battery(uint8_t* level);
bool sensor_is_running(void);

#ifdef __cplusplus
}
#endif

#endif

#ifndef CAMERA_H
#define CAMERA_H

#include <stdint.h>
#include <stdbool.h>

#define CAMERA_WIDTH 320
#define CAMERA_HEIGHT 240

typedef struct {
    bool enabled;
    uint16_t width;
    uint16_t height;
    uint32_t frame_count;
    uint32_t last_capture_time;
    uint8_t *frame_buffer;
    uint16_t buffer_size;
} Camera;

void camera_init(void);
void camera_start(void);
void camera_stop(void);
bool camera_capture_frame(uint8_t **buffer, uint16_t *size);
void camera_release_frame(void);
void camera_update(void);
bool camera_is_enabled(void);
uint32_t camera_get_frame_count(void);

#endif

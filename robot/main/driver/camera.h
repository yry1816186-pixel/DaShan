#ifndef CAMERA_H
#define CAMERA_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CAMERA_WIDTH    320
#define CAMERA_HEIGHT   240
#define CAMERA_FPS      15
#define MAX_FRAME_SIZE  (CAMERA_WIDTH * CAMERA_HEIGHT * 2)

typedef enum {
    CAMERA_OK = 0,
    CAMERA_ERROR_INIT,
    CAMERA_ERROR_CONFIG,
    CAMERA_ERROR_FRAME
} CameraStatus;

typedef struct {
    uint16_t width;
    uint16_t height;
    uint8_t fps;
    uint8_t format;
    uint8_t quality;
} CameraConfig;

typedef struct {
    uint8_t data[MAX_FRAME_SIZE];
    uint16_t size;
    uint32_t timestamp;
} CameraFrame;

CameraStatus camera_init(CameraConfig* config);
CameraStatus camera_deinit(void);
CameraStatus camera_start(void);
CameraStatus camera_stop(void);
CameraStatus camera_get_frame(CameraFrame* frame);
CameraStatus camera_set_config(CameraConfig* config);
bool camera_is_running(void);

#ifdef __cplusplus
}
#endif

#endif

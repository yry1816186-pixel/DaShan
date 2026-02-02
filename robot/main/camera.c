#include "camera.h"
#include "esp_camera.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "CAMERA";
static Camera camera;

#define CAMERA_MODEL_ESP32S3_EYE

#ifdef CAMERA_MODEL_ESP32S3_EYE
#define PWDN_GPIO_NUM -1
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 15
#define SIOD_GPIO_NUM 4
#define SIOC_GPIO_NUM 5

#define Y9_GPIO_NUM 16
#define Y8_GPIO_NUM 35
#define Y7_GPIO_NUM 17
#define Y6_GPIO_NUM 18
#define Y5_GPIO_NUM 12
#define Y4_GPIO_NUM 10
#define Y3_GPIO_NUM 8
#define Y2_GPIO_NUM 9
#define VSYNC_GPIO_NUM 6
#define HREF_GPIO_NUM 7
#define PCLK_GPIO_NUM 11

#endif

void camera_init(void)
{
    memset(&camera, 0, sizeof(Camera));
    camera.width = CAMERA_WIDTH;
    camera.height = CAMERA_HEIGHT;
    
    camera_config_t config = {
        .pin_pwdn = PWDN_GPIO_NUM,
        .pin_reset = RESET_GPIO_NUM,
        .pin_xclk = XCLK_GPIO_NUM,
        .pin_sscb = SIOD_GPIO_NUM,
        .pin_sscc = SIOC_GPIO_NUM,
        .pin_d7 = Y9_GPIO_NUM,
        .pin_d6 = Y8_GPIO_NUM,
        .pin_d5 = Y7_GPIO_NUM,
        .pin_d4 = Y6_GPIO_NUM,
        .pin_d3 = Y5_GPIO_NUM,
        .pin_d2 = Y4_GPIO_NUM,
        .pin_d1 = Y3_GPIO_NUM,
        .pin_d0 = Y2_GPIO_NUM,
        .pin_vsync = VSYNC_GPIO_NUM,
        .pin_href = HREF_GPIO_NUM,
        .pin_pclk = PCLK_GPIO_NUM,
        
        .xclk_freq_hz = 20000000,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        
        .pixel_format = PIXFORMAT_JPEG,
        .frame_size = FRAMESIZE_QVGA,
        .jpeg_quality = 12,
        .fb_count = 1,
        
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
    };
    
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed with error 0x%x", err);
        return;
    }
    
    sensor_t *s = esp_camera_sensor_get();
    s->set_brightness(s, 0);
    s->set_contrast(s, 0);
    s->set_saturation(s, 0);
    
    camera.buffer_size = camera.width * camera.height * 2;
    camera.frame_buffer = (uint8_t *)malloc(camera.buffer_size);
    
    if (!camera.frame_buffer) {
        ESP_LOGE(TAG, "Failed to allocate frame buffer");
        return;
    }
    
    ESP_LOGI(TAG, "Camera initialized: %dx%d", camera.width, camera.height);
}

void camera_start(void)
{
    camera.enabled = true;
    camera.frame_count = 0;
    camera.last_capture_time = esp_timer_get_time() / 1000;
    
    ESP_LOGI(TAG, "Camera started");
}

void camera_stop(void)
{
    camera.enabled = false;
    ESP_LOGI(TAG, "Camera stopped");
}

bool camera_capture_frame(uint8_t **buffer, uint16_t *size)
{
    if (!camera.enabled) {
        return false;
    }
    
    camera_fb_t *fb = esp_camera_fb_get();
    
    if (!fb) {
        ESP_LOGE(TAG, "Camera capture failed");
        return false;
    }
    
    if (fb->len > camera.buffer_size) {
        ESP_LOGW(TAG, "Frame too large: %d > %d", fb->len, camera.buffer_size);
        esp_camera_fb_return(fb);
        return false;
    }
    
    memcpy(camera.frame_buffer, fb->buf, fb->len);
    
    *buffer = camera.frame_buffer;
    *size = fb->len;
    
    camera.frame_count++;
    camera.last_capture_time = esp_timer_get_time() / 1000;
    
    esp_camera_fb_return(fb);
    
    ESP_LOGD(TAG, "Captured frame: %d bytes", fb->len);
    
    return true;
}

void camera_release_frame(void)
{
}

void camera_update(void)
{
}

bool camera_is_enabled(void)
{
    return camera.enabled;
}

uint32_t camera_get_frame_count(void)
{
    return camera.frame_count;
}

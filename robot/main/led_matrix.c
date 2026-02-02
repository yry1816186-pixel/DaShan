#include "led_matrix.h"
#include "driver/rmt.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char *TAG = "LED_MATRIX";
static LedMatrix led_matrix;

#define LED_RMT_RESOLUTION_HZ 10000000
#define LED_RMT_CHANNELS RMT_CHANNEL_0

static uint8_t rmt_buffer[MATRIX_SIZE * MATRIX_SIZE * 24 * 2];

void ws2812_rmt_init(void)
{
    rmt_config_t config = RMT_DEFAULT_CONFIG_TX(LED_DATA_PIN, LED_RMT_CHANNELS);
    config.clk_div = 2;
    config.mem_block_num = 2;
    
    rmt_config(&config);
    rmt_driver_install(LED_RMT_CHANNELS, 0, 0);
    
    ESP_LOGI(TAG, "RMT initialized for WS2812B");
}

void ws2812_write_pixels(uint8_t *pixels, uint32_t num_pixels)
{
    rmt_item32_t *rmt_items = (rmt_item32_t *)rmt_buffer;
    rmt_item32_t *current_item = rmt_items;
    
    for (uint32_t i = 0; i < num_pixels; i++) {
        uint8_t pixel = pixels[i];
        
        for (int j = 7; j >= 0; j--) {
            uint8_t bit = (pixel >> j) & 0x01;
            
            if (bit) {
                current_item->duration0 = 8;
                current_item->level0 = 1;
                current_item->duration1 = 4;
                current_item->level1 = 0;
            } else {
                current_item->duration0 = 4;
                current_item->level0 = 1;
                current_item->duration1 = 8;
                current_item->level1 = 0;
            }
            
            current_item++;
        }
    }
    
    rmt_write_items(LED_RMT_CHANNELS, rmt_items, num_pixels * 8, true);
    rmt_wait_tx_done(LED_RMT_CHANNELS, pdMS_TO_TICKS(100));
}

void led_matrix_init(void)
{
    memset(&led_matrix, 0, sizeof(LedMatrix));
    led_matrix.brightness = LED_BRIGHTNESS_DEFAULT;
    
    ws2812_rmt_init();
    led_matrix_clear();
    
    ESP_LOGI(TAG, "LED matrix initialized");
}

void led_matrix_set_pixel(uint8_t x, uint8_t y, uint8_t r, uint8_t g, uint8_t b)
{
    if (x >= MATRIX_SIZE || y >= MATRIX_SIZE) {
        return;
    }
    
    led_matrix.matrix[x][y][0] = (r * led_matrix.brightness) / 255;
    led_matrix.matrix[x][y][1] = (g * led_matrix.brightness) / 255;
    led_matrix.matrix[x][y][2] = (b * led_matrix.brightness) / 255;
}

void led_matrix_get_pixel(uint8_t x, uint8_t y, uint8_t *r, uint8_t *g, uint8_t *b)
{
    if (x >= MATRIX_SIZE || y >= MATRIX_SIZE) {
        return;
    }
    
    *r = led_matrix.matrix[x][y][0];
    *g = led_matrix.matrix[x][y][1];
    *b = led_matrix.matrix[x][y][2];
}

void led_matrix_clear(void)
{
    memset(led_matrix.matrix, 0, sizeof(led_matrix.matrix));
}

void led_matrix_fill(uint8_t r, uint8_t g, uint8_t b)
{
    for (uint8_t x = 0; x < MATRIX_SIZE; x++) {
        for (uint8_t y = 0; y < MATRIX_SIZE; y++) {
            led_matrix_set_pixel(x, y, r, g, b);
        }
    }
}

void led_matrix_set_brightness(uint8_t brightness)
{
    led_matrix.brightness = brightness;
}

void led_matrix_update(void)
{
    uint8_t pixels[MATRIX_SIZE * MATRIX_SIZE * 3];
    uint8_t *pixel_ptr = pixels;
    
    for (uint8_t x = 0; x < MATRIX_SIZE; x++) {
        for (uint8_t y = 0; y < MATRIX_SIZE; y++) {
            *pixel_ptr++ = led_matrix.matrix[x][y][1];
            *pixel_ptr++ = led_matrix.matrix[x][y][0];
            *pixel_ptr++ = led_matrix.matrix[x][y][2];
        }
    }
    
    ws2812_write_pixels(pixels, MATRIX_SIZE * MATRIX_SIZE);
}

void led_matrix_draw_eye(int center_x, int center_y, int radius, uint8_t r, uint8_t g, uint8_t b)
{
    for (int x = center_x - radius; x <= center_x + radius; x++) {
        for (int y = center_y - radius; y <= center_y + radius; y++) {
            if (x >= 0 && x < MATRIX_SIZE && y >= 0 && y < MATRIX_SIZE) {
                int dx = x - center_x;
                int dy = y - center_y;
                if (dx * dx + dy * dy <= radius * radius) {
                    led_matrix_set_pixel(x, y, r, g, b);
                }
            }
        }
    }
}

void led_matrix_draw_pupil(int center_x, int center_y, int radius, uint8_t r, uint8_t g, uint8_t b)
{
    for (int x = center_x - radius; x <= center_x + radius; x++) {
        for (int y = center_y - radius; y <= center_y + radius; y++) {
            if (x >= 0 && x < MATRIX_SIZE && y >= 0 && y < MATRIX_SIZE) {
                int dx = x - center_x;
                int dy = y - center_y;
                if (dx * dx + dy * dy <= radius * radius) {
                    led_matrix_set_pixel(x, y, r, g, b);
                }
            }
        }
    }
}

void led_matrix_set_expression(uint8_t expression_id)
{
    led_matrix_clear();
    
    switch (expression_id) {
        case 0x00: 
            led_matrix_draw_eye(2, 4, 2, 50, 50, 50);
            led_matrix_draw_eye(5, 4, 2, 50, 50, 50);
            break;
        case 0x01: 
            led_matrix_draw_eye(2, 4, 2, 0, 255, 0);
            led_matrix_draw_eye(5, 4, 2, 0, 255, 0);
            break;
        case 0x02: 
            led_matrix_draw_eye(2, 4, 2, 0, 150, 255);
            led_matrix_draw_eye(5, 4, 2, 0, 150, 255);
            break;
        case 0x03: 
            led_matrix_draw_eye(2, 3, 2, 255, 200, 0);
            led_matrix_draw_eye(5, 3, 2, 255, 200, 0);
            break;
        case 0x04: 
            led_matrix_draw_eye(2, 4, 2, 255, 100, 100);
            led_matrix_draw_eye(5, 4, 2, 255, 100, 100);
            break;
        case 0x05: 
            led_matrix_draw_eye(2, 4, 2, 255, 255, 0);
            led_matrix_draw_eye(5, 4, 2, 255, 255, 0);
            break;
        case 0x06: 
            led_matrix_draw_eye(2, 5, 2, 0, 0, 255);
            led_matrix_draw_eye(5, 5, 2, 0, 0, 255);
            break;
        case 0x07: 
            led_matrix_draw_eye(2, 3, 2, 255, 255, 255);
            led_matrix_draw_eye(5, 3, 2, 255, 255, 255);
            break;
        case 0x08: 
            led_matrix_draw_eye(2, 4, 2, 255, 165, 0);
            led_matrix_draw_eye(5, 4, 2, 255, 165, 0);
            break;
        case 0x09: 
            led_matrix_draw_eye(2, 4, 2, 255, 255, 150);
            led_matrix_draw_eye(5, 4, 2, 255, 255, 150);
            break;
        case 0x0A: 
            led_matrix_draw_eye(2, 5, 2, 255, 182, 193);
            led_matrix_draw_eye(5, 5, 2, 255, 182, 193);
            break;
        case 0x0B: 
            led_matrix_draw_eye(2, 4, 2, 255, 0, 0);
            led_matrix_draw_eye(5, 4, 2, 255, 0, 0);
            break;
        case 0x0C: 
            led_matrix_draw_eye(2, 4, 2, 255, 105, 180);
            led_matrix_draw_eye(5, 4, 2, 255, 105, 180);
            break;
        case 0x0D: 
            led_matrix_draw_eye(2, 4, 2, 128, 128, 128);
            led_matrix_draw_eye(5, 4, 2, 128, 128, 128);
            break;
        case 0x0E: 
            led_matrix_draw_eye(2, 3, 2, 255, 0, 255);
            led_matrix_draw_eye(5, 3, 2, 255, 0, 255);
            break;
        case 0x0F: 
            led_matrix_draw_eye(2, 4, 2, 200, 200, 200);
            led_matrix_draw_eye(5, 4, 2, 200, 200, 200);
            break;
        default:
            led_matrix_draw_eye(2, 4, 2, 255, 255, 255);
            led_matrix_draw_eye(5, 4, 2, 255, 255, 255);
            break;
    }
    
    led_matrix_update();
}

void led_matrix_set_eyes(uint8_t left_expr, uint8_t right_expr)
{
    led_matrix_clear();
    
    switch (left_expr) {
        case 0:
            led_matrix_draw_eye(2, 4, 2, 50, 50, 50);
            break;
        default:
            led_matrix_draw_eye(2, 4, 2, 0, 150, 255);
            break;
    }
    
    switch (right_expr) {
        case 0:
            led_matrix_draw_eye(5, 4, 2, 50, 50, 50);
            break;
        default:
            led_matrix_draw_eye(5, 4, 2, 0, 150, 255);
            break;
    }
    
    led_matrix_update();
}

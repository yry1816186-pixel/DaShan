#ifndef LED_MATRIX_H
#define LED_MATRIX_H

#include <stdint.h>
#include <stdbool.h>

#define MATRIX_SIZE 8
#define LED_DATA_PIN GPIO_NUM_8
#define LED_BRIGHTNESS_DEFAULT 255

typedef struct {
    uint8_t matrix[MATRIX_SIZE][MATRIX_SIZE][3];
    uint8_t brightness;
    uint32_t last_update;
    bool animating;
    uint8_t animation_frame;
} LedMatrix;

void led_matrix_init(void);
void led_matrix_set_pixel(uint8_t x, uint8_t y, uint8_t r, uint8_t g, uint8_t b);
void led_matrix_get_pixel(uint8_t x, uint8_t y, uint8_t *r, uint8_t *g, uint8_t *b);
void led_matrix_clear(void);
void led_matrix_fill(uint8_t r, uint8_t g, uint8_t b);
void led_matrix_set_brightness(uint8_t brightness);
void led_matrix_update(void);
void led_matrix_set_expression(uint8_t expression_id);
void led_matrix_set_eyes(uint8_t left_expr, uint8_t right_expr);
void led_matrix_draw_eye(int center_x, int center_y, int radius, uint8_t r, uint8_t g, uint8_t b);
void led_matrix_draw_pupil(int center_x, int center_y, int radius, uint8_t r, uint8_t g, uint8_t b);

#endif

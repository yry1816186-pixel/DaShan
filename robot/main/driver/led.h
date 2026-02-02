#ifndef LED_H
#define LED_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LED_WIDTH    32
#define LED_HEIGHT   32
#define LED_COUNT    (LED_WIDTH * LED_HEIGHT)

typedef enum {
    EYE_LEFT = 0,
    EYE_RIGHT = 1
} EyeId;

typedef enum {
    EXP_SLEEP = 0x00,
    EXP_WAKE = 0x01,
    EXP_LISTEN = 0x02,
    EXP_THINK = 0x03,
    EXP_TALK = 0x04,
    EXP_HAPPY = 0x05,
    EXP_SAD = 0x06,
    EXP_SURPRISED = 0x07,
    EXP_CONFUSED = 0x08,
    EXP_CURIOUS = 0x09,
    EXP_SHY = 0x0A,
    EXP_ANGRY = 0x0B,
    EXP_LOVE = 0x0C,
    EXP_TIRED = 0x0D,
    EXP_EXCITED = 0x0E,
    EXP_BLANK = 0x0F,
    EXP_COUNT
} Expression;

typedef struct {
    EyeId eye;
    Expression exp;
    uint8_t brightness;
    uint16_t duration;
} LedConfig;

void led_init(void);
void led_deinit(void);
esp_err_t led_set_expression(EyeId eye, Expression exp);
esp_err_t led_set_brightness(EyeId eye, uint8_t brightness);
esp_err_t led_set_both(Expression exp);
void led_clear(EyeId eye);
void led_clear_all(void);
esp_err_t led_animate(EyeId eye, Expression exp, uint16_t duration);

#ifdef __cplusplus
}
#endif

#endif

#ifndef AUDIO_H
#define AUDIO_H

#include <stdint.h>
#include <stdbool.h>

#define I2S_MIC_SCK GPIO_NUM_15
#define I2S_MIC_WS GPIO_NUM_14
#define I2S_MIC_SD GPIO_NUM_13

#define I2S_SPK_BCLK GPIO_NUM_41
#define I2S_SPK_LRC GPIO_NUM_42
#define I2S_SPK_DIN GPIO_NUM_40

#define SAMPLE_RATE 16000
#define SAMPLE_BITS 16
#define BUFFER_SIZE 1024

typedef enum {
    AUDIO_IDLE,
    AUDIO_RECORDING,
    AUDIO_PLAYING
} AudioState;

typedef struct {
    i2s_port_t mic_port;
    i2s_port_t spk_port;
    AudioState state;
    uint8_t *record_buffer;
    uint16_t record_size;
    uint16_t record_index;
    uint8_t *play_buffer;
    uint16_t play_size;
    uint16_t play_index;
    uint32_t volume;
    bool enabled;
} AudioController;

void audio_init(void);
void audio_start_recording(void);
void audio_stop_recording(void);
bool audio_is_recording(void);
uint8_t *audio_get_recorded_data(uint16_t *size);
void audio_play_audio(const uint8_t *data, uint16_t size);
bool audio_is_playing(void);
void audio_set_volume(uint8_t volume);
uint8_t audio_get_volume(void);
void audio_update(void);

#endif

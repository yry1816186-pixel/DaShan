#ifndef AUDIO_H
#define AUDIO_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define AUDIO_SAMPLE_RATE    16000
#define AUDIO_CHANNELS       1
#define AUDIO_BITS_PER_SAMPLE 16
#define AUDIO_FRAME_SIZE     512
#define MAX_AUDIO_BUFFER     4096

typedef enum {
    AUDIO_OK = 0,
    AUDIO_ERROR_INIT,
    AUDIO_ERROR_MIC,
    AUDIO_ERROR_SPEAKER,
    AUDIO_ERROR_CONFIG
} AudioStatus;

typedef enum {
    AUDIO_MIC,
    AUDIO_SPEAKER,
    AUDIO_BOTH
} AudioDirection;

typedef struct {
    uint16_t sample_rate;
    uint8_t channels;
    uint8_t bits_per_sample;
    uint16_t frame_size;
} AudioConfig;

typedef struct {
    int16_t data[MAX_AUDIO_BUFFER];
    uint16_t size;
    uint32_t timestamp;
} AudioFrame;

AudioStatus audio_init(AudioConfig* config);
AudioStatus audio_deinit(void);
AudioStatus audio_start(AudioDirection dir);
AudioStatus audio_stop(AudioDirection dir);
AudioStatus audio_read_mic(AudioFrame* frame);
AudioStatus audio_write_speaker(AudioFrame* frame);
AudioStatus audio_set_volume(uint8_t volume);
AudioStatus audio_get_config(AudioConfig* config);
bool audio_is_mic_running(void);
bool audio_is_speaker_running(void);

#ifdef __cplusplus
}
#endif

#endif

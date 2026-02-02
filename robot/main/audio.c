#include "audio.h"
#include "driver/i2s.h"
#include "esp_log.h"
#include "esp_timer.h"
#include <string.h>

static const char *TAG = "AUDIO";
static AudioController audio;

void audio_init(void)
{
    memset(&audio, 0, sizeof(AudioController));
    audio.mic_port = I2S_NUM_0;
    audio.spk_port = I2S_NUM_1;
    audio.state = AUDIO_IDLE;
    audio.volume = 80;
    audio.enabled = true;
    
    audio.record_buffer = (uint8_t *)malloc(1024 * 10);
    audio.play_buffer = (uint8_t *)malloc(1024 * 10);
    
    if (!audio.record_buffer || !audio.play_buffer) {
        ESP_LOGE(TAG, "Failed to allocate audio buffers");
        return;
    }
    
    i2s_config_t mic_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0
    };
    
    i2s_pin_config_t mic_pins = {
        .bck_io_num = I2S_MIC_SCK,
        .ws_io_num = I2S_MIC_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num = I2S_MIC_SD
    };
    
    ESP_ERROR_CHECK(i2s_driver_install(audio.mic_port, &mic_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(audio.mic_port, &mic_pins));
    
    i2s_config_t spk_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = BUFFER_SIZE,
        .use_apll = false,
        .tx_desc_auto_clear = true,
        .fixed_mclk = 0
    };
    
    i2s_pin_config_t spk_pins = {
        .bck_io_num = I2S_SPK_BCLK,
        .ws_io_num = I2S_SPK_LRC,
        .data_out_num = I2S_SPK_DIN,
        .data_in_num = I2S_PIN_NO_CHANGE
    };
    
    ESP_ERROR_CHECK(i2s_driver_install(audio.spk_port, &spk_config, 0, NULL));
    ESP_ERROR_CHECK(i2s_set_pin(audio.spk_port, &spk_pins));
    
    ESP_LOGI(TAG, "Audio controller initialized");
}

void audio_start_recording(void)
{
    if (!audio.enabled) {
        return;
    }
    
    audio.state = AUDIO_RECORDING;
    audio.record_index = 0;
    audio.record_size = 0;
    
    ESP_LOGI(TAG, "Recording started");
}

void audio_stop_recording(void)
{
    if (audio.state != AUDIO_RECORDING) {
        return;
    }
    
    audio.state = AUDIO_IDLE;
    audio.record_size = audio.record_index;
    
    ESP_LOGI(TAG, "Recording stopped: %d bytes", audio.record_size);
}

bool audio_is_recording(void)
{
    return audio.state == AUDIO_RECORDING;
}

uint8_t *audio_get_recorded_data(uint16_t *size)
{
    *size = audio.record_size;
    return audio.record_buffer;
}

void audio_play_audio(const uint8_t *data, uint16_t size)
{
    if (!audio.enabled || size == 0) {
        return;
    }
    
    memcpy(audio.play_buffer, data, size);
    audio.play_size = size;
    audio.play_index = 0;
    audio.state = AUDIO_PLAYING;
    
    ESP_LOGI(TAG, "Playing audio: %d bytes", size);
}

bool audio_is_playing(void)
{
    return audio.state == AUDIO_PLAYING;
}

void audio_set_volume(uint8_t volume)
{
    if (volume > 100) {
        volume = 100;
    }
    
    audio.volume = volume;
    ESP_LOGD(TAG, "Volume set to %d%%", volume);
}

uint8_t audio_get_volume(void)
{
    return audio.volume;
}

void audio_update(void)
{
    if (!audio.enabled) {
        return;
    }
    
    if (audio.state == AUDIO_RECORDING) {
        size_t bytes_read = 0;
        i2s_read(audio.mic_port, 
                  audio.record_buffer + audio.record_index, 
                  BUFFER_SIZE * 2, 
                  &bytes_read, 
                  pdMS_TO_TICKS(100));
        
        if (bytes_read > 0 && audio.record_index + bytes_read < 1024 * 10) {
            audio.record_index += bytes_read;
        }
    }
    else if (audio.state == AUDIO_PLAYING) {
        size_t remaining = audio.play_size - audio.play_index;
        size_t to_write = (remaining > BUFFER_SIZE * 2) ? BUFFER_SIZE * 2 : remaining;
        
        if (to_write > 0) {
            size_t bytes_written = 0;
            i2s_write(audio.spk_port, 
                       audio.play_buffer + audio.play_index, 
                       to_write, 
                       &bytes_written, 
                       pdMS_TO_TICKS(100));
            
            audio.play_index += bytes_written;
        }
        
        if (audio.play_index >= audio.play_size) {
            audio.state = AUDIO_IDLE;
            ESP_LOGD(TAG, "Playback finished");
        }
    }
}

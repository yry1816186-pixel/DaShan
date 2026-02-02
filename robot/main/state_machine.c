#include "state_machine.h"
#include "led_matrix.h"
#include "servo.h"
#include "protocol.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "STATE_MACHINE";
static StateMachine state_machine;

extern ProtocolHandler protocol_handler;

void state_machine_init(void)
{
    memset(&state_machine, 0, sizeof(StateMachine));
    state_machine.current_state = STATE_SLEEP;
    state_machine.previous_state = STATE_SLEEP;
    state_machine.battery_level = 100;
    state_machine.current_expression = 0x00;
    state_machine.servo_h_angle = 90;
    state_machine.servo_v_angle = 90;
    state_machine.running = false;
    
    led_matrix_set_expression(state_machine.current_expression);
    
    ESP_LOGI(TAG, "State machine initialized");
}

void state_machine_start(void)
{
    state_machine.running = true;
    state_machine.state_enter_time = esp_timer_get_time() / 1000;
    ESP_LOGI(TAG, "State machine started");
}

void state_machine_stop(void)
{
    state_machine.running = false;
    ESP_LOGI(TAG, "State machine stopped");
}

void state_machine_transition(SystemState new_state)
{
    if (new_state == state_machine.current_state) {
        return;
    }
    
    ESP_LOGI(TAG, "State transition: %s -> %s", 
              state_machine_get_state_name(state_machine.current_state),
              state_machine_get_state_name(new_state));
    
    state_machine.previous_state = state_machine.current_state;
    state_machine.current_state = new_state;
    state_machine.state_enter_time = esp_timer_get_time() / 1000;
    
    switch (new_state) {
        case STATE_SLEEP:
            state_machine.current_expression = 0x00;
            break;
        case STATE_WAKE:
            state_machine.current_expression = 0x01;
            break;
        case STATE_LISTEN:
            state_machine.current_expression = 0x02;
            break;
        case STATE_THINK:
            state_machine.current_expression = 0x03;
            break;
        case STATE_TALK:
            state_machine.current_expression = 0x04;
            break;
        default:
            break;
    }
    
    led_matrix_set_expression(state_machine.current_expression);
    
    uint8_t data[9];
    data[0] = new_state;
    data[1] = state_machine.battery_level;
    data[2] = state_machine.current_expression;
    memcpy(&data[3], &state_machine.servo_h_angle, 2);
    memcpy(&data[5], &state_machine.servo_v_angle, 2);
    
    protocol_send_response(&protocol_handler, CMD_SET_STATE, data, 9);
}

void state_machine_update(void)
{
    if (!state_machine.running) {
        return;
    }
    
    uint32_t now = esp_timer_get_time() / 1000;
    uint32_t elapsed = now - state_machine.state_enter_time;
    
    switch (state_machine.current_state) {
        case STATE_SLEEP:
            break;
            
        case STATE_WAKE:
            if (elapsed > 2000) {
                state_machine_transition(STATE_LISTEN);
            }
            break;
            
        case STATE_LISTEN:
            break;
            
        case STATE_THINK:
            break;
            
        case STATE_TALK:
            break;
            
        default:
            break;
    }
}

SystemState state_machine_get_state(void)
{
    return state_machine.current_state;
}

const char *state_machine_get_state_name(SystemState state)
{
    switch (state) {
        case STATE_IDLE: return "IDLE";
        case STATE_SLEEP: return "SLEEP";
        case STATE_WAKE: return "WAKE";
        case STATE_LISTEN: return "LISTEN";
        case STATE_THINK: return "THINK";
        case STATE_TALK: return "TALK";
        default: return "UNKNOWN";
    }
}

void state_machine_set_battery_level(uint8_t level)
{
    state_machine.battery_level = level;
    ESP_LOGD(TAG, "Battery level: %d%%", level);
}

uint8_t state_machine_get_battery_level(void)
{
    return state_machine.battery_level;
}

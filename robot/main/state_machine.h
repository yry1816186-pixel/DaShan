#ifndef STATE_MACHINE_H
#define STATE_MACHINE_H

#include "protocol.h"
#include <stdbool.h>

typedef enum {
    STATE_IDLE,
    STATE_SLEEP,
    STATE_WAKE,
    STATE_LISTEN,
    STATE_THINK,
    STATE_TALK
} SystemState;

typedef struct {
    SystemState current_state;
    SystemState previous_state;
    uint32_t state_enter_time;
    uint8_t battery_level;
    uint8_t current_expression;
    uint16_t servo_h_angle;
    uint16_t servo_v_angle;
    bool running;
} StateMachine;

void state_machine_init(void);
void state_machine_start(void);
void state_machine_stop(void);
void state_machine_update(void);
void state_machine_transition(SystemState new_state);
SystemState state_machine_get_state(void);
const char *state_machine_get_state_name(SystemState state);
void state_machine_set_battery_level(uint8_t level);
uint8_t state_machine_get_battery_level(void);

#endif

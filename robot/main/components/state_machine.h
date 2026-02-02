#ifndef STATE_MACHINE_H
#define STATE_MACHINE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    STATE_SLEEP = 0,
    STATE_WAKE,
    STATE_LISTEN,
    STATE_THINK,
    STATE_TALK,
    STATE_ERROR,
    STATE_CHARGING,
    STATE_UPDATING,
    STATE_COUNT
} RobotState;

typedef enum {
    EVT_WAKE_UP = 0x01,
    EVT_SLEEP = 0x02,
    EVT_START_LISTEN = 0x03,
    EVT_STOP_LISTEN = 0x04,
    EVT_START_THINK = 0x05,
    EVT_START_TALK = 0x06,
    EVT_STOP_TALK = 0x07,
    EVT_ERROR = 0x08,
    EVT_START_CHARGING = 0x09,
    EVT_STOP_CHARGING = 0x0A,
    EVT_START_UPDATE = 0x0B,
    EVT_STOP_UPDATE = 0x0C
} StateEvent;

typedef struct {
    RobotState state;
    uint32_t enter_time;
    uint32_t duration;
    uint8_t retry_count;
} StateContext;

typedef void (*StateHandler)(void);
typedef void (*TransitionHandler)(RobotState from, RobotState to);

void state_machine_init(void);
void state_machine_deinit(void);
void state_machine_start(void);
void state_machine_stop(void);
RobotState state_machine_get_state(void);
void state_machine_set_state(RobotState new_state);
void state_machine_handle_event(StateEvent event);
void state_machine_register_handler(RobotState state, StateHandler handler);
void state_machine_register_transition(RobotState from, RobotState to, TransitionHandler handler);
bool state_machine_can_transition(RobotState from, RobotState to);
uint32_t state_machine_get_state_duration(void);

#ifdef __cplusplus
}
#endif

#endif

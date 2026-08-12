/**
 * uplink.c — Yer istasyonundan gelen komut çerçevelerinin ayrıştırılması.
 *
 * Yer istasyonunun FrameParser'ına karşılık gelen bir durum makinesi kullanır.
 * Tamamlanan her çerçeve için uplink_handle_command çağrılır.
 */
#include "uplink.h"
#include "protocol.h"
#include "telemetry.h"
#include "main.h"

typedef enum {
    UP_SYNC1,
    UP_SYNC2,
    UP_LEN,
    UP_TYPE,
    UP_PAYLOAD,
    UP_END1,
    UP_END2
} uplink_state_t;

static uplink_state_t s_state = UP_SYNC1;
static uint8_t  s_payload[PROTO_MAX_PAYLOAD];
static uint16_t s_len = 0;
static uint16_t s_idx = 0;
static uint8_t  s_type = 0;

static void uplink_handle_command(uint8_t cmd, const uint8_t *payload, uint16_t len);

void uplink_init(void)
{
    s_state = UP_SYNC1;
    s_len = 0;
    s_idx = 0;
}

void uplink_feed(uint8_t byte)
{
    switch (s_state) {
    case UP_SYNC1:
        if (byte == PROTO_SYNC1) { s_state = UP_SYNC2; }
        break;
    case UP_SYNC2:
        if (byte == PROTO_SYNC2) { s_state = UP_LEN; }
        else if (byte == PROTO_SYNC1) { s_state = UP_SYNC2; } /* 0xAA 0xAA ... */
        else { s_state = UP_SYNC1; }
        break;
    case UP_LEN:
        s_len = byte;
        s_idx = 0;
        s_state = UP_TYPE;
        break;
    case UP_TYPE:
        s_type = byte;
        s_state = (s_len == 0) ? UP_END1 : UP_PAYLOAD;
        break;
    case UP_PAYLOAD:
        s_payload[s_idx++] = byte;
        if (s_idx >= s_len) { s_state = UP_END1; }
        break;
    case UP_END1:
        s_state = (byte == PROTO_END1) ? UP_END2 : UP_SYNC1;
        break;
    case UP_END2:
        if (byte == PROTO_END2) {
            uplink_handle_command(s_type, s_payload, s_len);
        }
        s_state = UP_SYNC1;
        break;
    default:
        s_state = UP_SYNC1;
        break;
    }
}

static void uplink_handle_command(uint8_t cmd, const uint8_t *payload, uint16_t len)
{
    (void)payload;
    (void)len;

    switch (cmd) {
    case CMD_PING:
        telemetry_send_status_now();
        break;

    case CMD_ARM:
        telemetry_set_state(STATE_ARMED);
        telemetry_arm_gpio(1);       /* silahlanma çıkışını aktif et */
        telemetry_send_status_now();
        break;

    case CMD_DISARM:
        telemetry_set_state(STATE_SAFE);
        telemetry_arm_gpio(0);       /* silahlanma çıkışını kapat */
        telemetry_send_status_now();
        break;

    case CMD_REBOOT:
        NVIC_SystemReset();
        break;

    case CMD_DEPLOY:
        if (telemetry_get_state() == STATE_ARMED) {
            telemetry_deploy();      /* paraşüt/ayrılma ateşlemesi */
            telemetry_set_state(STATE_DEPLOYED);
        }
        telemetry_send_status_now();
        break;

    case CMD_CAMERA_ON:
        telemetry_set_camera_enabled(1);
        telemetry_send_status_now();
        break;

    case CMD_CAMERA_OFF:
        telemetry_set_camera_enabled(0);
        telemetry_send_status_now();
        break;

    case CMD_SET_MODE:
        if (len >= 1) { telemetry_set_mode(payload[0]); }
        telemetry_send_status_now();
        break;

    case CMD_TELEMETRY_RATE:
        if (len >= 1) { telemetry_set_rate_hz(payload[0]); }
        telemetry_send_status_now();
        break;

    case CMD_RAW:
        /* İsteğe bağlı: özel RAW komut işleme buraya eklenebilir. */
        break;

    default:
        /* Bilinmeyen komut yok sayılır. */
        break;
    }
}

/**
 * protocol.c — Çerçeve oluşturma ve UART üzerinden gönderme.
 *
 * Gönderme, CubeMX tarafından üretilen huart1 (veya PROTO_UART_HANDLE ile
 * seçilen) üzerinden yapılır. Yüksek hız gerektiğinde HAL_UART_Transmit yerine
 * HAL_UART_Transmit_DMA / _IT kullanılabilir.
 */
#include "protocol.h"
#include "main.h"
#include <string.h>

/* Telemetri/komut hattı — CubeMX'teki huartX ile eşleştirin. */
#ifndef PROTO_UART_HANDLE
#define PROTO_UART_HANDLE huart1
#endif

/* Paylaşılan TX tamponu (bare-metal tek iş parçacığı için güvenlidir). */
static uint8_t s_tx[PROTO_MAX_PAYLOAD + PROTO_FRAME_OVERHEAD];

void protocol_send_frame(uint8_t type, const uint8_t *payload, uint16_t len)
{
    if (len > PROTO_MAX_PAYLOAD) {
        return;
    }

    s_tx[0] = PROTO_SYNC1;
    s_tx[1] = PROTO_SYNC2;
    s_tx[2] = (uint8_t)len;
    s_tx[3] = type;
    if (len > 0 && payload != NULL) {
        memcpy(&s_tx[4], payload, len);
    }
    s_tx[4 + len] = PROTO_END1;
    s_tx[5 + len] = PROTO_END2;

    HAL_UART_Transmit(&PROTO_UART_HANDLE, s_tx, (uint16_t)(len + PROTO_FRAME_OVERHEAD),
                      HAL_MAX_DELAY);
}

void protocol_send_telemetry(const telemetry_pkt_t *t)
{
    protocol_send_frame(TYPE_TELEMETRY, (const uint8_t *)t, sizeof(*t));
}

void protocol_send_gps(const gps_pkt_t *g)
{
    protocol_send_frame(TYPE_GPS, (const uint8_t *)g, sizeof(*g));
}

void protocol_send_status(const status_pkt_t *s)
{
    protocol_send_frame(TYPE_STATUS, (const uint8_t *)s, sizeof(*s));
}

void protocol_send_camera_chunk(uint32_t frame_id, uint16_t chunk_index,
                                uint16_t total_chunks,
                                const uint8_t *data, uint16_t data_len)
{
    uint8_t payload[CAMERA_HDR_SIZE + CAMERA_CHUNK_SIZE];
    camera_hdr_t hdr;

    hdr.frame_id = frame_id;
    hdr.chunk_index = chunk_index;
    hdr.total_chunks = total_chunks;
    hdr.data_length = data_len;

    memcpy(payload, &hdr, sizeof(hdr));
    if (data_len > 0 && data != NULL) {
        memcpy(&payload[CAMERA_HDR_SIZE], data, data_len);
    }
    protocol_send_frame(TYPE_CAMERA, payload,
                        (uint16_t)(CAMERA_HDR_SIZE + data_len));
}

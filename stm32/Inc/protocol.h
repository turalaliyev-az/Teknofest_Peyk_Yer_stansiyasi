/**
 * protocol.h — Yer istasyonu ile birebir uyumlu iletişim protokolü.
 *
 * Bu dosya, yer istasyonundaki `gs/comm/packet.py` ile AYNI çerçeve formatını ve
 * AYNI struct düzenini kullanır:
 *
 *   SYNC(0xAA 0x55) | LEN(u8) | TYPE(u8) | PAYLOAD(LEN byte) | END(0x0D 0x0A)
 *
 * Tüm çok baytlı alanlar LITTLE-ENDIAN ve paketleme DOLGU YOK (packed).
 * Cortex-M doğal olarak little-endian'dır; IEEE-754 float/double kullanılır.
 */
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- Çerçeve sabitleri --- */
#define PROTO_SYNC1       0xAA
#define PROTO_SYNC2       0x55
#define PROTO_END1        0x0D
#define PROTO_END2        0x0A
#define PROTO_MAX_PAYLOAD 255U
#define PROTO_FRAME_OVERHEAD 6U   /* SYNC(2) + LEN(1) + TYPE(1) + END(2) */

/* --- Downlink tipleri (STM32 -> yer) --- */
#define TYPE_TELEMETRY    0x10
#define TYPE_GPS          0x20
#define TYPE_STATUS       0x30
#define TYPE_CAMERA       0x40

/* --- Uplink komut tipleri (yer -> STM32) --- */
#define CMD_PING           0x01
#define CMD_SET_MODE       0x02
#define CMD_ARM            0x03
#define CMD_DISARM         0x04
#define CMD_REBOOT         0x05
#define CMD_DEPLOY         0x06
#define CMD_CAMERA_ON      0x07
#define CMD_CAMERA_OFF     0x08
#define CMD_TELEMETRY_RATE 0x09
#define CMD_RAW            0xFF

/* --- Durum (state) değerleri --- */
#define STATE_SAFE      0
#define STATE_ARMED     1
#define STATE_FLIGHT    2
#define STATE_DEPLOYED  3
#define STATE_RECOVERY  4

/* --- Kamera parça boyutu (payload 12 + 240 = 252 byte; LEN u8 sınırının altında) --- */
#define CAMERA_CHUNK_SIZE   240U
#define CAMERA_HDR_SIZE     12U

/*
 * Payload yapıları — Python struct.Struct("<...") ile BİREBİR aynı.
 * Dolgu olmaması için packed kullanılır.
 */
#pragma pack(push, 1)
typedef struct {
    uint32_t seq;        /* paket sıra no */
    float battery_v;     /* batarya gerilimi (V) */
    float battery_i;     /* akım (A) */
    float temp_cpu;      /* CPU sıcaklığı (C) */
    float temp_batt;     /* batarya sıcaklığı (C) */
    float pressure;      /* basınç (hPa) */
    float altitude;      /* barometrik irtifa (m) */
    float roll;          /* derece */
    float pitch;         /* derece */
    float yaw;           /* derece */
    float gyro_x;        /* dps */
    float gyro_y;
    float gyro_z;
    float accel_x;       /* m/s^2 */
    float accel_y;
    float accel_z;
    float mag_x;         /* uT */
    float mag_y;
    float mag_z;
    float rssi;          /* dBm */
    uint16_t flags;      /* durum bayrakları */
} telemetry_pkt_t;

typedef struct {
    double lat;          /* enlem (derece) */
    double lon;          /* boylam (derece) */
    float alt;           /* GPS irtifası (m) */
    float speed;         /* m/s */
    float heading;       /* derece */
    float hdop;          /* HDOP */
    uint8_t sats;        /* uydu sayısı */
    uint8_t fix;         /* 0=yok 1=GPS 2=DGPS 3=3D 4=RTK */
    uint32_t utc_time;   /* HHMMSS */
    uint16_t seq;        /* paket sıra no */
} gps_pkt_t;

typedef struct {
    uint8_t mode;        /* çalışma modu */
    uint8_t state;       /* STATE_SAFE / ARMED / ... */
    uint32_t uptime;     /* saniye */
    uint16_t error_flags;/* hata bayrakları */
    float temp_mcu;      /* MCU sıcaklığı (C) */
} status_pkt_t;

typedef struct {
    uint32_t frame_id;   /* kare kimliği */
    uint16_t chunk_index;/* parça indeksi */
    uint16_t total_chunks;/* toplam parça */
    uint32_t data_length;/* bu parçadaki veri boyutu */
} camera_hdr_t;
#pragma pack(pop)

/* Derleme zamanı boyut kontrolü — Python struct boyutlarıyla aynı olmalı */
_Static_assert(sizeof(telemetry_pkt_t) == 82, "telemetry_pkt_t 82 byte olmali");
_Static_assert(sizeof(gps_pkt_t) == 40, "gps_pkt_t 40 byte olmali");
_Static_assert(sizeof(status_pkt_t) == 12, "status_pkt_t 12 byte olmali");
_Static_assert(sizeof(camera_hdr_t) == 12, "camera_hdr_t 12 byte olmali");

/* --- Çerçeve gönderme API --- */
void protocol_send_frame(uint8_t type, const uint8_t *payload, uint16_t len);
void protocol_send_telemetry(const telemetry_pkt_t *t);
void protocol_send_gps(const gps_pkt_t *g);
void protocol_send_status(const status_pkt_t *s);
void protocol_send_camera_chunk(uint32_t frame_id, uint16_t chunk_index,
                                uint16_t total_chunks,
                                const uint8_t *data, uint16_t data_len);

#ifdef __cplusplus
}
#endif

#endif /* PROTOCOL_H */

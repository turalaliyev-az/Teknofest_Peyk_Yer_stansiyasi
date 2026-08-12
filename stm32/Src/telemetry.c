/**
 * telemetry.c — Telemetri/GPS/durum/kamera paketlerinin periyodik gönderimi.
 *
 * Ana döngüden sürekli olarak telemetry_task()/gps_task()/status_task()/
 * camera_task() çağrılır; her görev kendi periyodunu HAL_GetTick() ile kontrol
 * eder. Paket içerikleri yer istasyonunun packet.py formatıyla birebir uyumludur.
 */
#include "telemetry.h"
#include "sensors.h"
#include "protocol.h"
#include "main.h"

#define TELEMETRY_DEFAULT_PERIOD_MS 100U
#define GPS_PERIOD_MS               1000U
#define STATUS_PERIOD_MS            2000U
#define CAMERA_PERIOD_MS            400U
#define CAMERA_JPEG_MAX             8192U

/* --- GPIO pinleri (CubeMX'te uygun pinlerle değiştirin) --- */
#ifndef ARM_GPIO_Port
#define ARM_GPIO_Port  GPIOA
#define ARM_GPIO_Pin   GPIO_PIN_8
#endif
#ifndef DEPLOY_GPIO_Port
#define DEPLOY_GPIO_Port  GPIOA
#define DEPLOY_GPIO_Pin   GPIO_PIN_9
#endif

/* --- Sistem durumu --- */
static volatile uint8_t g_state = STATE_SAFE;
static volatile uint8_t g_mode = 1;
static volatile uint8_t g_camera_enabled = 1;
static uint16_t g_tel_period_ms = TELEMETRY_DEFAULT_PERIOD_MS;

/* --- Sayaçlar --- */
static uint32_t g_tel_seq = 0;
static uint16_t g_gps_seq = 0;
static uint32_t g_camera_frame_id = 0;

/* --- Zamanlayıcılar --- */
static uint32_t g_last_tel = 0;
static uint32_t g_last_gps = 0;
static uint32_t g_last_status = 0;
static uint32_t g_last_camera = 0;

void telemetry_init(void)
{
    sensors_init();
    g_state = STATE_SAFE;
    g_mode = 1;
    g_camera_enabled = 1;
    g_tel_period_ms = TELEMETRY_DEFAULT_PERIOD_MS;

    g_last_tel = HAL_GetTick();
    g_last_gps = HAL_GetTick();
    g_last_status = HAL_GetTick();
    g_last_camera = HAL_GetTick();

    telemetry_send_status_now();  /* açılış durumunu bildir */
}

void telemetry_task(void)
{
    uint32_t now = HAL_GetTick();
    if ((now - g_last_tel) < g_tel_period_ms) { return; }
    g_last_tel = now;

    sensors_data_t d;
    sensors_read(&d);

    telemetry_pkt_t t;
    t.seq = ++g_tel_seq;
    t.battery_v = d.battery_v;
    t.battery_i = d.battery_i;
    t.temp_cpu = d.temp_cpu;
    t.temp_batt = d.temp_batt;
    t.pressure = d.pressure;
    t.altitude = d.altitude;
    t.roll = d.roll;
    t.pitch = d.pitch;
    t.yaw = d.yaw;
    t.gyro_x = d.gyro_x;
    t.gyro_y = d.gyro_y;
    t.gyro_z = d.gyro_z;
    t.accel_x = d.accel_x;
    t.accel_y = d.accel_y;
    t.accel_z = d.accel_z;
    t.mag_x = d.mag_x;
    t.mag_y = d.mag_y;
    t.mag_z = d.mag_z;
    t.rssi = d.rssi;
    t.flags = 0;
    protocol_send_telemetry(&t);
}

void telemetry_gps_task(void)
{
    uint32_t now = HAL_GetTick();
    if ((now - g_last_gps) < GPS_PERIOD_MS) { return; }
    g_last_gps = now;

    sensors_data_t d;
    sensors_read(&d);   /* TODO: verimlilik için yalnızca GPS okunabilir */

    gps_pkt_t g;
    g.lat = d.lat;
    g.lon = d.lon;
    g.alt = d.gps_alt;
    g.speed = d.speed;
    g.heading = d.heading;
    g.hdop = d.hdop;
    g.sats = d.sats;
    g.fix = d.fix;
    g.utc_time = d.utc_time;
    g.seq = ++g_gps_seq;
    protocol_send_gps(&g);
}

void telemetry_status_task(void)
{
    uint32_t now = HAL_GetTick();
    if ((now - g_last_status) < STATUS_PERIOD_MS) { return; }
    g_last_status = now;
    telemetry_send_status_now();
}

void telemetry_send_status_now(void)
{
    status_pkt_t s;
    s.mode = g_mode;
    s.state = g_state;
    s.uptime = HAL_GetTick() / 1000U;
    s.error_flags = 0;
    s.temp_mcu = 30.0f;   /* TODO: STM32 dahili sıcaklık sensöründen okuyun */
    protocol_send_status(&s);
}

void telemetry_camera_task(void)
{
    static uint8_t jpeg[CAMERA_JPEG_MAX];
    uint16_t jpeg_len = 0;
    uint16_t total;
    uint16_t i;
    uint32_t frame_id;

    if (!g_camera_enabled) { return; }

    {
        uint32_t now = HAL_GetTick();
        if ((now - g_last_camera) < CAMERA_PERIOD_MS) { return; }
        g_last_camera = now;
    }

    if (!sensors_camera_capture(jpeg, &jpeg_len)) { return; }

    total = (uint16_t)((jpeg_len + CAMERA_CHUNK_SIZE - 1U) / CAMERA_CHUNK_SIZE);
    if (total == 0) { total = 1; }
    frame_id = ++g_camera_frame_id;

    for (i = 0; i < total; i++) {
        uint16_t off = (uint16_t)(i * CAMERA_CHUNK_SIZE);
        uint16_t rem = (uint16_t)(jpeg_len - off);
        uint16_t clen = (rem > CAMERA_CHUNK_SIZE) ? CAMERA_CHUNK_SIZE : rem;
        protocol_send_camera_chunk(frame_id, i, total, &jpeg[off], clen);
    }
}

/* --- Uplink komut işleyicileri --- */
void telemetry_set_state(uint8_t state) { g_state = state; }
uint8_t telemetry_get_state(void) { return g_state; }
void telemetry_set_mode(uint8_t mode) { g_mode = mode; }
void telemetry_set_camera_enabled(uint8_t en) { g_camera_enabled = (en ? 1U : 0U); }

void telemetry_set_rate_hz(uint8_t hz)
{
    if (hz == 0) { hz = 1; }
    g_tel_period_ms = 1000U / hz;
    if (g_tel_period_ms == 0) { g_tel_period_ms = 1; }
}

void telemetry_arm_gpio(uint8_t on)
{
    HAL_GPIO_WritePin(ARM_GPIO_Port, ARM_GPIO_Pin,
                      on ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

void telemetry_deploy(void)
{
    /* Piroteknik/e-pin ateşleme için kısa darbe.
     * Hassas zamanlama için PWM/timer kullanmanız önerilir. */
    HAL_GPIO_WritePin(DEPLOY_GPIO_Port, DEPLOY_GPIO_Pin, GPIO_PIN_SET);
    HAL_Delay(500);
    HAL_GPIO_WritePin(DEPLOY_GPIO_Port, DEPLOY_GPIO_Pin, GPIO_PIN_RESET);
}

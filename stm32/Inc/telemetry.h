/**
 * telemetry.h — Telemetri/GPS/durum/kamera paketlerinin periyodik gönderimi
 * ve sistem durumu (ARM/DISARM vb.) yönetimi.
 */
#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Açılışta bir kez çağrılır. */
void telemetry_init(void);

/* Ana döngüden sürekli çağrılır; iç zamanlayıcılar ile periyodik gönderir. */
void telemetry_task(void);        /* telemetri (varsayılan 10 Hz) */
void telemetry_gps_task(void);    /* GPS (1 Hz) */
void telemetry_status_task(void); /* durum (0.5 Hz) */
void telemetry_camera_task(void); /* kamera (2.5 Hz, parçalı) */

/* Uplink komut işleyicilerinden çağrılır. */
void telemetry_set_state(uint8_t state);
uint8_t telemetry_get_state(void);
void telemetry_set_mode(uint8_t mode);
void telemetry_set_camera_enabled(uint8_t en);
void telemetry_set_rate_hz(uint8_t hz);
void telemetry_arm_gpio(uint8_t on);
void telemetry_deploy(void);
void telemetry_send_status_now(void);

#ifdef __cplusplus
}
#endif

#endif /* TELEMETRY_H */

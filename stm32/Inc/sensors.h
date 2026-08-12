/**
 * sensors.h — Sensör verilerinin toplanması için arayüz.
 *
 * Buradaki işlevler, gerçek sensör sürücülerinizi (BMP280, MPU6050/GY-91,
 * GPS NMEA, batarya ADC, OV2640 kamera) bağlayacağınız noktalardır.
 */
#ifndef SENSORS_H
#define SENSORS_H

#include <stdint.h>

/* Telemetri + GPS + durum için gereken tüm ham değerler. */
typedef struct {
    float battery_v;
    float battery_i;
    float temp_cpu;
    float temp_batt;
    float pressure;
    float altitude;
    float roll, pitch, yaw;
    float gyro_x, gyro_y, gyro_z;
    float accel_x, accel_y, accel_z;
    float mag_x, mag_y, mag_z;
    float rssi;
    float temp_mcu;

    double lat, lon;
    float gps_alt, speed, heading, hdop;
    uint8_t sats, fix;
    uint32_t utc_time;
} sensors_data_t;

/* Açılışta bir kez çağrılır (I2C/ADC/GPS başlatma, kalibrasyon). */
void sensors_init(void);

/* Sensörleri okuyup yapıyı doldurur. */
void sensors_read(sensors_data_t *d);

/* Kamera JPEG karesini yakalar. Başarılıysa 1 döner, jpeg_buf/jpeg_len doldurur.
 * Kamera yoksa 0 döner (telemetry_camera_task kareyi atlar). */
int sensors_camera_capture(uint8_t *jpeg_buf, uint16_t *jpeg_len);

#endif /* SENSORS_H */

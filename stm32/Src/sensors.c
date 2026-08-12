/**
 * sensors.c — Sensör okuma işlevleri.
 *
 * Bu dosya şu an için yer tutucu (placeholder) değerler döndürür; gerçek
 * sürücülerinizi (BMP280, MPU6050, GPS NMEA, batarya ADC, OV2640) bağlamanız
 * gereken yerleri TODO ile işaretlenmiştir. Kodun derlenip protokolün çalışması
 * için güvenli varsayılanlar sağlanmıştır.
 */
#include "sensors.h"
#include "main.h"

/* ------------------------------------------------------------------------- */
/* TODO: I2C/ADC/GPS başlatma (CubeMX MX_I2C1_Init vs. zaten main'de yapılır). */
/* ------------------------------------------------------------------------- */
void sensors_init(void)
{
    /* Örnek: MPU6050 kalibrasyonu, BMP280 filtre ayarı vb. */
}

/* ------------------------------------------------------------------------- */
/* Batarya: ADC1 kanalından gerilim oku (TODO: gerçek kalibrasyon).            */
/* ------------------------------------------------------------------------- */
static float sensors_read_battery_v(void)
{
    /* TODO: HAL_ADC_Start / HAL_ADC_PollForConversion / HAL_ADC_GetValue
     * ve gerilim bölücü kalibrasyonu ile gerçek değeri hesaplayın. */
    return 11.1f;   /* örnek değer */
}

static float sensors_read_battery_i(void)
{
    /* TODO: akım sensörü (INA226/ACS712) veya shunt üzerinden okuyun. */
    return 0.35f;
}

static void sensors_read_imu(float *roll, float *pitch, float *yaw,
                             float *gx, float *gy, float *gz,
                             float *ax, float *ay, float *az,
                             float *mx, float *my, float *mz)
{
    /* TODO: MPU6050 (gyro+accel) ve manyetometre (HMC5883L/QMC5883L) okuyun.
     * roll/pitch/yaw için tamamlayıcı filtre veya DMP kullanın. */
    *roll = 0.0f;  *pitch = 0.0f; *yaw = 0.0f;
    *gx = 0.0f; *gy = 0.0f; *gz = 0.0f;
    *ax = 0.0f; *ay = 0.0f; *az = 9.81f;
    *mx = 0.0f; *my = 0.0f; *mz = 0.0f;
}

static void sensors_read_baro(float *pressure, float *altitude, float *temp)
{
    /* TODO: BMP280/BME280 okuyun; irtifayı deniz seviyesi basıncına göre hesaplayın:
     * altitude = 44330 * (1 - pow(p / 1013.25, 0.1903)) */
    *pressure = 1013.25f;
    *altitude = 0.0f;
    *temp = 25.0f;
}

static void sensors_read_gps(double *lat, double *lon, float *alt, float *speed,
                             float *heading, float *hdop,
                             uint8_t *sats, uint8_t *fix, uint32_t *utc)
{
    /* TODO: GPS modülünün (NEO-6M/8M) NMEA çıktısını UART'tan ayrıştırın
     * ($GPGGA ve $GPRMC cümleleri). */
    *lat = 39.9334; *lon = 32.8597;
    *alt = 0.0f; *speed = 0.0f; *heading = 0.0f; *hdop = 1.0f;
    *sats = 0; *fix = 0; *utc = 0;
}

void sensors_read(sensors_data_t *d)
{
    float pressure, temp_baro;

    d->battery_v = sensors_read_battery_v();
    d->battery_i = sensors_read_battery_i();
    sensors_read_baro(&pressure, &d->altitude, &temp_baro);
    d->pressure = pressure;
    d->temp_cpu = temp_baro;
    d->temp_batt = 20.0f;   /* TODO: batarya termistörü/DS18B20 */
    d->temp_mcu = 30.0f;    /* TODO: STM32 dahili sıcaklık sensörü (ADC) */

    sensors_read_imu(&d->roll, &d->pitch, &d->yaw,
                     &d->gyro_x, &d->gyro_y, &d->gyro_z,
                     &d->accel_x, &d->accel_y, &d->accel_z,
                     &d->mag_x, &d->mag_y, &d->mag_z);

    sensors_read_gps(&d->lat, &d->lon, &d->gps_alt, &d->speed, &d->heading,
                     &d->hdop, &d->sats, &d->fix, &d->utc_time);

    d->rssi = -60.0f;   /* TODO: radyo modemin RSSI kaydından okuyun */
}

int sensors_camera_capture(uint8_t *jpeg_buf, uint16_t *jpeg_len)
{
    /* TODO: OV2640/OV7670 veya dijital kamera modülünden JPEG karesi alın.
     * jpeg_buf içine yazıp jpeg_len doldurun; başarılıysa 1 döndürün.
     * Kamera yoksa 0 döndürün. */
    (void)jpeg_buf;
    (void)jpeg_len;
    return 0;   /* kamera yok */
}

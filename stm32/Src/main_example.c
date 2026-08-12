/**
 * main_example.c — Uygulama katmanının CubeMX main.c'ine nasıl bağlanacağını
 * gösteren ÖRNEK dosya.
 *
 * Bu dosyayı doğrudan CubeMX'in ürettiği main.c yerine kullanmayın. Bunun
 * yerine, aşağıdaki üç noktayı kendi main.c'inize kopyalayın:
 *   1) HAL_UART_RxCpltCallback  -> uplink_feed
 *   2) Başlangıçta             -> telemetry_init/uplink_init + RX interrupt
 *   3) while(1) döngüsüne       -> *_task çağrıları
 */
#include "main.h"
#include "protocol.h"
#include "telemetry.h"
#include "uplink.h"

/* CubeMX tarafından üretilen tanımlar (kendi projenize göre düzenleyin):
 *   extern UART_HandleTypeDef huart1;  // Telemetri + komut hattı (radyo)
 *   extern UART_HandleTypeDef huart2;  // GPS modülü
 *   extern I2C_HandleTypeDef hi2c1;    // BMP280 + MPU6050
 *   extern ADC_HandleTypeDef hadc1;    // Batarya gerilimi
 */

static uint8_t rx_byte;

/* UART RX tamamlanma geri çağrısı — komut baytlarını uplink ayrıştırıcısına ver. */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance == USART1) {          /* telemetri/komut hattı */
        uplink_feed(rx_byte);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1);  /* tekrar dinle */
    }
    /* GPS için USART2 ayrı bir NMEA ayrıştırıcı ile işlenebilir. */
}

int main(void)
{
    HAL_Init();
    SystemClock_Config();

    MX_GPIO_Init();
    MX_USART1_UART_Init();   /* radyo/telemetri hattı */
    MX_USART2_UART_Init();   /* GPS */
    MX_I2C1_Init();          /* BMP280 + MPU6050 */
    MX_ADC1_Init();          /* batarya */

    telemetry_init();
    uplink_init();

    /* Komut almak için tek baytlık interrupt tabanlı RX başlat. */
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1);

    while (1) {
        telemetry_task();        /* ~10 Hz */
        telemetry_gps_task();    /* 1 Hz */
        telemetry_status_task(); /* 0.5 Hz */
        telemetry_camera_task(); /* 2.5 Hz (kamera varsa) */
    }
}

/* Not: SystemClock_Config() ve MX_* fonksiyonları CubeMX tarafından üretilir;
 * bu örnek dosyada tanımlı değildir. */

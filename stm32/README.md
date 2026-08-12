# STM32 Tarafı — Yer İstasyonu ile Uyumlu Firmware

Bu klasör, yer istasyonunun (`gs/comm/packet.py`) beklediği **birebir aynı** protokolü
konuşan STM32 (HAL/CubeMX) tarafı kodunu içerir. Yer istasyonu kodu değiştirilmemiştir;
bu taraf tamamen ona uyum sağlayacak şekilde yazılmıştır.

> ✅ Protokol uyumu **byte-seviyesinde test edilerek doğrulanmıştır**:
> aynı değerlerle C (STM32) ve Python (yer istasyonu) aynı hex bayt dizisini üretir.

## Protokol özeti

```
SYNC(0xAA 0x55) | LEN(u8) | TYPE(u8) | PAYLOAD(LEN byte) | END(0x0D 0x0A)
```

- Tüm çok baytlı alanlar **little-endian**, yapılar **packed** (dolgu yok).
- CRC **yok** (yer istasyonu ile aynı).

| TYPE | Anlam | C yapısı |
|---|---|---|
| `0x10` | Telemetri | `telemetry_pkt_t` (82 byte) |
| `0x20` | GPS | `gps_pkt_t` (40 byte) |
| `0x30` | Durum | `status_pkt_t` (12 byte) |
| `0x40` | Kamera (parçalı) | `camera_hdr_t` (12) + JPEG parçası |

Uplink komutları (yer → STM32): `PING 0x01`, `SET_MODE 0x02`, `ARM 0x03`,
`DISARM 0x04`, `REBOOT 0x05`, `DEPLOY 0x06`, `CAMERA_ON 0x07`, `CAMERA_OFF 0x08`,
`TELEMETRY_RATE 0x09`, `RAW 0xFF`.

## Dosyalar

```
stm32/
  Inc/
    protocol.h    # çerçeve + struct tanımları (packet.py ile birebir)
    telemetry.h   # periyodik gönderim + durum yönetimi
    uplink.h      # gelen komut ayrıştırıcı
    sensors.h     # sensör okuma arayüzü
  Src/
    protocol.c    # çerçeve oluşturma + UART gönderimi
    telemetry.c   # telemetri/GPS/durum/kamera görevleri
    uplink.c      # komut durum makinesi + işleyiciler
    sensors.c     # sensör okuma (TODO yer tutucular)
    main_example.c# CubeMX main.c'ine nasıl bağlanacağını gösterir
```

## CubeMX / CubeIDE'ye entegrasyon

1. **CubeMX**'te bir UART'ı telemetri/komut hattı olarak yapılandırın
   (radyo modeminizle aynı baudrate, örn. `115200`). Varsayılan kod `huart1`
   kullanır; farklıysa `Src/protocol.c` içindeki `PROTO_UART_HANDLE` makrosunu
   ve `main.c` içindeki `USART1` kontrollerini değiştirin.
2. `Inc/` klasörünü include path'e, `Src/*.c` dosyalarını projeye ekleyin
   (`main_example.c` hariç — o sadece örnektir).
3. `main.c` içine şunları ekleyin (bkz. `main_example.c`):
   - `HAL_UART_RxCpltCallback` içine `uplink_feed(rx_byte)` + RX'i yeniden başlat.
   - Başlangıçta `telemetry_init(); uplink_init(); HAL_UART_Receive_IT(...)`.
   - `while(1)` içine `telemetry_task(); telemetry_gps_task();
     telemetry_status_task(); telemetry_camera_task();`.
4. **GPIO pinleri**: `telemetry.c` içindeki `ARM_GPIO_Port/Pin` ve
   `DEPLOY_GPIO_Port/Pin` makrolarını kendi donanımınıza göre değiştirin ve
   bu pinleri CubeMX'te **çıkış** olarak ayarlayın.
5. **Sensörler**: `sensors.c` içindeki `TODO` ile işaretli işlevlere gerçek
   sürücülerinizi (BMP280, MPU6050/GY-91, GPS NMEA, batarya ADC, OV2640) bağlayın.
   Şu an için güvenli yer tutucu değerler döndürür; böylece protokol derhal test
   edilebilir.

## Komut davranışı

- **ARM** → `state=ARMED`, ARM pin'i aktif, durum yanıtı.
- **DISARM** → `state=SAFE`, ARM pin'i pasif, durum yanıtı.
- **DEPLOY** → yalnızca `ARMED` durumda çalışır; paraşüt pinine 500 ms darbe,
  `state=DEPLOYED`.
- **REBOOT** → `NVIC_SystemReset()`.
- **SET_MODE / TELEMETRY_RATE / CAMERA_ON-OFF** → ilgili ayarı değiştirir ve
  durum yanıtı gönderir.
- **PING** → durum yanıtı gönderir.

## Gönderim hızları (varsayılan)

Telemetri `100 ms` (10 Hz) · GPS `1000 ms` (1 Hz) · Durum `2000 ms` (0.5 Hz) ·
Kamera `400 ms` (2.5 Hz, parça boyutu 240 byte). `TELEMETRY_RATE` komutu ile
telemetri hızı değiştirilebilir.

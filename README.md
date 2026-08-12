# Teknofest Yer İstasyonu (Ground Station)

Teknofest model uydu/roket yarışmaları için masaüstü yer istasyonu arayüzü.
Peyk/roket ile **seri port (radyo)** üzerinden haberleşir; telemetri, GPS,
kamera ve 3D attitude verilerini gerçek zamanlı görselleştirir ve peyke
**uplink komut** gönderilmesine olanak tanır.

## Özellikler

- 📷 **Kamera görüntüsü** — 3 kaynak: uydu linki (paketlerden), USB **webcam**, **UDP** stream.
- 🛰️ **3D uydu görseli** (OpenGL) — roll / pitch / yaw canlı döner, Dünya + yörünge halkası referansı.
- 📍 **GPS → harita** — Google Earth/Maps tarzı karo harita: uydu görüntüsü (Esri) veya yol haritası (OSM), fareyle kaydırma, tekerlekle zoom, konum + zemin izi (ground track).
- 📊 **Telemetri** — batarya, sıcaklık, basınç, irtifa, gyro/accel/mag, RSSI (sayısal panel).
- 📈 **Grafikler** (pyqtgraph) — batarya, sıcaklık, irtifa, attitude, RSSI zaman serisi.
- 🎛️ **Uplink komutları** — PING, **ARM**, **DISARM**, DEPLOY, REBOOT, CAMERA ON/OFF, SET MODE, TELEMETRY RATE, RAW.
- 🧪 **Simülatör modu** — donanım olmadan demo yapmak için sentetik telemetri/GPS/kamera.

## Kurulum

Bağımlılıklar: `PyQt5`, `pyqtgraph`, `pyserial`, `numpy`, `Pillow`, `opencv-python`, `PyOpenGL`.

> **Bu makinede (Ubuntu 24.04) bağımlılıklar zaten kurulu olduğu için** doğrudan
> `python3 yerstansiyasi.py` çalıştırabilirsin; `pip install` gerekmez.

Yeni / temiz bir makinede kurulum için (sistem Python'unu bozmamak adına) sanal ortam önerilir:

```bash
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -r requirements.txt
python3 yerstansiyasi.py
```

> Not: OpenCV (`cv2`) yalnızca webcam seçildiğinde yüklenir; bu sayede PyQt5'in
> `xcb` platform eklentisiyle çakışma olmaz.

## Çalıştırma

```bash
python3 yerstansiyasi.py
```

1. **Bağlantı** açılır listesinden `Simülatör` (donanımsız demo) veya `Seri Port` seçin.
2. Seri port için port ve baudrate'i seçip **Bağlan**'a basın.
3. Kamera kaynağını seçin (Uydu Linki / Webcam / UDP).

> ARM / DISARM / DEPLOY komutları güvenlik için **onay diyaloğu** ister.

---

## İletişim Protokolü (CRC yok)

### Tel çerçevesi

```
SYNC(0xAA 0x55) | LEN(u8) | TYPE(u8) | PAYLOAD(LEN byte) | END(0x0D 0x0A)
```

- `LEN` : payload uzunluğu (1..255 byte)
- `TYPE`: paket tipi (aşağıda)
- CRC kullanılmaz.

### Downlink paket tipleri (peyk → yer)

| TYPE | Anlam | Payload |
|---|---|---|
| `0x10` | TELEMETRİ | `struct < I f*9 f*9 f H` → seq, bat_v, bat_i, temp_cpu, temp_batt, pressure, altitude, roll, pitch, yaw, gyro_x/y/z, accel_x/y/z, mag_x/y/z, rssi, flags |
| `0x20` | GPS | `struct < dd f*4 BB I H` → lat, lon, alt, speed, heading, hdop, sats, fix, utc_time, seq |
| `0x30` | DURUM | `struct < BB I H f` → mode, state, uptime, error_flags, temp_mcu |
| `0x40` | KAMERA | `struct < I H H I` başlık + JPEG parçası → frame_id, chunk_index, total_chunks, data_length, data |

Kamera kareleri parçalanarak gönderilir (chunk boyutu 240 byte); alıcı taraf
`frame_id` ile parçaları birleştirir.

### Uplink komut tipleri (yer → peyk)

| Komut | Kod | Payload |
|---|---|---|
| PING | `0x01` | — |
| SET_MODE | `0x02` | 1 byte mod |
| **ARM** | `0x03` | — |
| **DISARM** | `0x04` | — |
| REBOOT | `0x05` | — |
| DEPLOY | `0x06` | — |
| CAMERA_ON | `0x07` | — |
| CAMERA_OFF | `0x08` | — |
| TELEMETRY_RATE | `0x09` | 1 byte Hz |
| RAW | `0xFF` | ham veri |

### Durum (state) değerleri

`0=SAFE`, `1=ARMED`, `2=FLIGHT`, `3=DEPLOYED`, `4=RECOVERY`

---

## Proje yapısı

```
yerstansiyasi.py          # giriş noktası
gs/
  comm/
    packet.py             # paket çerçeveleme/ayrıştırma
    link.py               # seri bağlantı (pyserial)
    simulator.py          # sentetik uydu simülatörü
  gui/
    main_window.py        # ana pencere
    telemetry_panel.py    # sayısal göstergeler
    map_widget.py         # GPS haritası
    globe3d_widget.py     # 3D uydu (OpenGL)
    camera_widget.py      # kamera + webcam/UDP kaynakları
    plot_widget.py        # zaman serisi grafikleri
    command_panel.py      # uplink komut paneli
```

Harita karoları (uydu/yol görüntüsü) çevrimiçi sunuculardan indirilir ve
`~/.cache/gs_tiles/` altında diskte önbelleğe alınır; böylece aynı bölge
bir sonraki açılışta internet olmadan da görüntülenebilir.


## Notlar

- Gerçek donanımla kullanırken baudrate ve portu peyk/radyo ayarlarıyla eşleştirin.
- UDP kamera varsayılan portu `5600`; her UDP datagramı tek bir JPEG kare olarak beklenir.
- **CSV telemetri**: Peyk ikili protokol yerine virgülle ayrılmış ASCII/CSV
  satırı gönderiyorsa yer istasyonu bunu otomatik algılar. Alan eşleştirmesi
  `gs/comm/csv_parser.py` içindeki `IDX_*` sabitlerinde yapılır — kendi
  peykinin gönderdiği sıraya göre bu indeksleri düzenleyin.

"""CSV (virgülle ayrılmış) telemetri satırı ayrıştırıcı.

Bazı peyk/roket donanımları ikili protokol yerine seri porttan, yeni satırla
biten bir CSV satırı gönderir. Örnek:

    882,0,3,01/01/2026, 00:07:2,99948.8,0.3,-0.03,32.2,12.22,0.000000,0.000000,0.0,0.30,-0.16,9.26,0.1,0.1,0.1,------,1

Alanlar 0 tabanlı indekslerle eşleştirilir. Aşağıdaki IDX_* değerlerini kendi
peykinin gönderdiği sıraya göre düzenle; emin olmadığın alanları None yaparak
devre dışı bırakabilirsin.
"""
from __future__ import annotations

from . import packet

# --------------------------------------------------------------------------
# Alan indeksleri (0 tabanlı) — KENDİ PEYK FORMATINA GÖRE DÜZENLE
#
# Gerçek satır örneği (Arduino Serial.print çıktısı):
#   1204,5,11,01/01/2026, 00:18:1,99957.6,-0.5,0.05,32.3,12.21,0.0,0.0,0.0,0.38,0.11,9.16,0.6,-0.1,-0.3,------,1
#     0  1  2      3          4       5      6   7    8    9    10 11  12  13   14   15   16   17  18   19     20
# --------------------------------------------------------------------------
IDX_SEQ = 0            # paket sayacı (1204, 1205, ...)
IDX_MODE = 1           # sabit değer (mod/versiyon?)
IDX_STATE = 2          # sabit değer (durum?)
IDX_PRESSURE_PA = 5    # basınç (Pa) — hPa'ya çevrilir (÷100)
IDX_ALTITUDE = 6       # barometrik irtifa (m)
IDX_YAW = 7            # küçük salınım yapan değer — yaw olabilir (emin değilsen None)
IDX_TEMPERATURE = 8    # sıcaklık (°C)
IDX_BATTERY_V = 9      # batarya gerilimi (V)
IDX_LAT = 10           # enlem (derece; 0 ise GPS fix yok kabul edilir)
IDX_LON = 11           # boylam (derece)
IDX_ROLL = 13          # roll açısı (°)
IDX_PITCH = 14         # pitch açısı (°)
IDX_ACCEL_Z = 15       # dikey ivme (m/s²)
IDX_GYRO_X = 16        # jiroskop X (dps)
IDX_GYRO_Y = 17        # jiroskop Y (dps)
IDX_GYRO_Z = 18        # jiroskop Z (dps)


def _f(parts: list, i):
    """i. alanı float olarak döndür; yoksa/hatalıysa None."""
    if i is None or i >= len(parts):
        return None
    s = parts[i].strip()
    if not s or s == "------":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _i(parts: list, i) -> int:
    v = _f(parts, i)
    return int(v) if v is not None else 0


def parse_line(raw: bytes):
    """Bir CSV satırını çöz; (TelemetryData, GpsData, StatusData) döner.

    Satır geçersizse (None, None, None) döner.
    """
    text = raw.decode("utf-8", "replace").strip()
    if not text or text.startswith("#"):
        return None, None, None
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 6:
        return None, None, None

    pressure_pa = _f(parts, IDX_PRESSURE_PA)
    tm = packet.TelemetryData(
        seq=_i(parts, IDX_SEQ),
        battery_v=_f(parts, IDX_BATTERY_V) or 0.0,
        battery_i=0.0,
        temp_cpu=_f(parts, IDX_TEMPERATURE) or 0.0,
        temp_batt=0.0,
        pressure=(pressure_pa or 0.0) / 100.0,  # Pa -> hPa
        altitude=_f(parts, IDX_ALTITUDE) or 0.0,
        roll=_f(parts, IDX_ROLL) or 0.0,
        pitch=_f(parts, IDX_PITCH) or 0.0,
        yaw=_f(parts, IDX_YAW) or 0.0,
        gyro_x=_f(parts, IDX_GYRO_X) or 0.0,
        gyro_y=_f(parts, IDX_GYRO_Y) or 0.0,
        gyro_z=_f(parts, IDX_GYRO_Z) or 0.0,
        accel_z=_f(parts, IDX_ACCEL_Z) or 0.0,
        rssi=0.0,
        flags=0,
    )

    lat = _f(parts, IDX_LAT) or 0.0
    lon = _f(parts, IDX_LON) or 0.0
    has_fix = (lat != 0.0) or (lon != 0.0)
    g = packet.GpsData(
        lat=lat, lon=lon, alt=tm.altitude,
        sats=0, fix=3 if has_fix else 0,
    )

    s = packet.StatusData(
        mode=_i(parts, IDX_MODE),
        state=_i(parts, IDX_STATE),
        uptime=0, error_flags=0, temp_mcu=0.0,
    )

    return tm, g, s


class CsvLineParser:
    """Bayt akışını besler; tamamlanan satırları ayrıştırır."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes):
        self._buf.extend(data)
        if len(self._buf) > 8192:  # yeni satır gelmezse tamponu sınırla
            del self._buf[:len(self._buf) - 4096]
        results = []
        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                break
            line = bytes(self._buf[:idx])
            del self._buf[:idx + 1]
            line = line.strip()
            if line:
                t, g, s = parse_line(line)
                if t is not None:
                    results.append((t, g, s))
        return results

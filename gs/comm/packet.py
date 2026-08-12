"""Paket çerçeveleme ve ayrıştırma (CRC yok).

Tel çerçevesi (downlink/peyk -> yer):
    SYNC(0xAA 0x55) | LEN(u8) | TYPE(u8) | PAYLOAD(LEN byte) | END(0x0D 0x0A)

Uplink komutları (yer -> peyk) de aynı çerçeveyi kullanır; TYPE alanına komut
kodu yazılır. CRC kullanılmaz (kullanıcı isteği).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Çerçeve sabitleri
# --------------------------------------------------------------------------
SYNC = b"\xaa\x55"
END = b"\x0d\x0a"
MAX_PAYLOAD = 255

# Downlink tipleri (peyk -> yer)
TYPE_TELEMETRY = 0x10
TYPE_GPS = 0x20
TYPE_STATUS = 0x30
TYPE_CAMERA = 0x40

# Uplink komut tipleri (yer -> peyk)
CMD_PING = 0x01
CMD_SET_MODE = 0x02
CMD_ARM = 0x03
CMD_DISARM = 0x04
CMD_REBOOT = 0x05
CMD_DEPLOY = 0x06
CMD_CAMERA_ON = 0x07
CMD_CAMERA_OFF = 0x08
CMD_TELEMETRY_RATE = 0x09
CMD_RAW = 0xFF

# Durum bayrakları (STATUS.state)
STATE_SAFE = 0
STATE_ARMED = 1
STATE_FLIGHT = 2
STATE_DEPLOYED = 3
STATE_RECOVERY = 4

STATE_NAMES = {
    STATE_SAFE: "SAFE",
    STATE_ARMED: "ARMED",
    STATE_FLIGHT: "FLIGHT",
    STATE_DEPLOYED: "DEPLOYED",
    STATE_RECOVERY: "RECOVERY",
}

# Komut isimleri (log/gösterim için)
COMMAND_NAMES = {
    CMD_PING: "PING",
    CMD_SET_MODE: "SET_MODE",
    CMD_ARM: "ARM",
    CMD_DISARM: "DISARM",
    CMD_REBOOT: "REBOOT",
    CMD_DEPLOY: "DEPLOY",
    CMD_CAMERA_ON: "CAMERA_ON",
    CMD_CAMERA_OFF: "CAMERA_OFF",
    CMD_TELEMETRY_RATE: "TELEMETRY_RATE",
    CMD_RAW: "RAW",
}

# --------------------------------------------------------------------------
# Payload formatları (struct ile sabit boyutlu -> deterministik ayrıştırma)
# --------------------------------------------------------------------------
# Telemetri: seq + 9 float (güç/sıcaklık/irtifa/attitude) + 9 float (gyro/accel/mag)
#            + rssi + flags
TELEMETRY_STRUCT = struct.Struct(
    "<"
    + "I"        # seq (uint32)
    + "f" * 9    # bat_v, bat_i, temp_cpu, temp_batt, pressure, alt, roll, pitch, yaw
    + "f" * 9    # gyro_x/y/z, accel_x/y/z, mag_x/y/z
    + "f"        # rssi (dBm)
    + "H"        # flags (uint16)
)

# GPS: enlem/boylam (double) + alt/hiz/yön/hdop (float) + sats/fix (u8) + utc + seq
GPS_STRUCT = struct.Struct("<dd" + "f" * 4 + "BB" + "I" + "H")

# Durum: mode/state (u8) + uptime (u32) + error_flags (u16) + temp_mcu (f)
STATUS_STRUCT = struct.Struct("<BB" + "I" + "H" + "f")

# Kamera kare başlığı: frame_id + chunk_index + total_chunks + data_length
CAMERA_HDR_STRUCT = struct.Struct("<IHHI")
CAMERA_CHUNK_SIZE = 240  # payload 252 byte -> LEN u8 sınırının altında kalır


# --------------------------------------------------------------------------
# Veri modelleri
# --------------------------------------------------------------------------
@dataclass
class TelemetryData:
    seq: int = 0
    battery_v: float = 0.0
    battery_i: float = 0.0
    temp_cpu: float = 0.0
    temp_batt: float = 0.0
    pressure: float = 0.0
    altitude: float = 0.0
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    gyro_x: float = 0.0
    gyro_y: float = 0.0
    gyro_z: float = 0.0
    accel_x: float = 0.0
    accel_y: float = 0.0
    accel_z: float = 0.0
    mag_x: float = 0.0
    mag_y: float = 0.0
    mag_z: float = 0.0
    rssi: float = 0.0
    flags: int = 0


@dataclass
class GpsData:
    lat: float = 0.0
    lon: float = 0.0
    alt: float = 0.0
    speed: float = 0.0
    heading: float = 0.0
    hdop: float = 0.0
    sats: int = 0
    fix: int = 0
    utc_time: int = 0  # HHMMSS
    seq: int = 0


@dataclass
class StatusData:
    mode: int = 0
    state: int = 0
    uptime: int = 0
    error_flags: int = 0
    temp_mcu: float = 0.0


# --------------------------------------------------------------------------
# Serileştirme
# --------------------------------------------------------------------------
def pack_telemetry(t: TelemetryData) -> bytes:
    return TELEMETRY_STRUCT.pack(
        t.seq,
        t.battery_v, t.battery_i, t.temp_cpu, t.temp_batt,
        t.pressure, t.altitude, t.roll, t.pitch, t.yaw,
        t.gyro_x, t.gyro_y, t.gyro_z,
        t.accel_x, t.accel_y, t.accel_z,
        t.mag_x, t.mag_y, t.mag_z,
        t.rssi, t.flags,
    )


def unpack_telemetry(data: bytes) -> TelemetryData:
    v = TELEMETRY_STRUCT.unpack(data)
    return TelemetryData(
        seq=v[0],
        battery_v=v[1], battery_i=v[2], temp_cpu=v[3], temp_batt=v[4],
        pressure=v[5], altitude=v[6], roll=v[7], pitch=v[8], yaw=v[9],
        gyro_x=v[10], gyro_y=v[11], gyro_z=v[12],
        accel_x=v[13], accel_y=v[14], accel_z=v[15],
        mag_x=v[16], mag_y=v[17], mag_z=v[18],
        rssi=v[19], flags=v[20],
    )


def pack_gps(g: GpsData) -> bytes:
    return GPS_STRUCT.pack(
        g.lat, g.lon, g.alt, g.speed, g.heading, g.hdop,
        g.sats, g.fix, g.utc_time, g.seq,
    )


def unpack_gps(data: bytes) -> GpsData:
    v = GPS_STRUCT.unpack(data)
    return GpsData(
        lat=v[0], lon=v[1], alt=v[2], speed=v[3], heading=v[4],
        hdop=v[5], sats=v[6], fix=v[7], utc_time=v[8], seq=v[9],
    )


def pack_status(s: StatusData) -> bytes:
    return STATUS_STRUCT.pack(s.mode, s.state, s.uptime, s.error_flags, s.temp_mcu)


def unpack_status(data: bytes) -> StatusData:
    v = STATUS_STRUCT.unpack(data)
    return StatusData(mode=v[0], state=v[1], uptime=v[2], error_flags=v[3], temp_mcu=v[4])


# --------------------------------------------------------------------------
# Çerçeve oluşturma / ayrıştırma
# --------------------------------------------------------------------------
def build_frame(type_byte: int, payload: bytes) -> bytes:
    """type_byte + payload'u tel çerçevesine sar."""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload çok uzun: {len(payload)} > {MAX_PAYLOAD}")
    return SYNC + bytes((len(payload), type_byte)) + payload + END


def command_frame(cmd: int, payload: bytes = b"") -> bytes:
    """Uplink komutu için çerçeve üret."""
    return build_frame(cmd, payload)


def unpack(type_byte: int, payload: bytes):
    """Tipe göre payload'u uygun veri modeline çevir."""
    if type_byte == TYPE_TELEMETRY:
        return unpack_telemetry(payload)
    if type_byte == TYPE_GPS:
        return unpack_gps(payload)
    if type_byte == TYPE_STATUS:
        return unpack_status(payload)
    return payload  # kamera ya da bilinmeyen -> ham bayt


class FrameParser:
    """Bayt akışını besle; tamamlanan (type, payload) çiftlerini döndür."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes):
        self._buf.extend(data)
        frames = []
        while True:
            idx = self._buf.find(SYNC)
            if idx < 0:
                # SYNC başlangıcı kısmen gelebilir -> son baytı sakla
                if len(self._buf) > 1:
                    self._buf = self._buf[-1:]
                break
            if idx > 0:
                del self._buf[:idx]
            if len(self._buf) < 4:  # SYNC + LEN + TYPE
                break
            length = self._buf[2]
            type_byte = self._buf[3]
            need = 4 + length + len(END)
            if len(self._buf) < need:
                break
            payload = bytes(self._buf[4:4 + length])
            tail = bytes(self._buf[4 + length:4 + length + len(END)])
            if tail == END:
                del self._buf[:need]
                frames.append((type_byte, payload))
            else:
                del self._buf[:1]  # hatalı çerçeve -> SYNC'i atla
        return frames


class CameraAssembler:
    """Parçalı kamera karelerini birleştirir; tamamlanan JPEG baytlarını döndürür."""

    def __init__(self) -> None:
        self._frames = {}

    def feed(self, payload: bytes):
        hdr = CAMERA_HDR_STRUCT.size
        if len(payload) < hdr:
            return None
        frame_id, chunk_index, total_chunks, data_len = CAMERA_HDR_STRUCT.unpack(payload[:hdr])
        data = payload[hdr:hdr + data_len]
        self._frames.setdefault(frame_id, {})[chunk_index] = data
        if len(self._frames[frame_id]) >= total_chunks:
            parts = [self._frames[frame_id].get(i) for i in range(total_chunks)]
            if all(p is not None for p in parts):
                del self._frames[frame_id]
                return b"".join(parts)
        return None


def chunk_camera(frame_id: int, data: bytes, chunk_size: int = CAMERA_CHUNK_SIZE):
    """JPEG baytlarını kare parçalarına böl; (TYPE_CAMERA, payload) üretir."""
    total = max(1, math.ceil(len(data) / chunk_size))
    for i in range(total):
        chunk = data[i * chunk_size:(i + 1) * chunk_size]
        payload = CAMERA_HDR_STRUCT.pack(frame_id, i, total, len(chunk)) + chunk
        yield TYPE_CAMERA, payload



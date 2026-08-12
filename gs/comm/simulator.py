"""Donanım gerektirmeyen uydu simülatörü.

Sentetik telemetri, GPS zemin izi, durum paketleri ve sahte kamera karesi üretir.
Ayrıca uplink komutlarını çözüp tepki verir (ARM/DISARM/DEPLOY vb.).
"""
from __future__ import annotations

import io
import math
import time

from PIL import Image, ImageDraw
from PyQt5.QtCore import QTimer

from . import packet
from .link import Link


class SimulatorLink(Link):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._t0 = time.time()
        self._seq = 0
        self._gps_seq = 0
        self._frame_id = 0
        self._timers = []

        self.mode = 1
        self.state = packet.STATE_SAFE
        self.error_flags = 0
        self.uptime = 0
        self._armed = False
        self._cam_enabled = True

        # GPS başlangıç noktası (Ankara civarı)
        self._lat0 = 39.9334
        self._lon0 = 32.8597

    @property
    def name(self) -> str:
        return "Simülatör"

    def open(self) -> None:
        self._t0 = time.time()
        tlm = QTimer(self)
        tlm.timeout.connect(self._tick_telemetry)
        tlm.start(100)  # 10 Hz
        gps = QTimer(self)
        gps.timeout.connect(self._tick_gps)
        gps.start(1000)  # 1 Hz
        stt = QTimer(self)
        stt.timeout.connect(self._tick_status)
        stt.start(2000)  # 0.5 Hz
        cam = QTimer(self)
        cam.timeout.connect(self._tick_camera)
        cam.start(400)  # 2.5 Hz
        self._timers = [tlm, gps, stt, cam]

        self._open = True
        self.connected.emit(True)
        self.status_message.emit("Simülatör başlatıldı (sentetik telemetri + GPS + kamera).")

    def close(self) -> None:
        for t in self._timers:
            t.stop()
        self._timers = []
        self._open = False
        self.connected.emit(False)
        self.status_message.emit("Simülatör durduruldu.")

    def send(self, data: bytes) -> None:
        # Gelen uplink komut çerçevelerini çöz ve tepki ver
        parser = packet.FrameParser()
        for type_byte, payload in parser.feed(data):
            self._handle_command(type_byte, payload)

    # ------------------------------------------------------------------
    # Komut işleme
    # ------------------------------------------------------------------
    def _handle_command(self, cmd: int, payload: bytes) -> None:
        name = packet.COMMAND_NAMES.get(cmd, hex(cmd))
        if cmd == packet.CMD_PING:
            self.status_message.emit("PING alındı -> yanıt gönderiliyor.")
        elif cmd == packet.CMD_ARM:
            self._armed = True
            self.state = packet.STATE_ARMED
            self.status_message.emit("ARM komutu alındı: sistem SİLAHLANDI.")
        elif cmd == packet.CMD_DISARM:
            self._armed = False
            self.state = packet.STATE_SAFE
            self.status_message.emit("DISARM komutu alındı: sistem emniyete alındı.")
        elif cmd == packet.CMD_REBOOT:
            self.uptime = 0
            self.status_message.emit("REBOOT alındı: uptime sıfırlandı.")
        elif cmd == packet.CMD_DEPLOY:
            if self._armed:
                self.state = packet.STATE_DEPLOYED
                self.status_message.emit("DEPLOY alındı: kurtarma sistemi açıldı.")
            else:
                self.status_message.emit("DEPLOY reddedildi: sistem ARMED değil.")
        elif cmd == packet.CMD_CAMERA_ON:
            self._cam_enabled = True
            self.status_message.emit("Kamera açıldı.")
        elif cmd == packet.CMD_CAMERA_OFF:
            self._cam_enabled = False
            self.status_message.emit("Kamera kapatıldı.")
        elif cmd == packet.CMD_SET_MODE:
            if payload:
                self.mode = payload[0]
            self.status_message.emit(f"Mod {self.mode} olarak ayarlandı.")
        elif cmd == packet.CMD_TELEMETRY_RATE:
            if payload:
                self.status_message.emit(f"Telemetri hızı {payload[0]} Hz isteği alındı.")
        else:
            self.status_message.emit(f"Bilinmeyen komut alındı: {name}")

        self._emit_status()  # komuta durum paketiyle yanıt

    # ------------------------------------------------------------------
    # Uçuş profili
    # ------------------------------------------------------------------
    def _flight_profile(self, t: float) -> float:
        """90 saniyelik döngü: yükseliş -> apogee -> paraşütle iniş -> yerde."""
        t = t % 90.0
        if t < 15.0:
            return 3000.0 * (t / 15.0) ** 1.6
        if t < 20.0:
            return 3000.0
        if t < 75.0:
            p = (t - 20.0) / 55.0
            return 3000.0 * (1.0 - p)
        return 0.0

    def _attitude(self, t: float):
        alt = self._flight_profile(t)
        if alt > 100.0:
            roll = 12.0 * math.sin(2.0 * math.pi * t / 3.0)
            pitch = 8.0 * math.sin(2.0 * math.pi * t / 2.3 + 1.0)
            yaw = 60.0 * math.sin(2.0 * math.pi * t / 5.0)
        else:
            roll = 1.5 * math.sin(2.0 * math.pi * t / 8.0)
            pitch = 1.0 * math.sin(2.0 * math.pi * t / 7.0)
            yaw = 0.0
        return roll, pitch, yaw

    # ------------------------------------------------------------------
    # Paket üreticileri
    # ------------------------------------------------------------------
    def _tick_telemetry(self) -> None:
        t = time.time() - self._t0
        alt = self._flight_profile(t)
        roll, pitch, yaw = self._attitude(t)
        self._seq += 1
        self.uptime = int(t)

        tm = packet.TelemetryData(
            seq=self._seq,
            battery_v=11.1 + 0.2 * math.sin(t / 10.0) - 0.15 * min(t / 300.0, 1.5),
            battery_i=0.35 + 0.05 * math.sin(t / 2.0),
            temp_cpu=25.0 + 15.0 * math.sin(t / 12.0) ** 2,
            temp_batt=20.0 + 8.0 * math.sin(t / 15.0) ** 2,
            pressure=1013.25 - alt * 0.12,
            altitude=alt,
            roll=roll, pitch=pitch, yaw=yaw,
            gyro_x=12.0 * math.sin(t / 3.0),
            gyro_y=8.0 * math.sin(t / 2.3 + 1.0),
            gyro_z=60.0 * math.sin(t / 5.0),
            accel_x=0.05 * math.sin(t / 1.5),
            accel_y=0.05 * math.cos(t / 1.7),
            accel_z=9.81,
            mag_x=25.0 * math.cos(yaw * math.pi / 180.0),
            mag_y=25.0 * math.sin(yaw * math.pi / 180.0),
            mag_z=45.0,
            rssi=-60.0 - 8.0 * math.sin(t / 4.0) ** 2,
            flags=0,
        )
        self.data_received.emit(
            packet.build_frame(packet.TYPE_TELEMETRY, packet.pack_telemetry(tm))
        )

    def _tick_gps(self) -> None:
        t = time.time() - self._t0
        alt = self._flight_profile(t)
        # Küçük dairesel zemin izi (ground track)
        ang = 2.0 * math.pi * t / 60.0
        lat = self._lat0 + 0.0022 * math.sin(ang)
        lon = self._lon0 + 0.0030 * math.cos(ang)
        heading = (math.degrees(math.atan2(math.cos(ang), -math.sin(ang))) + 360.0) % 360.0
        self._gps_seq += 1
        g = packet.GpsData(
            lat=lat, lon=lon, alt=alt,
            speed=0.0 if alt < 100.0 else 12.0,
            heading=heading,
            hdop=1.1,
            sats=10,
            fix=3 if alt > 0.0 else 1,
            utc_time=int(time.strftime("%H%M%S")),
            seq=self._gps_seq,
        )
        self.data_received.emit(packet.build_frame(packet.TYPE_GPS, packet.pack_gps(g)))

    def _tick_status(self) -> None:
        self._emit_status()

    def _emit_status(self) -> None:
        s = packet.StatusData(
            mode=self.mode, state=self.state, uptime=self.uptime,
            error_flags=self.error_flags, temp_mcu=30.0,
        )
        self.data_received.emit(packet.build_frame(packet.TYPE_STATUS, packet.pack_status(s)))

    def _tick_camera(self) -> None:
        if not self._cam_enabled:
            return
        self._frame_id += 1
        jpg = self._make_frame(self._frame_id)
        for type_byte, payload in packet.chunk_camera(self._frame_id, jpg):
            self.data_received.emit(packet.build_frame(type_byte, payload))

    def _make_frame(self, frame_id: int) -> bytes:
        w, h = 320, 240
        img = Image.new("RGB", (w, h))
        draw = ImageDraw.Draw(img)
        t = time.time() - self._t0
        for y in range(h):
            r = int(30 + 60 * (y / h) + 40 * math.sin(t + y / 40.0))
            g = int(60 + 60 * (y / h) * math.sin(t / 2.0 + frame_id / 20.0))
            b = int(90 + 90 * (y / h))
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            draw.line([(0, y), (w, y)], fill=(r, g, b))
        cx = int(w / 2 + 60 * math.sin(t / 3.0))
        cy = int(h / 2 + 40 * math.cos(t / 2.5))
        draw.line([(cx - 20, cy), (cx + 20, cy)], fill=(255, 0, 0), width=2)
        draw.line([(cx, cy - 20), (cx, cy + 20)], fill=(255, 0, 0), width=2)
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], outline=(0, 255, 0), width=1)
        draw.text((8, 8), f"SAT-CAM | frame {frame_id}", fill=(255, 255, 255))
        draw.text((8, h - 22), f"t={t:06.1f}s  alt={self._flight_profile(t):.0f}m",
                  fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=55)
        return buf.getvalue()


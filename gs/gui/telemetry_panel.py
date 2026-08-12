"""Sayısal telemetri göstergeleri paneli."""
from __future__ import annotations

from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QLabel, QVBoxLayout, QWidget,
)

from ..comm import packet


class TelemetryPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._vals = {}
        main = QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(4)

        gb = QGroupBox("Durum / Link")
        g = QGridLayout(gb)
        self._row(g, 0, "Link:", "link")
        self._row(g, 1, "Durum:", "state")
        self._row(g, 2, "Mod:", "mode")
        self._row(g, 3, "Uptime (s):", "uptime")
        self._row(g, 4, "Paket #:", "seq")
        self._row(g, 5, "RSSI (dBm):", "rssi")
        main.addWidget(gb)

        gb = QGroupBox("Güç / Sıcaklık")
        g = QGridLayout(gb)
        self._row(g, 0, "Batarya (V):", "bat_v")
        self._row(g, 1, "Akım (A):", "bat_i")
        self._row(g, 2, "CPU sıc. (°C):", "temp_cpu")
        self._row(g, 3, "Bat sıc. (°C):", "temp_batt")
        self._row(g, 4, "MCU sıc. (°C):", "temp_mcu")
        self._row(g, 5, "Basınç (hPa):", "pressure")
        main.addWidget(gb)

        gb = QGroupBox("Attitude / İrtifa")
        g = QGridLayout(gb)
        self._row(g, 0, "İrtifa (m):", "altitude")
        self._row(g, 1, "Roll (°):", "roll")
        self._row(g, 2, "Pitch (°):", "pitch")
        self._row(g, 3, "Yaw (°):", "yaw")
        main.addWidget(gb)

        gb = QGroupBox("GPS")
        g = QGridLayout(gb)
        self._row(g, 0, "Enlem (°):", "lat")
        self._row(g, 1, "Boylam (°):", "lon")
        self._row(g, 2, "İrtifa (m):", "gps_alt")
        self._row(g, 3, "Hız (m/s):", "speed")
        self._row(g, 4, "Yön (°):", "heading")
        self._row(g, 5, "Uydu sayısı:", "sats")
        self._row(g, 6, "Fix:", "fix")
        main.addWidget(gb)

        main.addStretch(1)

    def _row(self, grid: QGridLayout, row: int, label: str, key: str) -> None:
        grid.addWidget(QLabel(label), row, 0)
        val = QLabel("—")
        val.setTextInteractionFlags(val.textInteractionFlags())
        grid.addWidget(val, row, 1)
        self._vals[key] = val

    def set_value(self, key: str, text: str, color: str | None = None) -> None:
        lbl = self._vals.get(key)
        if lbl is None:
            return
        lbl.setText(text)
        if color:
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        else:
            lbl.setStyleSheet("")

    def set_link(self, name: str, connected: bool) -> None:
        if connected:
            self.set_value("link", name, "#2ecc71")
        else:
            self.set_value("link", name + " (kapalı)", "#e74c3c")

    def update_telemetry(self, tm: packet.TelemetryData) -> None:
        self.set_value("bat_v", f"{tm.battery_v:.2f}")
        self.set_value("bat_i", f"{tm.battery_i:.2f}")
        self.set_value("temp_cpu", f"{tm.temp_cpu:.1f}")
        self.set_value("temp_batt", f"{tm.temp_batt:.1f}")
        self.set_value("pressure", f"{tm.pressure:.1f}")
        self.set_value("altitude", f"{tm.altitude:.0f}")
        self.set_value("roll", f"{tm.roll:.1f}")
        self.set_value("pitch", f"{tm.pitch:.1f}")
        self.set_value("yaw", f"{tm.yaw:.1f}")
        self.set_value("rssi", f"{tm.rssi:.0f}")
        self.set_value("seq", str(tm.seq))

    def update_gps(self, g: packet.GpsData) -> None:
        self.set_value("lat", f"{g.lat:.5f}")
        self.set_value("lon", f"{g.lon:.5f}")
        self.set_value("gps_alt", f"{g.alt:.0f}")
        self.set_value("speed", f"{g.speed:.1f}")
        self.set_value("heading", f"{g.heading:.0f}")
        self.set_value("sats", str(g.sats))
        self.set_value("fix", self._fix_text(g.fix))

    def update_status(self, s: packet.StatusData) -> None:
        self.set_value("mode", str(s.mode))
        self.set_value("uptime", str(s.uptime))
        self.set_value("temp_mcu", f"{s.temp_mcu:.1f}")
        state_name = packet.STATE_NAMES.get(s.state, str(s.state))
        if s.state == packet.STATE_ARMED:
            self.set_value("state", state_name, "#e67e22")
        elif s.state in (packet.STATE_FLIGHT, packet.STATE_DEPLOYED):
            self.set_value("state", state_name, "#3498db")
        else:
            self.set_value("state", state_name, "#2ecc71")

    @staticmethod
    def _fix_text(fix: int) -> str:
        return {0: "yok", 1: "GPS", 2: "DGPS", 3: "3D", 4: "RTK"}.get(fix, str(fix))

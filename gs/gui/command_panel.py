"""Peyke komut gönderme paneli (uplink)."""
from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from ..comm import packet


class CommandPanel(QWidget):
    command_requested = pyqtSignal(int, bytes)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        main = QVBoxLayout(self)
        main.setContentsMargins(4, 4, 4, 4)
        main.setSpacing(6)

        gb = QGroupBox("Temel Komutlar")
        g = QGridLayout(gb)
        btn = QPushButton("PING")
        btn.clicked.connect(lambda: self.command_requested.emit(packet.CMD_PING, b""))
        g.addWidget(btn, 0, 0)

        arm = QPushButton("ARM")
        arm.setStyleSheet("background:#c0392b; color:white; font-weight:bold;")
        arm.clicked.connect(self._confirm_arm)
        g.addWidget(arm, 0, 1)

        dis = QPushButton("DISARM")
        dis.setStyleSheet("background:#e67e22; color:white; font-weight:bold;")
        dis.clicked.connect(self._confirm_disarm)
        g.addWidget(dis, 0, 2)

        dep = QPushButton("DEPLOY")
        dep.setStyleSheet("background:#2980b9; color:white;")
        dep.clicked.connect(self._confirm_deploy)
        g.addWidget(dep, 1, 0)

        reb = QPushButton("REBOOT")
        reb.clicked.connect(lambda: self.command_requested.emit(packet.CMD_REBOOT, b""))
        g.addWidget(reb, 1, 1)

        cam_on = QPushButton("CAMERA ON")
        cam_on.clicked.connect(lambda: self.command_requested.emit(packet.CMD_CAMERA_ON, b""))
        g.addWidget(cam_on, 1, 2)

        cam_off = QPushButton("CAMERA OFF")
        cam_off.clicked.connect(lambda: self.command_requested.emit(packet.CMD_CAMERA_OFF, b""))
        g.addWidget(cam_off, 2, 0)
        main.addWidget(gb)

        gb = QGroupBox("Ayar Komutları")
        g = QGridLayout(gb)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([str(i) for i in range(1, 6)])
        g.addWidget(self._mode_combo, 0, 0)
        set_mode = QPushButton("SET MODE")
        set_mode.clicked.connect(self._send_set_mode)
        g.addWidget(set_mode, 0, 1)

        self._rate_spin = QSpinBox()
        self._rate_spin.setRange(1, 50)
        self._rate_spin.setValue(10)
        g.addWidget(self._rate_spin, 1, 0)
        set_rate = QPushButton("TELEMETRY RATE")
        set_rate.clicked.connect(self._send_rate)
        g.addWidget(set_rate, 1, 1)
        main.addWidget(gb)

        gb = QGroupBox("Ham Veri (RAW)")
        v = QVBoxLayout(gb)
        self._raw_edit = QLineEdit()
        self._raw_edit.setPlaceholderText("ASCII metin veya 0x ile HEX (örn: 0x01 0x02)")
        v.addWidget(self._raw_edit)
        send_raw = QPushButton("GÖNDER")
        send_raw.clicked.connect(self._send_raw)
        v.addWidget(send_raw)
        main.addWidget(gb)

        main.addStretch(1)

    # ------------------------------------------------------------------
    # Onay gerektiren komutlar
    # ------------------------------------------------------------------
    def _confirm_arm(self) -> None:
        if self._confirm("ARM Onayı", "Uyduyu SİLAHLANDIRMAK istediğinizden emin misiniz?"):
            self.command_requested.emit(packet.CMD_ARM, b"")

    def _confirm_disarm(self) -> None:
        if self._confirm("DISARM Onayı", "Uyduyu emniyete almak (DISARM) istediğinizden emin misiniz?"):
            self.command_requested.emit(packet.CMD_DISARM, b"")

    def _confirm_deploy(self) -> None:
        if self._confirm("DEPLOY Onayı", "Kurtarma/paraşüt sistemini AÇMAK istediğinizden emin misiniz?"):
            self.command_requested.emit(packet.CMD_DEPLOY, b"")

    @staticmethod
    def _confirm(title: str, text: str) -> bool:
        r = QMessageBox.question(
            None, title, text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return r == QMessageBox.Yes

    def _send_set_mode(self) -> None:
        mode = int(self._mode_combo.currentText())
        self.command_requested.emit(packet.CMD_SET_MODE, bytes([mode]))

    def _send_rate(self) -> None:
        rate = self._rate_spin.value()
        self.command_requested.emit(packet.CMD_TELEMETRY_RATE, bytes([rate]))

    def _send_raw(self) -> None:
        text = self._raw_edit.text().strip()
        if not text:
            return
        if text.lower().startswith("0x"):
            hexs = text.replace("0x", " ").replace(",", " ").split()
            try:
                data = bytes(int(h, 16) for h in hexs)
            except ValueError:
                QMessageBox.warning(self, "Hata", "Geçersiz HEX veri.")
                return
        else:
            data = text.encode("ascii", "replace")
        self.command_requested.emit(packet.CMD_RAW, data)

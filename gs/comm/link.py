"""Bağlantı soyutlaması: gerçek seri port (pyserial) ve temel Link arayüzü."""
from __future__ import annotations

import threading

import serial
from PyQt5.QtCore import QObject, pyqtSignal

from . import packet


class Link(QObject):
    """Tüm bağlantı türleri için ortak arayüz.

    Sinyaller:
        connected(bool)      -- bağlantı durumu değişti
        data_received(bytes) -- gelen ham baytlar (ayrıştırılmamış)
        status_message(str)  -- durum/log mesajı
    """

    connected = pyqtSignal(bool)
    data_received = pyqtSignal(bytes)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def name(self) -> str:
        return "Link"

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def send(self, data: bytes) -> None:
        raise NotImplementedError

    def send_command(self, cmd: int, payload: bytes = b"") -> None:
        """Uplink komutu gönder (çerçevelenmiş)."""
        self.send(packet.command_frame(cmd, payload))


class SerialLink(Link):
    """Gerçek seri port üzerinden bağlantı (pyserial)."""

    def __init__(self, port: str, baudrate: int = 115200, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._thread = None
        self._stop = threading.Event()

    @property
    def name(self) -> str:
        return f"Seri {self.port} @ {self.baudrate}"

    def open(self) -> None:
        self._serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
        self._stop.clear()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        self._open = True
        self.connected.emit(True)
        self.status_message.emit(f"Bağlandı: {self.port} @ {self.baudrate}")

    def _reader(self) -> None:
        while not self._stop.is_set():
            try:
                n = self._serial.in_waiting
                data = self._serial.read(n if n else 1)
            except Exception as exc:  # noqa: BLE001
                self.status_message.emit(f"Seri okuma hatası: {exc}")
                break
            if data:
                self.data_received.emit(data)
        if not self._stop.is_set():
            self._open = False
            self.connected.emit(False)
            self.status_message.emit("Bağlantı koptu.")

    def send(self, data: bytes) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.write(data)
            except Exception as exc:  # noqa: BLE001
                self.status_message.emit(f"Seri yazma hatası: {exc}")

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._serial:
            try:
                self._serial.close()
            except Exception:  # noqa: BLE001
                pass
        self._open = False
        self.connected.emit(False)
        self.status_message.emit(f"Bağlantı kapatıldı: {self.port}")


def list_serial_ports():
    """Sistemdeki seri portları listele."""
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:  # noqa: BLE001
        return []

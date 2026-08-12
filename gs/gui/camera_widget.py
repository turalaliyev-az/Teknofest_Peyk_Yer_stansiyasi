"""Kamera görüntüleme widget'ı + webcam/UDP kaynakları."""
from __future__ import annotations

import socket
import threading

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

# NOT: cv2 burada import edilmez! OpenCV kendi gömülü Qt'sini taşır ve modül
# import edildiğinde QT_QPA_PLATFORM_PLUGIN_PATH'i kendi dizinine çevirir. Bu
# da QApplication henüz oluşturulmadan cv2 yüklenirse PyQt5'in "xcb" eklentisini
# bulamamasına neden olur. Bu yüzden cv2 yalnızca WebcamSource içinde lazy import
# edilir (yani webcam gerçekten seçildiğinde).


class CameraWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(260, 200)
        self._label = QLabel("Kamera bekleniyor...")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("background: #000000; color: #7f8c8d;")
        self._pixmap = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def show_jpeg(self, data: bytes) -> None:
        img = QImage.fromData(data)
        if not img.isNull():
            self.show_qimage(img)

    def show_qimage(self, img: QImage) -> None:
        self._pixmap = QPixmap.fromImage(img)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        self._label.setPixmap(
            self._pixmap.scaled(
                self._label.size(), Qt.KeepAspectRatio, Qt.FastTransformation
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def clear(self) -> None:
        self._pixmap = None
        self._label.setPixmap(QPixmap())
        self._label.setText("Kamera bekleniyor...")


class WebcamSource(QObject):
    """OpenCV ile USB/webcam'den kare okur."""
    frame_ready = pyqtSignal(QImage)
    error = pyqtSignal(str)

    def __init__(self, index: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self._cap = None
        self._stop = threading.Event()
        self._thread = None

    def start(self) -> None:
        import cv2  # lazy import: PyQt5 platform eklentisiyle çakışmayı önler
        self._cap = cv2.VideoCapture(self.index)
        if not self._cap.isOpened():
            self.error.emit(f"Webcam {self.index} açılamadı")
            self._cap = None
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        import cv2
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                self.error.emit("Webcam karesi okunamadı")
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
            self.frame_ready.emit(img)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._cap:
            self._cap.release()
            self._cap = None


class UdpCameraSource(QObject):
    """UDP üzerinden JPEG kareleri alır (her datagram = bir JPEG kare)."""
    frame_ready = pyqtSignal(QImage)
    error = pyqtSignal(str)

    def __init__(self, port: int = 5600, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self._sock = None
        self._stop = threading.Event()
        self._thread = None

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.settimeout(0.5)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                data, _addr = self._sock.recvfrom(65536)
            except socket.timeout:
                continue
            except OSError as exc:
                self.error.emit(f"UDP hatası: {exc}")
                break
            img = QImage.fromData(data)
            if not img.isNull():
                self.frame_ready.emit(img)

    def stop(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread:
            self._thread.join(timeout=1.0)

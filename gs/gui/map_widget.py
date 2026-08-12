"""Google Earth/Maps benzeri karolu (tile) harita: uydu görüntüsü, kaydırma, zoom.

Çevrimiçi karo sunucularından (Esri World Imagery uydu görüntüsü, OpenStreetMap
yol haritası) karoları indirir, diskte önbelleğe alır ve Web Mercator (EPSG:3857)
projeksiyonuyla çizer. Fare ile kaydırma, tekerlek ile zoom yapılır. İnternet
yoksa koyu zemin + ızgara üzerinde konum/iz gösterilmeye devam eder.
"""
from __future__ import annotations

import math
import os
import time

from PyQt5.QtCore import QPointF, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

TILE_SIZE = 256
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "gs_tiles")

# Karo kaynakları: "Uydu (Esri)" Google Earth tarzı uydu görüntüsü,
# "Harita (OSM)" Google Maps tarzı yol haritası.
SOURCES = {
    "Uydu (Esri)": {
        "slug": "esri",
        "url": ("https://server.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        "ext": "jpg",
    },
    "Harita (OSM)": {
        "slug": "osm",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "ext": "png",
    },
}

USER_AGENT = b"Mozilla/5.0 (Teknofest Ground Station)"


# --------------------------------------------------------------------------
# Web Mercator yardımcıları (karo birimlerinde)
# --------------------------------------------------------------------------
def _lon_to_x(lon: float, z: int) -> float:
    return (lon + 180.0) / 360.0 * (2 ** z)


def _lat_to_y(lat: float, z: int) -> float:
    lat = max(-85.05112878, min(85.05112878, lat))
    r = math.radians(lat)
    return (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * (2 ** z)


def _x_to_lon(x: float, z: int) -> float:
    return x / (2 ** z) * 360.0 - 180.0


def _y_to_lat(y: float, z: int) -> float:
    n = math.pi - 2.0 * math.pi * y / (2 ** z)
    return math.degrees(math.atan(math.sinh(n)))


class MapWidget(QWidget):
    """Karo harita + kontrol çubuğu (kaynak, zoom, konum, izi temizle)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(260, 200)
        self._canvas = _MapCanvas()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        self._src_combo = QComboBox()
        self._src_combo.addItems(list(SOURCES.keys()))
        self._src_combo.currentTextChanged.connect(self._on_source)
        bar.addWidget(self._src_combo)

        zout = QPushButton("−")
        zout.setFixedWidth(26)
        zout.setToolTip("Uzaklaştır")
        zout.clicked.connect(lambda: self._canvas.zoom_by(-1))
        bar.addWidget(zout)
        zin = QPushButton("+")
        zin.setFixedWidth(26)
        zin.setToolTip("Yakınlaştır")
        zin.clicked.connect(lambda: self._canvas.zoom_by(1))
        bar.addWidget(zin)

        fit = QPushButton("⌖ Konum")
        fit.setToolTip("Uydu konumuna git")
        fit.clicked.connect(self._canvas.zoom_to_latest)
        bar.addWidget(fit)

        clr = QPushButton("✕ İz")
        clr.setToolTip("Zemin izini temizle")
        clr.clicked.connect(self.clear_track)
        bar.addWidget(clr)

        self._info = QLabel("—")
        bar.addWidget(self._info)
        bar.addStretch(1)
        lay.addLayout(bar)

        self._canvas.position_changed.connect(self._info.setText)
        lay.addWidget(self._canvas)

    # --- main_window'un kullandığı arayüz ---
    def set_gps(self, lat: float, lon: float) -> None:
        self._canvas.set_gps(lat, lon)

    def clear_track(self) -> None:
        self._canvas.clear_track()

    def latest_position(self):
        return self._canvas.latest_position()

    def _on_source(self, name: str) -> None:
        self._canvas.set_source(name)

class _MapCanvas(QWidget):
    """Karoları çizen ve etkileşimi (kaydırma/zoom) yöneten tuval."""

    position_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)
        self.setMinimumSize(240, 160)

        self._nam = QNetworkAccessManager(self)
        self._nam.finished.connect(self._on_reply)

        self._mem = {}          # karo anahtarı -> QPixmap
        self._req = set()       # indirilmekte olan karo anahtarları
        self._failed = {}       # başarısız karolar -> zaman damgası (backoff)
        self._reply_map = {}    # QNetworkReply -> (anahtar, z, x, y)

        self._source = list(SOURCES.keys())[0]
        self._zoom = 5
        self._cx = _lon_to_x(32.8597, self._zoom)
        self._cy = _lat_to_y(39.9334, self._zoom)

        self._pos = None
        self._track = []
        self._track_max = 3000

        self._drag = False
        self._drag_start = None
        self._drag_cx = 0.0
        self._drag_cy = 0.0

    # ------------------------------------------------------------------
    # Genel arayüz
    # ------------------------------------------------------------------
    def latest_position(self):
        return self._pos

    def set_source(self, name: str) -> None:
        if name == self._source:
            return
        self._source = name
        self.update()

    def set_gps(self, lat: float, lon: float) -> None:
        self._pos = (lat, lon)
        self._track.append((lat, lon))
        if len(self._track) > self._track_max:
            del self._track[: len(self._track) - self._track_max]
        self.update()
        self._emit_info()

    def clear_track(self) -> None:
        self._track.clear()
        self.update()

    def zoom_by(self, delta: int) -> None:
        self._set_zoom(self._zoom + delta)

    def _set_zoom(self, z: int) -> None:
        z = max(2, min(19, z))
        if z == self._zoom:
            return
        self._zoom = z
        self.update()
        self._emit_info()

    def zoom_to_latest(self) -> None:
        if self._pos is not None:
            self._zoom = 15
            self._cx = _lon_to_x(self._pos[1], self._zoom)
            self._cy = _lat_to_y(self._pos[0], self._zoom)
        else:
            self._zoom = 6
            self._cx = _lon_to_x(32.8597, self._zoom)
            self._cy = _lat_to_y(39.9334, self._zoom)
        self.update()
        self._emit_info()

    def _emit_info(self) -> None:
        lon = _x_to_lon(self._cx, self._zoom)
        lat = _y_to_lat(self._cy, self._zoom)
        extra = ""
        if self._pos:
            extra = f"   uydu: {self._pos[0]:.5f}, {self._pos[1]:.5f}"
        self.position_changed.emit(f"{lat:.4f}, {lon:.4f}   z={self._zoom}{extra}")

    # ------------------------------------------------------------------
    # Karo yükleme / önbellek
    # ------------------------------------------------------------------
    def _tile_key(self, z: int, x: int, y: int) -> str:
        return f"{SOURCES[self._source]['slug']}/{z}/{x}/{y}"

    def _tile_path(self, z: int, x: int, y: int) -> str:
        src = SOURCES[self._source]
        return os.path.join(CACHE_DIR, src["slug"], str(z), str(x), f"{y}.{src['ext']}")

    def _get_tile(self, z: int, x: int, y: int):
        key = self._tile_key(z, x, y)
        if key in self._mem:
            return self._mem[key]
        pm = self._load_disk(z, x, y)
        if pm is not None:
            self._mem[key] = pm
            return pm
        self._request_tile(z, x, y)
        return None

    def _load_disk(self, z: int, x: int, y: int):
        path = self._tile_path(z, x, y)
        if os.path.exists(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return pm
        return None

    def _request_tile(self, z: int, x: int, y: int) -> None:
        key = self._tile_key(z, x, y)
        if key in self._req:
            return
        now = time.monotonic()
        if key in self._failed and now - self._failed[key] < 5.0:
            return  # kısa süre içinde tekrar deneme (offline koruması)
        self._req.add(key)
        src = SOURCES[self._source]
        url = src["url"].format(z=z, x=x, y=y)
        req = QNetworkRequest(QUrl(url))
        req.setRawHeader(b"User-Agent", USER_AGENT)
        reply = self._nam.get(req)
        self._reply_map[reply] = (key, z, x, y)

    def _on_reply(self, reply) -> None:
        info = self._reply_map.pop(reply, None)
        if info is None:
            reply.deleteLater()
            return
        key, z, x, y = info
        self._req.discard(key)
        if reply.error() == reply.NoError:
            data = bytes(reply.readAll())
            pm = QPixmap()
            if pm.loadFromData(data) and not pm.isNull():
                self._mem[key] = pm
                self._failed.pop(key, None)
                self._save_disk(z, x, y, data)
                if len(self._mem) > 800:
                    for k in list(self._mem.keys())[:300]:
                        del self._mem[k]
                self.update()
        else:
            self._failed[key] = time.monotonic()
        reply.deleteLater()

    def _save_disk(self, z: int, x: int, y: int, data: bytes) -> None:
        try:
            path = self._tile_path(z, x, y)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------
    def _to_widget(self, lat: float, lon: float) -> QPointF:
        x = _lon_to_x(lon, self._zoom)
        y = _lat_to_y(lat, self._zoom)
        return QPointF(
            x * TILE_SIZE - self._cx * TILE_SIZE + self.width() / 2.0,
            y * TILE_SIZE - self._cy * TILE_SIZE + self.height() / 2.0,
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(15, 18, 25))
        w, h = self.width(), self.height()
        z = self._zoom
        px_c = self._cx * TILE_SIZE
        py_c = self._cy * TILE_SIZE

        tx0 = self._cx - (w / 2.0) / TILE_SIZE
        ty0 = self._cy - (h / 2.0) / TILE_SIZE
        x0 = int(math.floor(tx0))
        y0 = int(math.floor(ty0))
        x1 = int(math.floor(tx0 + w / TILE_SIZE)) + 1
        y1 = int(math.floor(ty0 + h / TILE_SIZE)) + 1
        n = 2 ** z

        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                if tx < 0 or ty < 0 or tx >= n or ty >= n:
                    continue
                sx = int(tx * TILE_SIZE - px_c + w / 2.0)
                sy = int(ty * TILE_SIZE - py_c + h / 2.0)
                pm = self._get_tile(z, tx, ty)
                if pm is not None:
                    p.drawPixmap(sx, sy, pm)
                else:
                    p.fillRect(sx, sy, TILE_SIZE, TILE_SIZE, QColor(30, 34, 42))
                    p.setPen(QColor(255, 255, 255, 18))
                    p.drawRect(sx, sy, TILE_SIZE - 1, TILE_SIZE - 1)

        self._draw_grid(p)

        # Zemin izi (ground track)
        if len(self._track) > 1:
            p.setPen(QPen(QColor(0, 220, 255, 210), 2))
            prev = None
            for (la, lo) in self._track:
                pt = self._to_widget(la, lo)
                if prev is not None:
                    p.drawLine(prev, pt)
                prev = pt

        # Uydu konumu
        if self._pos is not None:
            c = self._to_widget(self._pos[0], self._pos[1])
            p.setPen(QPen(QColor(255, 70, 70), 2))
            p.setBrush(QColor(255, 50, 50))
            p.drawEllipse(c, 7, 7)
            p.setBrush(Qt.NoBrush)
            p.drawLine(int(c.x()) - 14, int(c.y()), int(c.x()) + 14, int(c.y()))
            p.drawLine(int(c.x()), int(c.y()) - 14, int(c.x()), int(c.y()) + 14)
        p.end()

    def _draw_grid(self, p: QPainter) -> None:
        step = 10.0
        p.setPen(QPen(QColor(255, 255, 255, 36)))
        for lat in range(-80, 81, int(step)):
            y = int(_lat_to_y(lat, self._zoom) * TILE_SIZE
                    - self._cy * TILE_SIZE + self.height() / 2.0)
            p.drawLine(0, y, self.width(), y)
        for lon in range(-180, 181, int(step)):
            x = int(_lon_to_x(lon, self._zoom) * TILE_SIZE
                    - self._cx * TILE_SIZE + self.width() / 2.0)
            p.drawLine(x, 0, x, self.height())

    # ------------------------------------------------------------------
    # Etkileşim (kaydırma + zoom)
    # ------------------------------------------------------------------
    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._drag = True
            self._drag_start = e.pos()
            self._drag_cx = self._cx
            self._drag_cy = self._cy
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag and self._drag_start is not None:
            dx = (e.pos().x() - self._drag_start.x()) / TILE_SIZE
            dy = (e.pos().y() - self._drag_start.y()) / TILE_SIZE
            self._cx = self._drag_cx - dx
            self._cy = self._drag_cy - dy
            self.update()
            self._emit_info()

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._drag = False
            self.unsetCursor()

    def wheelEvent(self, e) -> None:  # noqa: N802
        delta = 1 if e.angleDelta().y() > 0 else -1
        mx = e.pos().x() - self.width() / 2.0
        my = e.pos().y() - self.height() / 2.0
        lat = _y_to_lat(self._cy + my / TILE_SIZE, self._zoom)
        lon = _x_to_lon(self._cx + mx / TILE_SIZE, self._zoom)
        z = max(2, min(19, self._zoom + delta))
        if z != self._zoom:
            self._zoom = z
            self._cx = _lon_to_x(lon, z) - mx / TILE_SIZE
            self._cy = _lat_to_y(lat, z) - my / TILE_SIZE
            self.update()
            self._emit_info()



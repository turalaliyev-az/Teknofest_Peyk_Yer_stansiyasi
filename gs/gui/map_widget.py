"""GPS konumunu dünya haritası üzerinde gösteren widget (equirectangular)."""
from __future__ import annotations

import os
from collections import deque

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PyQt5.QtWidgets import QWidget

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets")


class MapWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(260, 180)
        self._map = self._load_map()
        self._track = deque(maxlen=3000)
        self._pos = None  # (lat, lon)
        self._latest = None

    @staticmethod
    def _load_map() -> QPixmap | None:
        for name in ("world_map.jpg", "world_map.png"):
            path = os.path.join(ASSETS_DIR, name)
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    return pm
        return None

    def set_gps(self, lat: float, lon: float) -> None:
        self._pos = (lat, lon)
        self._latest = (lat, lon)
        self._track.append((lat, lon))
        self.update()

    def clear_track(self) -> None:
        self._track.clear()

    def _map_rect(self):
        w = self.width()
        h = self.height()
        if self._map is None:
            return QPointF(0, 0), QPointF(w, h)
        aspect = self._map.width() / max(1, self._map.height())
        if w / max(1, h) > aspect:
            mh = h
            mw = int(h * aspect)
        else:
            mw = w
            mh = int(w / aspect)
        x0 = (w - mw) / 2
        y0 = (h - mh) / 2
        return QPointF(x0, y0), QPointF(x0 + mw, y0 + mh)

    def _to_px(self, lat: float, lon: float, r0: QPointF, r1: QPointF) -> QPointF:
        x = r0.x() + (lon + 180.0) / 360.0 * (r1.x() - r0.x())
        y = r0.y() + (90.0 - lat) / 180.0 * (r1.y() - r0.y())
        return QPointF(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(13, 17, 26))
        r0, r1 = self._map_rect()

        if self._map is not None:
            p.drawPixmap(QRectF_rect(r0, r1), self._map)
        else:
            p.fillRect(QRectF_rect(r0, r1), QColor(20, 45, 75))

        # Enlem/boylam ızgarası
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setWidth(1)
        p.setPen(pen)
        for lon in range(-180, 181, 30):
            x = r0.x() + (lon + 180.0) / 360.0 * (r1.x() - r0.x())
            p.drawLine(int(x), int(r0.y()), int(x), int(r1.y()))
        for lat in range(-90, 91, 30):
            y = r0.y() + (90.0 - lat) / 180.0 * (r1.y() - r0.y())
            p.drawLine(int(r0.x()), int(y), int(r1.x()), int(y))

        # Zemin izi (ground track)
        if len(self._track) > 1:
            pts = [self._to_px(la, lo, r0, r1) for (la, lo) in self._track]
            p.setPen(QPen(QColor(0, 210, 255, 200), 2))
            p.drawPolyline(QPolygonF(pts))

        # Uydu konumu
        if self._pos is not None:
            lat, lon = self._pos
            c = self._to_px(lat, lon, r0, r1)
            p.setPen(QPen(QColor(255, 80, 80), 2))
            p.setBrush(QColor(255, 60, 60))
            p.drawEllipse(c, 6, 6)
            p.setBrush(Qt.NoBrush)
            p.drawLine(int(c.x()) - 12, int(c.y()), int(c.x()) + 12, int(c.y()))
            p.drawLine(int(c.x()), int(c.y()) - 12, int(c.x()), int(c.y()) + 12)


def QRectF_rect(r0: QPointF, r1: QPointF):
    from PyQt5.QtCore import QRectF
    return QRectF(r0.x(), r0.y(), r1.x() - r0.x(), r1.y() - r0.y())

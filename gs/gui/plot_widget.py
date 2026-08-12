"""Gerçek zamanlı telemetri grafikleri (pyqtgraph)."""
from __future__ import annotations

import time
from collections import deque

import pyqtgraph as pg


class PlotWidget(pg.GraphicsLayoutWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setBackground("#10131c")
        pg.setConfigOption("foreground", "#cccccc")
        pg.setConfigOption("antialias", True)
        self._t0 = time.time()
        self._maxlen = 1500
        self._times = deque(maxlen=self._maxlen)
        self._data = {}
        self._curves = {}

        self._make_plot("volt", "Batarya Gerilimi (V)", [("bat_v", "Gerilim", "#2ecc71")])
        self._make_plot(
            "temp", "Sıcaklık (°C)",
            [("temp_cpu", "CPU", "#e74c3c"), ("temp_batt", "Batarya", "#f1c40f")],
        )
        self._make_plot("alt", "İrtifa (m)", [("altitude", "İrtifa", "#3498db")])
        self._make_plot(
            "att", "Attitude (°)",
            [("roll", "Roll", "#e74c3c"), ("pitch", "Pitch", "#2ecc71"), ("yaw", "Yaw", "#3498db")],
        )
        self._make_plot("rssi", "RSSI (dBm)", [("rssi", "RSSI", "#9b59b6")])

    def _make_plot(self, key: str, title: str, series) -> None:
        p = self.addPlot(title=title)
        p.showGrid(x=True, y=True, alpha=0.2)
        p.addLegend(offset=(8, 8))
        p.setLabel("bottom", "Zaman", units="s")
        for skey, sname, color in series:
            self._curves[skey] = p.plot(pen=pg.mkPen(color, width=2), name=sname)
            self._data[skey] = deque(maxlen=self._maxlen)
        self.nextRow()

    def add_sample(self, values: dict) -> None:
        """values: {seri_anahtarı: değer} — bilinen anahtarları grafikler."""
        t = time.time() - self._t0
        self._times.append(t)
        tt = list(self._times)
        for skey, val in values.items():
            if skey in self._data:
                self._data[skey].append(val)
                self._curves[skey].setData(tt, list(self._data[skey]))

    def reset(self) -> None:
        self._times.clear()
        for d in self._data.values():
            d.clear()
        self._t0 = time.time()

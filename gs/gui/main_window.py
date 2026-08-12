"""Ana pencere: tüm bileşenleri birleştirir."""
from __future__ import annotations

import time

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit, QPushButton,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from ..comm import packet
from ..comm.csv_parser import CsvLineParser
from ..comm.link import SerialLink, list_serial_ports
from ..comm.simulator import SimulatorLink
from .camera_widget import CameraWidget, UdpCameraSource, WebcamSource
from .command_panel import CommandPanel
from .globe3d_widget import Globe3DWidget
from .map_widget import MapWidget
from .plot_widget import PlotWidget
from .telemetry_panel import TelemetryPanel

BAUD_RATES = ["9600", "19200", "38400", "57600", "115200", "230400", "460800"]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Teknofest Yer İstasyonu")
        self.resize(1440, 900)

        self._link = None
        self._parser = packet.FrameParser()
        self._csv_parser = CsvLineParser()
        self._csv_seen = False
        self._cam_assembler = packet.CameraAssembler()
        self._webcam = None
        self._udp = None

        self._counters = {"tel": 0, "gps": 0, "sts": 0, "cam": 0, "tx": 0}
        self._rx_bytes = 0
        self._hex_rx = False
        self._hex_buf = bytearray()
        self._last_bad_warn = 0.0
        self._last_rx = time.time()

        self._build_ui()
        self.command_panel.command_requested.connect(self._send_command)
        self._build_control_bar()

        self._hex_timer = QTimer(self)
        self._hex_timer.setInterval(500)
        self._hex_timer.timeout.connect(self._flush_hex)

        self._counters_lbl = QLabel("TEL: 0  GPS: 0  STS: 0  CAM: 0  RX: 0 B  TX: 0")
        self.statusBar().addPermanentWidget(self._counters_lbl)
        self.statusBar().showMessage("Hazır. Bağlanmak için Simülatör veya Seri Port seçin.")

    # ------------------------------------------------------------------
    # Arayüz kurulumu
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        self._bar = QWidget()
        bar_layout = QHBoxLayout(self._bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._bar)

        # Sol: kamera + telemetri
        self.camera = CameraWidget()
        self.telemetry = TelemetryPanel()
        left = QSplitter(Qt.Vertical)
        left.addWidget(self.camera)
        left.addWidget(self.telemetry)
        left.setSizes([320, 400])

        # Orta: 3D
        self.globe = Globe3DWidget()

        # Sağ: harita + komut
        self.map = MapWidget()
        self.command_panel = CommandPanel()
        right = QSplitter(Qt.Vertical)
        right.addWidget(self.map)
        right.addWidget(self.command_panel)
        right.setSizes([420, 300])

        main_split = QSplitter(Qt.Horizontal)
        main_split.addWidget(left)
        main_split.addWidget(self.globe)
        main_split.addWidget(right)
        main_split.setSizes([380, 560, 380])

        self.plot = PlotWidget()
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setPlaceholderText("Log...")

        bottom = QSplitter(Qt.Vertical)
        bottom.addWidget(main_split)
        bottom.addWidget(self.plot)
        bottom.addWidget(self.log_view)
        bottom.setSizes([560, 280, 120])

        outer.addWidget(bottom)
        self.setCentralWidget(central)

    def _build_control_bar(self) -> None:
        bar = self._bar.layout()

        bar.addWidget(QLabel("Bağlantı:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Simülatör", "Seri Port"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        bar.addWidget(self._mode_combo)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setMinimumWidth(150)
        self._port_combo.setEnabled(False)
        bar.addWidget(self._port_combo)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setToolTip("Portları yenile")
        refresh_btn.clicked.connect(self._refresh_ports)
        bar.addWidget(refresh_btn)

        self._baud_combo = QComboBox()
        self._baud_combo.addItems(BAUD_RATES)
        self._baud_combo.setCurrentText("115200")
        bar.addWidget(self._baud_combo)

        self._connect_btn = QPushButton("Bağlan")
        self._connect_btn.clicked.connect(self._toggle_connect)
        bar.addWidget(self._connect_btn)

        self._hex_btn = QPushButton("Ham RX: OFF")
        self._hex_btn.setCheckable(True)
        self._hex_btn.setToolTip("Gelen ham baytları hex olarak logla (teşhis için)")
        self._hex_btn.toggled.connect(self._toggle_hex)
        bar.addWidget(self._hex_btn)

        bar.addSpacing(16)

        bar.addWidget(QLabel("Kamera:"))
        self._cam_combo = QComboBox()
        self._cam_combo.addItems(["Uydu Linki", "Webcam", "UDP"])
        self._cam_combo.currentTextChanged.connect(self._on_camera_source_changed)
        bar.addWidget(self._cam_combo)

        self._webcam_spin = QSpinBox()
        self._webcam_spin.setRange(0, 8)
        self._webcam_spin.setToolTip("Webcam indeksi")
        bar.addWidget(self._webcam_spin)

        self._udp_spin = QSpinBox()
        self._udp_spin.setRange(1, 65535)
        self._udp_spin.setValue(5600)
        self._udp_spin.setToolTip("UDP kamera portu")
        bar.addWidget(self._udp_spin)

        bar.addStretch(1)

        self._armed_lbl = QLabel("● SAFE")
        self._armed_lbl.setStyleSheet("color:#2ecc71; font-weight:bold;")
        bar.addWidget(self._armed_lbl)

    # ------------------------------------------------------------------
    # Bağlantı yönetimi
    # ------------------------------------------------------------------
    def _on_mode_changed(self, text: str) -> None:
        serial = text == "Seri Port"
        self._port_combo.setEnabled(serial)
        self._baud_combo.setEnabled(serial)
        if serial:
            self._refresh_ports()

    def _refresh_ports(self) -> None:
        self._port_combo.clear()
        ports = list_serial_ports()
        self._port_combo.addItems(ports)
        if not ports:
            self._port_combo.setEditText("")

    def _toggle_connect(self) -> None:
        if self._link and self._link.is_open:
            self._close_link()
        else:
            self._open_link()

    def _open_link(self) -> None:
        mode = self._mode_combo.currentText()
        if mode == "Simülatör":
            link = SimulatorLink()
        else:
            port = self._port_combo.currentText().strip()
            if not port:
                self._log("Seri port seçilmedi.")
                return
            baud = int(self._baud_combo.currentText())
            link = SerialLink(port, baud)

        self._link = link
        link.data_received.connect(self._on_data)
        link.status_message.connect(self._log)
        link.connected.connect(self._on_connected)
        try:
            link.open()
        except Exception as exc:  # noqa: BLE001
            self._log(f"Bağlantı hatası: {exc}")
            self._link = None
            return
        self._log(f"Bağlantı açıldı: {link.name}")

    def _close_link(self) -> None:
        if self._link:
            self._link.close()
            self._link = None

    def _on_connected(self, ok: bool) -> None:
        self._connect_btn.setText("Bağlantıyı Kes" if ok else "Bağlan")
        self._mode_combo.setEnabled(not ok)
        serial = self._mode_combo.currentText() == "Seri Port"
        self._port_combo.setEnabled((not ok) and serial)
        self._baud_combo.setEnabled((not ok) and serial)
        name = self._link.name if self._link else "—"
        self.telemetry.set_link(name, ok)
        if not ok:
            self._armed_lbl.setText("● SAFE")
            self._armed_lbl.setStyleSheet("color:#2ecc71; font-weight:bold;")

    # ------------------------------------------------------------------
    # Veri alma / ayrıştırma
    # ------------------------------------------------------------------
    def _on_data(self, data: bytes) -> None:
        self._last_rx = time.time()
        self._rx_bytes += len(data)
        if self._hex_rx:
            self._hex_buf.extend(data)

        frames = self._parser.feed(data)
        if not frames and b"\xaa\x55" in data:
            # SYNC görüldü ama geçerli çerçeve çözülemedi -> olası uyuşmazlık
            if time.time() - self._last_bad_warn > 3.0:
                self._last_bad_warn = time.time()
                self._log("UYARI: ham veri geliyor ama geçerli çerçeve çözülemedi "
                          "(baudrate/protokol uyuşmazlığı olabilir). 'Ham RX' ile baytlara bakın.")

        for type_byte, payload in frames:
            try:
                self._dispatch(type_byte, payload)
            except Exception as exc:  # noqa: BLE001
                self._log(f"Ayrıştırma hatası (0x{type_byte:02x}): {exc}")

        # CSV satırları (gerçek peyk ASCII/CSV gönderiyorsa)
        for tm, g, s in self._csv_parser.feed(data):
            if not self._csv_seen:
                self._csv_seen = True
                self._log("CSV telemetri algılandı (ikili protokol yerine).")
            try:
                if tm is not None:
                    self._apply_telemetry(tm)
                if g is not None and (g.lat != 0.0 or g.lon != 0.0):
                    self._apply_gps(g)
                if s is not None:
                    self._apply_status(s)
            except Exception as exc:  # noqa: BLE001
                self._log(f"CSV ayrıştırma hatası: {exc}")
        self._update_counters()

    def _dispatch(self, type_byte: int, payload: bytes) -> None:
        if type_byte == packet.TYPE_TELEMETRY:
            self._apply_telemetry(packet.unpack_telemetry(payload))
        elif type_byte == packet.TYPE_GPS:
            self._apply_gps(packet.unpack_gps(payload))
        elif type_byte == packet.TYPE_STATUS:
            self._apply_status(packet.unpack_status(payload))
        elif type_byte == packet.TYPE_CAMERA:
            jpg = self._cam_assembler.feed(payload)
            if jpg:
                self._counters["cam"] += 1
                self.camera.show_jpeg(jpg)
        self._update_counters()

    def _apply_telemetry(self, tm: packet.TelemetryData) -> None:
        self._counters["tel"] += 1
        self.telemetry.update_telemetry(tm)
        self.globe.set_attitude(tm.roll, tm.pitch, tm.yaw)
        self.plot.add_sample({
            "bat_v": tm.battery_v, "bat_i": tm.battery_i,
            "temp_cpu": tm.temp_cpu, "temp_batt": tm.temp_batt,
            "altitude": tm.altitude,
            "roll": tm.roll, "pitch": tm.pitch, "yaw": tm.yaw,
            "rssi": tm.rssi,
        })

    def _apply_gps(self, g: packet.GpsData) -> None:
        self._counters["gps"] += 1
        self.telemetry.update_gps(g)
        self.map.set_gps(g.lat, g.lon)

    def _apply_status(self, s: packet.StatusData) -> None:
        self._counters["sts"] += 1
        self.telemetry.update_status(s)
        self._update_armed_indicator(s)

    def _update_armed_indicator(self, s: packet.StatusData) -> None:
        if s.state == packet.STATE_ARMED:
            self._armed_lbl.setText("● ARMED")
            self._armed_lbl.setStyleSheet("color:#e67e22; font-weight:bold;")
        elif s.state in (packet.STATE_FLIGHT, packet.STATE_DEPLOYED, packet.STATE_RECOVERY):
            self._armed_lbl.setText(f"● {packet.STATE_NAMES.get(s.state, s.state)}")
            self._armed_lbl.setStyleSheet("color:#3498db; font-weight:bold;")
        else:
            self._armed_lbl.setText("● SAFE")
            self._armed_lbl.setStyleSheet("color:#2ecc71; font-weight:bold;")

    def _update_counters(self) -> None:
        c = self._counters
        self._counters_lbl.setText(
            f"TEL: {c['tel']}  GPS: {c['gps']}  STS: {c['sts']}  "
            f"CAM: {c['cam']}  RX: {self._rx_bytes} B  TX: {c['tx']}"
        )

    # ------------------------------------------------------------------
    # Kamera kaynakları
    # ------------------------------------------------------------------
    def _on_camera_source_changed(self, text: str) -> None:
        self._stop_camera_sources()
        if text == "Webcam":
            self._webcam = WebcamSource(self._webcam_spin.value())
            self._webcam.frame_ready.connect(self.camera.show_qimage)
            self._webcam.error.connect(self._log)
            self._webcam.start()
            self._log(f"Webcam {self._webcam_spin.value()} başlatıldı.")
        elif text == "UDP":
            self._udp = UdpCameraSource(self._udp_spin.value())
            self._udp.frame_ready.connect(self.camera.show_qimage)
            self._udp.error.connect(self._log)
            self._udp.start()
            self._log(f"UDP kamera {self._udp_spin.value()} portunda dinleniyor.")
        else:
            self.camera.clear()
            self._log("Kamera kaynağı: Uydu Linki (telemetri paketlerinden).")

    def _stop_camera_sources(self) -> None:
        if self._webcam:
            self._webcam.stop()
            self._webcam = None
        if self._udp:
            self._udp.stop()
            self._udp = None

    # ------------------------------------------------------------------
    # Komut gönderme
    # ------------------------------------------------------------------
    def _send_command(self, cmd: int, payload: bytes) -> None:
        if not self._link or not self._link.is_open:
            self._log("Bağlantı yok — komut gönderilemedi.")
            return
        self._link.send_command(cmd, payload)
        self._counters["tx"] += 1
        name = packet.COMMAND_NAMES.get(cmd, hex(cmd))
        extra = payload.hex() if payload else ""
        self._log(f"TX -> {name} {extra}")
        self._update_counters()

    def _toggle_hex(self, on: bool) -> None:
        self._hex_rx = on
        self._hex_btn.setText("Ham RX: AÇIK" if on else "Ham RX: OFF")
        if on:
            self._hex_buf.clear()
            self._hex_timer.start()
            self._log("Ham RX izleme açıldı — gelen baytlar hex olarak loglanacak.")
        else:
            self._hex_timer.stop()
            self._log("Ham RX izleme kapatıldı.")

    def _flush_hex(self) -> None:
        if not self._hex_buf:
            return
        data = bytes(self._hex_buf)
        self._hex_buf.clear()
        shown = data[-96:] if len(data) > 96 else data
        note = f"  ... (toplam {len(data)} bayt)" if len(data) > 96 else ""
        self._log(f"RX hex: {shown.hex(' ')}{note}")

    def _log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop_camera_sources()
        if self._link:
            self._link.close()
        event.accept()



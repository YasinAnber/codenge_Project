import sys
import serial
import time
import re
import datetime
import serial.tools.list_ports
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QFrame,
                             QSpacerItem, QSizePolicy, QDialog, QComboBox,
                             QLineEdit, QSlider, QRadioButton, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPixmap, QPainterPath, QIcon  # EKLENDİ: QIcon eklendi

# ---------------- AYARLAR ----------------
DEFAULT_PORT = 'COM10'
DEFAULT_BAUD = 9600
SCALE_FACTOR = 18
# -----------------------------------------

# Stil Sabitleri
BG_COLOR = "#0b111a"
BORDER_COLOR = "#2a3441"
TEXT_WHITE = "#f5f5f5"
TEXT_BLUE = "#3b82f6"
TEXT_GRAY = "#94a3b8"
ALERT_RED = "#dc2626"
ALERT_BG = "rgba(220, 38, 38, 0.15)"
SUCCESS_GREEN = "#2ecc71"
SUCCESS_BG = "rgba(46, 204, 113, 0.15)"


class SerialWorker(QThread):
    data_ready = pyqtSignal(float, float, float, float, float, float)
    status_msg = pyqtSignal(str)
    log_msg = pyqtSignal(str, str)

    def __init__(self, port, baud_rate):
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.is_running = True
        self.ser = None
        self.last_status = "idle"

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=1)
            time.sleep(2)
            self.status_msg.emit(f"BAĞLANDI: {self.port} ({self.baud_rate} baud)")
            self.log_msg.emit("success", f"Seri port açıldı: {self.port}")

            while self.is_running:
                if self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            self.parse_data(line)
                    except Exception:
                        pass
                time.sleep(0.01)
        except serial.SerialException:
            self.status_msg.emit(f"HATA: {self.port} bulunamadı!")
            self.log_msg.emit("error", f"Bağlantı hatası: {self.port} bulunamadı!")

    def parse_data(self, line):
        try:
            match = re.search(r'Agirlik:\s*([-\d.]+).*?X_CG:\s*([-\d.]+).*?Y_CG:\s*([-\d.]+)', line)
            if match:
                weight = float(match.group(1))
                raw_x = float(match.group(2))
                raw_y = float(match.group(3))

                lc1, lc2, lc3 = 0.0, 0.0, 0.0
                m_lc1 = re.search(r'LC1:\s*([-\d.]+)', line)
                m_lc2 = re.search(r'LC2:\s*([-\d.]+)', line)
                m_lc3 = re.search(r'LC3:\s*([-\d.]+)', line)

                if m_lc1: lc1 = float(m_lc1.group(1))
                if m_lc2: lc2 = float(m_lc2.group(1))
                if m_lc3: lc3 = float(m_lc3.group(1))

                self.data_ready.emit(weight, raw_x, raw_y, lc1, lc2, lc3)

                if abs(raw_x) > 2.0 or abs(raw_y) > 2.0:
                    if self.last_status != "unbalanced":
                        self.log_msg.emit("warning", f"Sapma tespit edildi! (X:{raw_x:.1f}, Y:{raw_y:.1f})")
                        self.log_msg.emit("action", "Dengeleyici kütleler hedefe sürülüyor...")
                        self.last_status = "unbalanced"
                else:
                    if self.last_status != "balanced":
                        self.log_msg.emit("success", "Optimum denge noktasına ulaşıldı.")
                        self.last_status = "balanced"

        except Exception:
            pass

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()


# ---------------- SYSTEM STATE ----------------
class SystemStateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(450, 500)
        self.oldPos = self.pos()

        self.setStyleSheet("""
            QDialog {
                background-color: #121926; border: 1px solid #334155; border-radius: 12px;
            }
            QLabel { color: #cbd5e1; font-family: 'Segoe UI'; font-size: 13px; }

            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 6px; padding: 6px; font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #334155; color: white;
                border: 2px outset #64748b; 
            }
            QPushButton:pressed {
                border: 2px inset #1e293b;
            }

            QTextEdit {
                background-color: #000000; color: #10b981; font-family: 'Consolas', monospace; 
                font-size: 12px; border: 1px solid #334155; border-radius: 6px; padding: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("⚙ System State")
        title.setStyleSheet("font-size: 16px; color: #f8fafc; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #334155; border: none;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        lc_label = QLabel("Real-Time Sensor (Loadcell) Data")
        lc_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(lc_label)

        lc_layout = QHBoxLayout()
        self.lbl_lc1 = self.create_lc_panel("LC1 (Front)")
        self.lbl_lc2 = self.create_lc_panel("LC2 (Left)")
        self.lbl_lc3 = self.create_lc_panel("LC3 (Right)")
        lc_layout.addWidget(self.lbl_lc1)
        lc_layout.addWidget(self.lbl_lc2)
        lc_layout.addWidget(self.lbl_lc3)
        layout.addLayout(lc_layout)

        test_layout = QHBoxLayout()
        test_layout.addWidget(QPushButton("Ping Sensors"))
        test_layout.addWidget(QPushButton("Test Servo X"))
        test_layout.addWidget(QPushButton("Test Servo Y"))
        layout.addLayout(test_layout)

        log_label = QLabel("Live Event Console")
        log_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(log_label)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setHtml("<span style='color: #64748b;'>[System] Terminal initialized...</span><br>")
        layout.addWidget(self.console)

        btn_layout = QHBoxLayout()
        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedHeight(35)
        self.btn_close.setStyleSheet("""
            QPushButton { background: transparent; color: #cbd5e1; border: 1px solid #475569; border-radius: 6px; }
            QPushButton:hover { background: rgba(220, 38, 38, 0.2); border: 2px outset #ef4444; color: #ef4444; }
            QPushButton:pressed { border: 2px inset #991b1b; }
        """)
        self.btn_close.clicked.connect(self.hide)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def create_lc_panel(self, title):
        frame = QFrame()
        frame.setStyleSheet("background-color: #0f172a; border: 1px solid #334155; border-radius: 8px;")
        vbox = QVBoxLayout(frame)
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #64748b; font-size: 10px; border: none;")
        lbl_t.setAlignment(Qt.AlignCenter)
        lbl_val = QLabel("0.0 gr")
        lbl_val.setStyleSheet("color: #3b82f6; font-size: 14px; font-weight: bold; border: none;")
        lbl_val.setAlignment(Qt.AlignCenter)
        vbox.addWidget(lbl_t)
        vbox.addWidget(lbl_val)
        frame.val_label = lbl_val
        return frame

    def update_loadcells(self, lc1, lc2, lc3):
        self.lbl_lc1.val_label.setText(f"{lc1:.1f} gr")
        self.lbl_lc2.val_label.setText(f"{lc2:.1f} gr")
        self.lbl_lc3.val_label.setText(f"{lc3:.1f} gr")

        for lbl, val in [(self.lbl_lc1.val_label, lc1), (self.lbl_lc2.val_label, lc2), (self.lbl_lc3.val_label, lc3)]:
            if val <= -999:
                lbl.setStyleSheet("color: #ef4444; font-size: 14px; font-weight: bold; border: none;")
                lbl.setText("ERROR")
            else:
                lbl.setStyleSheet("color: #3b82f6; font-size: 14px; font-weight: bold; border: none;")

    def append_log(self, msg_type, msg):
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        color = "#10b981"
        if msg_type == "warning":
            color = "#f59e0b"
            msg = f"Uyarı: {msg}"
        elif msg_type == "action":
            color = "#3b82f6"
            msg = f"Eylem: {msg}"
        elif msg_type == "error":
            color = "#ef4444"
            msg = f"Hata: {msg}"
        elif msg_type == "success":
            color = "#2ecc71"
            msg = f"Başarılı: {msg}"

        html_msg = f"<span style='color: #64748b;'>{timestamp}</span> <span style='color: {color};'>{msg}</span>"
        self.console.append(html_msg)
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()


# ---------------- PROFESYONEL AVATAR İKONU (ROZET) ----------------
class AvatarBadge(QLabel):
    def __init__(self, initials, bg_color):
        super().__init__()
        self.setFixedSize(30, 30)
        self.initials = initials
        self.bg_color = bg_color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setBrush(QBrush(QColor(self.bg_color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())

        painter.setPen(QPen(QColor("#ffffff")))
        font = QFont("Segoe UI", 11, QFont.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignCenter, self.initials)


# ---------------- PROJECT TEAM POP-UP ----------------
class ProjectTeamDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(380, 420)
        self.oldPos = self.pos()

        self.setStyleSheet("""
            QDialog {
                background-color: #121926; border: 1px solid #334155; border-radius: 12px;
            }
            QLabel { color: #cbd5e1; font-family: 'Segoe UI'; font-size: 13px; }

            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 6px; padding: 6px; font-weight: bold;
            }
            QPushButton:hover { 
                background-color: #334155; color: white;
                border: 2px outset #64748b; 
            }
            QPushButton:pressed {
                border: 2px inset #1e293b;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Project Team")
        title.setStyleSheet("font-size: 16px; color: #f8fafc; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #334155; border: none;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        team_members = [
            ("YA", "#2563eb", "Yasin Anber - Computer Engineer"),
            ("Sİ", "#9333ea", "Sude İpekci - Computer Engineer"),
            ("SG", "#059669", "Selin Göç - Computer Engineer"),
            ("EM", "#ea580c", "Elif Sude Memiş - Software Engineer")
        ]

        for initials, color, name in team_members:
            badge = AvatarBadge(initials, color)
            layout.addWidget(self.create_team_row(badge, name))

        adv_title = QLabel("Project Advisor")
        adv_title.setStyleSheet("font-size: 12px; color: #94a3b8; margin-top: 10px; font-weight: bold;")
        layout.addWidget(adv_title)

        adv_badge = AvatarBadge("Hİ", "#b91c1c")
        layout.addWidget(self.create_team_row(adv_badge, "Prof. Dr. Hakkı Gökhan İlk"))

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedSize(120, 35)
        self.btn_close.setStyleSheet("""
            QPushButton { background: transparent; color: #cbd5e1; border: 1px solid #475569; border-radius: 6px; }
            QPushButton:hover { background: rgba(51, 65, 85, 0.5); border: 2px outset #64748b; color: white; }
            QPushButton:pressed { border: 2px inset #334155; }
        """)
        self.btn_close.clicked.connect(self.hide)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def create_team_row(self, badge_widget, text):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a; 
                border: 1px solid #334155; 
                border-radius: 6px; 
            }
        """)
        h_layout = QHBoxLayout(frame)
        h_layout.setContentsMargins(15, 8, 15, 8)
        h_layout.setSpacing(15)

        h_layout.addWidget(badge_widget)

        text_lbl = QLabel(text)
        text_lbl.setStyleSheet("color: #e2e8f0; font-size: 13px; border: none; background: transparent;")
        h_layout.addWidget(text_lbl, 1)

        return frame

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()


# ---------------- KALİBRASYON POP-UP ----------------
class CalibrationDialog(QDialog):
    def __init__(self, current_port, current_baud, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setFixedSize(380, 420)
        self.oldPos = self.pos()

        self.setStyleSheet("""
            QDialog {
                background-color: #121926; border: 1px solid #334155; border-radius: 12px;
            }
            QLabel { color: #cbd5e1; font-family: 'Segoe UI'; font-size: 13px; }

            QPushButton {
                background-color: #1e293b; color: #cbd5e1; border: 1px solid #334155;
                border-radius: 6px; padding: 6px;
            }
            QPushButton:hover { 
                background-color: #334155; color: white;
                border: 2px outset #64748b; 
            }
            QPushButton:pressed {
                border: 2px inset #1e293b;
            }

            QLineEdit, QComboBox {
                background-color: #0f172a; color: #60a5fa; border: 1px solid #334155;
                border-radius: 4px; padding: 4px; font-weight: bold;
            }
            QComboBox::drop-down { border: none; }
            QSlider::groove:horizontal { border: 1px solid #334155; height: 6px; background: #0f172a; border-radius: 3px; }
            QSlider::sub-page:horizontal { background: #3b82f6; border-radius: 3px; }
            QSlider::handle:horizontal { background: #cbd5e1; border: 1px solid #94a3b8; width: 14px; margin: -4px 0; border-radius: 7px; }
            QRadioButton { color: #cbd5e1; font-size: 13px; }
            QRadioButton::indicator { width: 12px; height: 12px; border-radius: 6px; border: 1px solid #3b82f6; }
            QRadioButton::indicator:checked { background-color: #3b82f6; border: 3px solid #0f172a; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Calibration Settings")
        title.setStyleSheet("font-size: 16px; color: #f8fafc;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #334155; border: none;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        port_layout = QHBoxLayout()
        lbl_port = QLabel("Port:")
        self.cb_port = QComboBox()

        ports = [port.device for port in serial.tools.list_ports.comports()]
        if current_port not in ports:
            ports.insert(0, current_port)
        self.cb_port.addItems(ports)
        self.cb_port.setCurrentText(current_port)

        lbl_baud = QLabel(" Baud:")
        self.cb_baud = QComboBox()
        self.cb_baud.addItems(['4800', '9600', '19200', '38400', '57600', '115200'])
        self.cb_baud.setCurrentText(str(current_baud))

        port_layout.addWidget(lbl_port)
        port_layout.addWidget(self.cb_port, 1)
        port_layout.addWidget(lbl_baud)
        port_layout.addWidget(self.cb_baud, 1)
        layout.addLayout(port_layout)

        btn_tare = QPushButton("Tare Scales (Reset Zero)")
        layout.addWidget(btn_tare)

        lbl_opt = QLabel("Set Optimum Center (0,0)")
        layout.addWidget(lbl_opt)

        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("X:"))
        le_x = QLineEdit("-0.5")
        le_x.setAlignment(Qt.AlignCenter)
        opt_layout.addWidget(le_x)

        opt_layout.addWidget(QLabel("Y:"))
        le_y = QLineEdit("0.0")
        le_y.setAlignment(Qt.AlignCenter)
        opt_layout.addWidget(le_y)

        le_z = QLineEdit("-3.0")
        le_z.setStyleSheet("color: #ef4444;")
        le_z.setAlignment(Qt.AlignCenter)
        opt_layout.addWidget(le_z)
        opt_layout.addWidget(QLabel("mm"))
        layout.addLayout(opt_layout)

        layout.addWidget(QLabel("Servo Speed"))
        slider = QSlider(Qt.Horizontal)
        slider.setValue(60)
        layout.addWidget(slider)

        units_layout = QHBoxLayout()
        units_layout.addWidget(QLabel("Units"))
        rb_gr = QRadioButton("(gr/kg)")
        rb_gr.setChecked(True)
        rb_mass = QRadioButton("Mass")
        units_layout.addWidget(rb_gr)
        units_layout.addWidget(rb_mass)
        units_layout.addStretch()
        layout.addLayout(units_layout)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setFixedSize(100, 35)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #1d4ed8);
                color: white; border: 1px solid #60a5fa; font-weight: bold; border-radius: 6px;
            }
            QPushButton:hover { background: #2563eb; border: 2px outset #93c5fd; }
            QPushButton:pressed { border: 2px inset #1d4ed8; }
        """)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedSize(100, 35)
        self.btn_cancel.setStyleSheet("""
            QPushButton { background: transparent; color: #cbd5e1; border: 1px solid #475569; border-radius: 6px; }
            QPushButton:hover { background: rgba(51, 65, 85, 0.5); border: 2px outset #64748b; color: white; }
            QPushButton:pressed { border: 2px inset #334155; }
        """)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.btn_apply.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def get_port_config(self):
        return self.cb_port.currentText(), int(self.cb_baud.currentText())

    def mousePressEvent(self, event):
        self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPos() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPos()


# ---------------- RADAR & TITLE FRAME ----------------
class TitleCardFrame(QFrame):
    def __init__(self):
        super().__init__()
        self.pixmap = QPixmap("helicopter.png")

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            path = QPainterPath()
            path.addRoundedRect(0, 0, self.width(), self.height(), 15, 15)
            painter.setClipPath(path)
            painter.setOpacity(0.07)

            scaled_pixmap = self.pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)


class RadarWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background-color: #0f172a; border: 1px solid {BORDER_COLOR}; border-radius: 12px;")
        self.helicopter_pixmap = QPixmap("chinook_top.png")
        self.dot_rel_x = 0.0
        self.dot_rel_y = 0.0
        self.dot_color = QColor(SUCCESS_GREEN)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        width = self.width()
        height = self.height()
        center = self.rect().center()

        if not self.helicopter_pixmap.isNull():
            painter.setOpacity(0.30) # helikopter opasitesi

            scaled_img = self.helicopter_pixmap.scaled(
                width, height,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            )

            painter.drawPixmap(0, 0, scaled_img)
            painter.setOpacity(1.45) # koordinat çizgileri

        pen = QPen(QColor("#1e293b"), 1)
        painter.setPen(pen)
        painter.drawLine(0, center.y(), width, center.y())
        painter.drawLine(center.x(), 0, center.x(), height)

        painter.drawEllipse(center, width // 6, height // 6)
        painter.drawEllipse(center, width // 4, height // 4)
        painter.drawEllipse(center, width // 3, height // 3)

        painter.setPen(QPen(QColor(TEXT_GRAY)))
        font = QFont("Arial", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(center.x() - 25, 20, "+Y (Front)")
        painter.drawText(center.x() - 25, height - 10, "-Y (Rear)")
        painter.drawText(10, center.y() + 5, "-X (Left)")
        painter.drawText(width - 65, center.y() + 5, "+X (Right)")

        new_x = center.x() + (self.dot_rel_x * SCALE_FACTOR)
        new_y = center.y() - (self.dot_rel_y * SCALE_FACTOR)

        painter.setBrush(QBrush(self.dot_color))
        painter.setPen(Qt.NoPen)
        r = 8
        painter.drawEllipse(int(new_x - r), int(new_y - r), r * 2, r * 2)

        painter.setBrush(QBrush(QColor(TEXT_BLUE)))
        painter.drawEllipse(center.x() - 4, center.y() - 4, 8, 8)


# ---------------- ANA UYGULAMA ----------------
class CodengeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("codenGe Project v1.0 - Live CG Analysis")

        # --- EKLENEN SATIR: Pencere İkonunu Ayarla ---
        self.setWindowIcon(QIcon("icon.ico"))

        self.setMinimumSize(1200, 700)
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        self.current_port = DEFAULT_PORT
        self.current_baud = DEFAULT_BAUD

        self.offset_x = 0.0
        self.offset_y = 0.0
        self.raw_x = 0.0
        self.raw_y = 0.0

        self.state_dialog = SystemStateDialog(self)
        self.team_dialog = ProjectTeamDialog(self)

        self.serial_thread = None

        self.init_ui()

        self.update_status("Hazır. Başlamak için 'START SYSTEM'e basın.")
        self.state_dialog.append_log("action", "Sistem başlatılmaya hazır bekliyor.")

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(20)

        self.landing_layout = QVBoxLayout()
        self.setup_landing_page()
        self.main_layout.addLayout(self.landing_layout, 5)

        self.dashboard_layout = QVBoxLayout()
        self.setup_dashboard()
        self.main_layout.addLayout(self.dashboard_layout, 6)

    def soft_restart_system(self):
        self.update_status("Sistem ve Bağlantılar Sıfırlanıyor...")
        self.state_dialog.append_log("warning", "Sistem yeniden başlatılıyor (Arayüz açık kalarak)...")

        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread.wait()

        self.offset_x = 0.0
        self.offset_y = 0.0
        self.raw_x = 0.0
        self.raw_y = 0.0

        self.lbl_weight_val.setText("0 gr")
        self.lbl_pos_val.setText("X: 0.00 mm\nY: 0.00 mm")
        self.lbl_dev_val.setText("ΔX: 0.00\nΔY: 0.00")

        self.radar_area.dot_rel_x = 0.0
        self.radar_area.dot_rel_y = 0.0
        self.radar_area.update()

        self.serial_thread = SerialWorker(self.current_port, self.current_baud)
        self.serial_thread.data_ready.connect(self.update_ui_data)
        self.serial_thread.status_msg.connect(self.update_status)
        self.serial_thread.log_msg.connect(self.state_dialog.append_log)
        self.serial_thread.start()

        self.state_dialog.append_log("success", "Sistem arka planda başarıyla yeniden başlatıldı ve port temizlendi!")

    def start_system(self):
        if not self.serial_thread or not self.serial_thread.isRunning():
            self.update_status("Sistem Başlatılıyor...")
            self.state_dialog.append_log("action", "Kullanıcı veri alımını başlattı.")

            self.serial_thread = SerialWorker(self.current_port, self.current_baud)
            self.serial_thread.data_ready.connect(self.update_ui_data)
            self.serial_thread.status_msg.connect(self.update_status)
            self.serial_thread.log_msg.connect(self.state_dialog.append_log)
            self.serial_thread.start()
        else:
            self.state_dialog.append_log("warning", "Sistem zaten çalışıyor.")

    def setup_landing_page(self):
        top_vbox = QVBoxLayout()
        top_vbox.setSpacing(2)

        header = QLabel("codenGe")
        header.setStyleSheet(f"color: {TEXT_WHITE}; font-size: 22px; font-weight: 900; letter-spacing: 1px;")
        top_vbox.addWidget(header, alignment=Qt.AlignLeft)

        tusas_lbl = QLabel("TUSAŞ LIFT-UP PROJECT")
        tusas_lbl.setStyleSheet(f"color: {TEXT_BLUE}; font-size: 14px; font-weight: bold; letter-spacing: 2px;")
        top_vbox.addWidget(tusas_lbl, alignment=Qt.AlignLeft)

        self.landing_layout.addLayout(top_vbox)
        self.landing_layout.addStretch()

        title_card = TitleCardFrame()
        title_card.setStyleSheet(
            f"background-color: rgba(30, 41, 59, 0.4); border: 1px solid {BORDER_COLOR}; border-radius: 15px; padding: 40px;")
        title_vbox = QVBoxLayout(title_card)
        main_title = QLabel("AIRCRAFT WEIGHT CENTER DETECTION\nAND BALANCING SYSTEM")
        main_title.setAlignment(Qt.AlignCenter)
        main_title.setStyleSheet(
            "color: white; font-size: 24px; font-weight: bold; border: none; background: transparent;")
        title_vbox.addWidget(main_title)
        self.landing_layout.addWidget(title_card)
        self.landing_layout.addSpacerItem(QSpacerItem(20, 40))

        start_btn = QPushButton(" START SYSTEM ")
        start_btn.setFixedSize(320, 80)
        start_btn.setStyleSheet("""
            QPushButton { 
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e3a8a, stop:1 #0f172a);
                color: white; font-size: 16px; font-weight: bold; border: 2px solid #3b82f6; border-radius: 12px; 
            }
            QPushButton:hover { background: #1e40af; border: 3px outset #60a5fa; }
            QPushButton:pressed { border: 3px inset #0f172a; }
        """)
        start_btn.clicked.connect(self.start_system)
        self.landing_layout.addWidget(start_btn, alignment=Qt.AlignCenter)

        self.landing_layout.addSpacerItem(QSpacerItem(20, 8))

        btn_rerun = QPushButton("  RESET SYSTEM ")
        btn_rerun.setFixedSize(220, 40)
        btn_style_rerun = """
            QPushButton { 
                background-color: #7f1d1d; color: #f8fafc; border: 1px solid #b91c1c; border-radius: 8px; font-weight: bold; font-size: 12px;
            }
            QPushButton:hover { background-color: #991b1b; color: white; border: 2px outset #dc2626; }
            QPushButton:pressed { border: 2px inset #450a0a; }
        """
        btn_rerun.setStyleSheet(btn_style_rerun)
        btn_rerun.clicked.connect(self.soft_restart_system)
        self.landing_layout.addWidget(btn_rerun, alignment=Qt.AlignCenter)

        self.landing_layout.addStretch()

        bottom_btns = QHBoxLayout()

        btn_style = """
            QPushButton { 
                background-color: #1e293b; color: #94a3b8; border: 1px solid #2a3441; border-radius: 8px; padding: 10px; 
            }
            QPushButton:hover { background-color: #334155; color: white; border: 2px outset #60a5fa; }
            QPushButton:pressed { border: 2px inset #1e293b; }
        """

        b1 = QPushButton("⚙ Calibration Settings")
        b1.setStyleSheet(btn_style)
        b1.clicked.connect(self.open_calibration_dialog)
        bottom_btns.addWidget(b1)

        b2 = QPushButton("⚙ System State")
        b2.setStyleSheet(btn_style)
        b2.clicked.connect(self.open_state_dialog)
        bottom_btns.addWidget(b2)

        b3 = QPushButton("ℹ Project Team")
        b3.setStyleSheet(btn_style)
        b3.clicked.connect(self.open_team_dialog)
        bottom_btns.addWidget(b3)

        self.landing_layout.addLayout(bottom_btns)

        self.landing_layout.addSpacerItem(QSpacerItem(20, 25, QSizePolicy.Minimum, QSizePolicy.Fixed))

        dev_label = QLabel("Developed by Yasin Anber")
        dev_label.setStyleSheet("color: #475569; font-size: 11px; font-style: italic; font-weight: bold;")
        dev_label.setAlignment(Qt.AlignCenter)
        self.landing_layout.addWidget(dev_label)

    def setup_dashboard(self):
        self.lbl_status = QLabel("Durum: Bağlantı aranıyor...")
        self.lbl_status.setStyleSheet(f"color: {TEXT_GRAY}; font-size: 13px; font-weight: bold;")
        self.dashboard_layout.addWidget(self.lbl_status, alignment=Qt.AlignLeft)

        panel_header = QFrame()
        panel_header.setStyleSheet(f"background-color: #1e293b; border: 1px solid {BORDER_COLOR}; border-radius: 10px;")
        panel_header.setFixedHeight(50)
        ph_layout = QVBoxLayout(panel_header)
        title = QLabel("Aircraft Weight Center Balancing Sys. Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #e2e8f0; font-size: 16px; font-weight: bold; border: none;")
        ph_layout.addWidget(title)
        self.dashboard_layout.addWidget(panel_header)

        self.radar_area = RadarWidget()
        self.dashboard_layout.addWidget(self.radar_area, 5)

        data_hbox = QHBoxLayout()
        data_hbox.setSpacing(10)

        self.lbl_weight_val = QLabel("0 gr")
        self.lbl_pos_val = QLabel("X: 0.00 mm\nY: 0.00 mm")
        self.lbl_dev_val = QLabel("ΔX: 0.00\nΔY: 0.00")

        self.create_data_tile(data_hbox, "TOTAL WEIGHT", self.lbl_weight_val, TEXT_BLUE)
        self.create_data_tile(data_hbox, "CURRENT POSITION", self.lbl_pos_val, TEXT_WHITE)
        self.create_data_tile(data_hbox, "DEVIATION", self.lbl_dev_val, TEXT_WHITE)
        self.dashboard_layout.addLayout(data_hbox)

        btn_tare = QPushButton("📍 Merkezi Sıfırla (Datum)")
        btn_tare.setFixedHeight(40)
        btn_tare.setStyleSheet("""
            QPushButton { 
                background-color: #0f766e; color: white; font-weight: bold; font-size: 14px;
                border: 1px solid #14b8a6; border-radius: 8px; 
            }
            QPushButton:hover { background-color: #0d9488; border: 2px outset #2dd4bf;}
            QPushButton:pressed { border: 2px inset #0f766e; }
        """)
        btn_tare.clicked.connect(self.zero_center)
        self.dashboard_layout.addWidget(btn_tare)

        self.warn_frame = QFrame()
        self.warn_frame.setStyleSheet(
            f"background-color: {ALERT_BG}; border: 1px solid {ALERT_RED}; border-radius: 8px;")
        self.warn_vbox = QVBoxLayout(self.warn_frame)
        self.w_t1 = QLabel("⚠ WEIGHT CENTER NOT AT OPTIMUM POINT!")
        self.w_t1.setStyleSheet(
            f"color: {ALERT_RED}; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        self.w_t1.setAlignment(Qt.AlignCenter)
        self.w_t2 = QLabel("Balancing system active: Mass is being moved...")
        self.w_t2.setStyleSheet("color: #fca5a5; font-size: 11px; border: none; background: transparent;")
        self.w_t2.setAlignment(Qt.AlignCenter)
        self.warn_vbox.addWidget(self.w_t1)
        self.warn_vbox.addWidget(self.w_t2)
        self.dashboard_layout.addWidget(self.warn_frame)

    def create_data_tile(self, layout, title_text, label_obj, color):
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #1e293b; border: 1px solid {BORDER_COLOR}; border-radius: 12px;")
        vbox = QVBoxLayout(frame)
        lbl_title = QLabel(title_text)
        lbl_title.setStyleSheet(
            f"color: {TEXT_GRAY}; font-size: 11px; border: none; border-bottom: 1px solid #2a3441; padding-bottom: 5px;")
        lbl_title.setAlignment(Qt.AlignCenter)
        label_obj.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold; border: none;")
        label_obj.setAlignment(Qt.AlignCenter)
        vbox.addWidget(lbl_title)
        vbox.addWidget(label_obj)
        layout.addWidget(frame)

    def zero_center(self):
        self.offset_x = self.raw_x
        self.offset_y = self.raw_y
        self.update_status(f"Datum Sıfırlandı! Yeni referans: X={self.offset_x:.2f}, Y={self.offset_y:.2f}")
        self.state_dialog.append_log("action",
                                     f"Kullanıcı datum noktasını sıfırladı. (Ofset X: {self.offset_x}, Y: {self.offset_y})")

    def open_calibration_dialog(self):
        dialog = CalibrationDialog(self.current_port, self.current_baud, self)
        if dialog.exec_():
            new_port, new_baud = dialog.get_port_config()
            if new_port != self.current_port or new_baud != self.current_baud:
                self.current_port = new_port
                self.current_baud = new_baud
                if self.serial_thread and self.serial_thread.isRunning():
                    self.serial_thread.stop()
                    self.serial_thread.wait()
                    self.update_status(f"Port güncelleniyor: {self.current_port}...")

                    self.serial_thread = SerialWorker(self.current_port, self.current_baud)
                    self.serial_thread.data_ready.connect(self.update_ui_data)
                    self.serial_thread.status_msg.connect(self.update_status)
                    self.serial_thread.log_msg.connect(self.state_dialog.append_log)
                    self.serial_thread.start()

    def open_state_dialog(self):
        self.state_dialog.show()
        self.state_dialog.raise_()

    def open_team_dialog(self):
        self.team_dialog.show()
        self.team_dialog.raise_()

    def update_status(self, msg):
        self.lbl_status.setText(f"Durum: {msg}")

    def update_ui_data(self, weight, x, y, lc1, lc2, lc3):
        self.raw_x = x
        self.raw_y = y

        rel_x = x - self.offset_x
        rel_y = y - self.offset_y

        self.lbl_weight_val.setText(f"{int(weight)} gr")
        self.lbl_pos_val.setText(f"X: {rel_x:.2f} mm\nY: {rel_y:.2f} mm")
        self.lbl_dev_val.setText(f"ΔX: {abs(rel_x):.2f}\nΔY: {abs(rel_y):.2f}")

        self.radar_area.dot_rel_x = rel_x
        self.radar_area.dot_rel_y = rel_y

        self.state_dialog.update_loadcells(lc1, lc2, lc3)

        if abs(rel_x) > 2.0 or abs(rel_y) > 2.0:
            self.radar_area.dot_color = QColor(ALERT_RED)
            self.warn_frame.setStyleSheet(
                f"background-color: {ALERT_BG}; border: 1px solid {ALERT_RED}; border-radius: 8px;")
            self.w_t1.setText("⚠ WEIGHT CENTER NOT AT OPTIMUM POINT!")
            self.w_t1.setStyleSheet(f"color: {ALERT_RED}; font-size: 13px; font-weight: bold; border: none;")
            self.w_t2.setText("Balancing system active! Initiating correction...")
            self.w_t2.setStyleSheet("color: #fca5a5; font-size: 11px; border: none;")
        else:
            self.radar_area.dot_color = QColor(SUCCESS_GREEN)
            self.warn_frame.setStyleSheet(
                f"background-color: {SUCCESS_BG}; border: 1px solid {SUCCESS_GREEN}; border-radius: 8px;")
            self.w_t1.setText(" SYSTEM BALANCED")
            self.w_t1.setStyleSheet(f"color: {SUCCESS_GREEN}; font-size: 13px; font-weight: bold; border: none;")
            self.w_t2.setText("Center of Gravity is at optimum position.")
            self.w_t2.setStyleSheet("color: #86efac; font-size: 11px; border: none;")

        self.radar_area.update()

    def closeEvent(self, event):
        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_thread.stop()
            self.serial_thread.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = CodengeApp()
    window.show()
    sys.exit(app.exec_())

    #end
import sys
import time
import random
import json
import os
from threading import Thread, Event
from pynput.mouse import Controller, Listener, Button

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QGraphicsBlurEffect, QTextEdit, QDialog,
    QSpinBox, QFormLayout, QDialogButtonBox, QMessageBox
)
from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QObject

CONFIG_PATH = "config.json"
BG_COLOR = "#121212"
FG_COLOR = "#E0E0E0"
ACCENT_COLOR = "#1DB954"
BUTTON_BG = "rgba(0,0,0,0.3)"
BUTTON_HOVER_BG = "#3DB961"
STATUS_RUNNING_COLOR = "#1DB954"
STATUS_STOPPED_COLOR = "#FFA500"
WARNING_COLOR = "#FF5555"


class WorkerSignals(QObject):
    log = pyqtSignal(str)
    status = pyqtSignal(str, str)


class AutoClickerWorker(Thread):
    def __init__(self, signals, target_cps, min_cps):
        super().__init__()
        self.signals = signals
        self.target_cps = target_cps
        self.min_cps = min_cps
        self.running = Event()
        self.running.set()
        self.mouse = Controller()
        self.click_times = []
        self.is_sending_clicks = False
        self.listener = None

    def log(self, text):
        self.signals.log.emit(text)

    def update_status(self, text, color=FG_COLOR):
        self.signals.status.emit(text, color)

    def on_click(self, x, y, button, pressed):
        if pressed and button == Button.left and not self.is_sending_clicks:
            self.click_times.append(time.time())
            self.log(f"Click at {self.click_times[-1]:.3f} seconds\n")

    def get_output_cps(self, real_cps):
        if real_cps > self.min_cps + 1:
            return self.target_cps
        elif real_cps > self.min_cps:
            return real_cps
        else:
            return 0

    def click_n_times(self, n):
        self.is_sending_clicks = True
        for _ in range(int(n)):
            if not self.running.is_set():
                break
            self.mouse.press(Button.left)
            press_time = random.uniform(0.015, 0.03)
            time.sleep(press_time)
            self.mouse.release(Button.left)

            base_interval = 1 / self.target_cps
            interval = base_interval + random.uniform(-base_interval * 0.15, base_interval * 0.15)
            time.sleep(max(0, interval - press_time))
        self.is_sending_clicks = False

    def run(self):
        self.log(f"AutoClicker started with Target CPS={self.target_cps}, Min CPS={self.min_cps}\n")
        self.listener = Listener(on_click=self.on_click)
        self.listener.start()

        while self.running.is_set():
            now = time.time()
            one_sec_ago = now - 1
            self.click_times = [t for t in self.click_times if t > one_sec_ago]
            real_cps = len(self.click_times)
            output_cps = self.get_output_cps(real_cps)

            self.update_status(f"Status: Running - Real CPS: {real_cps} - Output CPS: {output_cps}", STATUS_RUNNING_COLOR)

            if output_cps > 0:
                self.click_n_times(output_cps)
            else:
                time.sleep(0.1)

        self.listener.stop()
        self.update_status("Clicker stopped. You can edit config or restart.", STATUS_STOPPED_COLOR)
        self.log("AutoClicker stopped.\n")


class ConfigDialog(QDialog):
    def __init__(self, parent, target_cps, min_cps):
        super().__init__(parent)
        self.setWindowTitle("Edit Config")
        self.setFixedSize(300, 120)
        self.setStyleSheet(f"background-color: {BG_COLOR}; color: {FG_COLOR};")

        layout = QFormLayout(self)
        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 50)
        self.target_spin.setValue(target_cps)
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, target_cps)
        self.min_spin.setValue(min_cps)

        self.target_spin.valueChanged.connect(self.update_min_max)

        layout.addRow("Target CPS:", self.target_spin)
        layout.addRow("Min CPS:", self.min_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def update_min_max(self, val):
        self.min_spin.setMaximum(val)

    def get_values(self):
        return self.target_spin.value(), self.min_spin.value()


class AutoClickerGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Clicker v1.0")
        self.setFixedSize(400, 400)
        self.setWindowIcon(QIcon(self.resource_path("icon.ico")))
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        bg = QLabel(self)
        pixmap = QPixmap(self.resource_path("bg.jpg")).scaled(400, 400, Qt.KeepAspectRatioByExpanding)
        bg.setPixmap(pixmap)
        bg.setGeometry(0, 0, 400, 400)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(20)
        bg.setGraphicsEffect(blur)

        container = QWidget(self)
        container.setGeometry(0, 0, 400, 400)
        container.setStyleSheet("background-color: transparent;")

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        header = QLabel("Auto Clicker v1.0")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"color: {FG_COLOR};")
        header.setFont(QFont("Segoe UI", 16, QFont.Bold))
        main_layout.addWidget(header)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.start_btn = self.make_button("Start Clicker")
        self.edit_btn = self.make_button("Edit Config")
        self.support_btn = self.make_button("Support")

        for btn in (self.start_btn, self.edit_btn, self.support_btn):
            btn.setFixedSize(120, 30)

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.support_btn)
        main_layout.addLayout(btn_layout)

        self.status_label = QLabel("Status: Waiting...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color: {FG_COLOR};")
        self.status_label.setFont(QFont("Segoe UI", 11))
        main_layout.addWidget(self.status_label)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 80);
                color: #E0E0E0;
                border: none;
                border-radius: 6px;
                font-family: Consolas;
                font-size: 10pt;
            }
        """)
        self.log_box.setFrameStyle(0)
        self.log_box.setMinimumHeight(190)
        main_layout.addWidget(self.log_box)

        self.signals = WorkerSignals()
        self.signals.log.connect(self.append_log)
        self.signals.status.connect(self.update_status)

        self.target_cps = 12
        self.min_cps = 3

        self.load_config()
        self.worker = None

        self.start_btn.clicked.connect(self.toggle_clicker)
        self.edit_btn.clicked.connect(self.edit_config)
        self.support_btn.clicked.connect(self.open_support_link)

    def resource_path(self, relative_path):
        """ Get absolute path to resource (for PyInstaller) """
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def make_button(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {BUTTON_BG};
                color: {FG_COLOR};
                border: none;
                border-radius: 6px;
                font-size: 10pt;
                font-family: Segoe UI;
            }}
            QPushButton:hover {{
                background-color: {BUTTON_HOVER_BG};
                color: #000000;
            }}
        """)
        btn.setAttribute(Qt.WA_TranslucentBackground)
        return btn

    def append_log(self, text):
        self.log_box.moveCursor(self.log_box.textCursor().End)
        self.log_box.insertPlainText(text)
        self.log_box.moveCursor(self.log_box.textCursor().End)

    def update_status(self, text, color=FG_COLOR):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def load_config(self):
        if not os.path.exists(CONFIG_PATH):
            self.append_log("config.json not found, using defaults.\n")
            return
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
                self.target_cps = config.get("target_cps", 12)
                self.min_cps = config.get("min_cps", 3)
            self.append_log(f"Loaded config.json: target_cps={self.target_cps}, min_cps={self.min_cps}\n")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load config.json:\n{e}")

    def save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump({"target_cps": self.target_cps, "min_cps": self.min_cps}, f)
            self.append_log(f"Saved config.json: target_cps={self.target_cps}, min_cps={self.min_cps}\n")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save config.json:\n{e}")

    def toggle_clicker(self):
        if self.worker and self.worker.running.is_set():
            self.worker.running.clear()
            self.worker.join()
            self.worker = None
            self.start_btn.setText("Start Clicker")
        else:
            self.worker = AutoClickerWorker(self.signals, self.target_cps, self.min_cps)
            self.worker.start()
            self.start_btn.setText("Stop Clicker")

    def edit_config(self):
        if self.worker and self.worker.running.is_set():
            QMessageBox.information(self, "Info", "Stop the clicker before editing the config.")
            return

        dialog = ConfigDialog(self, self.target_cps, self.min_cps)
        if dialog.exec_() == QDialog.Accepted:
            self.target_cps, self.min_cps = dialog.get_values()
            self.save_config()

    def open_support_link(self):
        import webbrowser
        webbrowser.open("https://youtube.com/@yashh699")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = AutoClickerGUI()
    window.show()
    sys.exit(app.exec_())

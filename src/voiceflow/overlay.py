"""Плавающее окно индикатора записи."""

import time

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QFont


def format_recording_time(elapsed_seconds: float) -> str:
    """Форматировать длительность записи как MM:SS."""
    total_seconds = max(0, int(elapsed_seconds))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class RecordingOverlay(QWidget):
    """Компактное окно поверх всех окон с индикатором уровня звука."""

    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(250, 155)

        screen = self.screen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2 - 100,
        )

        self.audio_level = 0.0
        self._recording_started_at = None
        self._bars = 10
        self._bar_values = [0.0] * self._bars

        self._setup_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.start(40)

        self.hide()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(10)

        self.title = QLabel("🎤 Идёт запись...")
        self.title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.title.setStyleSheet("color: #ffffff;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.time_label.setStyleSheet("color: #7ee787;")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)

        bars_container = QWidget()
        bars_layout = QHBoxLayout(bars_container)
        bars_layout.setSpacing(3)
        bars_layout.setContentsMargins(0, 0, 0, 0)

        self._bar_widgets = []
        for _ in range(self._bars):
            bar = QLabel()
            bar.setFixedSize(14, 4)
            bar.setStyleSheet("background-color: #444; border-radius: 2px;")
            bars_layout.addWidget(bar)
            self._bar_widgets.append(bar)

        layout.addWidget(bars_container, alignment=Qt.AlignmentFlag.AlignCenter)

        hint = QLabel("Ctrl+Space — остановить и вставить")
        hint.setFont(QFont("Segoe UI", 9))
        hint.setStyleSheet("color: #888;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def set_audio_level(self, level: float):
        """Установить текущий уровень звука (0.0 - 1.0)."""
        self.audio_level = max(0.0, min(1.0, level))

    def _update_animation(self):
        """Обновить анимацию полосок."""
        if self._recording_started_at is not None:
            elapsed = time.monotonic() - self._recording_started_at
            self.time_label.setText(format_recording_time(elapsed))

        self._bar_values.pop(0)
        self._bar_values.append(self.audio_level)

        for i, (bar, val) in enumerate(zip(self._bar_widgets, self._bar_values)):
            if val < 0.3:
                color = f"rgb({int(80 + val * 500)}, 220, 80)"
            elif val < 0.7:
                color = f"rgb(220, {int(220 - (val - 0.3) * 350)}, 80)"
            else:
                color = f"rgb(255, {int(80 - (val - 0.7) * 200)}, 80)"

            height = int(4 + val * 36)
            bar.setFixedSize(14, max(4, height))
            bar.setStyleSheet(
                f"background-color: {color}; border-radius: 2px;"
            )

    def paintEvent(self, event):
        """Отрисовка фона с закруглёнными углами."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(25, 25, 30, 245))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 20, 20)

    def showEvent(self, event):
        """При показе сбрасываем состояние."""
        super().showEvent(event)
        self.audio_level = 0.0
        self._bar_values = [0.0] * self._bars
        self._recording_started_at = time.monotonic()
        self.time_label.setText("00:00")

    def hideEvent(self, event):
        """Остановить таймер при скрытии индикатора."""
        self._recording_started_at = None
        super().hideEvent(event)

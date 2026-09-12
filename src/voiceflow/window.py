"""Main RechType window for transcribing existing media files."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from voiceflow.media import MEDIA_FILE_FILTER


class TranscriptionWindow(QWidget):
    """Small desktop window for choosing a media file and reading its text."""

    transcription_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._selected_path: Path | None = None
        self._busy = False
        self.setWindowTitle("RechType — транскрибация файлов")
        self.setMinimumSize(720, 520)
        self.resize(820, 620)
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Транскрибация аудио и видео")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title)

        description = QLabel(
            "Выберите или перетащите сюда локальный файл. Аудиодорожка и текст "
            "обрабатываются только на этом компьютере."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("Файл ещё не выбран")
        file_row.addWidget(self.path_edit, 1)

        self.choose_button = QPushButton("Выбрать файл…")
        self.choose_button.clicked.connect(self._choose_file)
        file_row.addWidget(self.choose_button)
        layout.addLayout(file_row)

        self.transcribe_button = QPushButton("Транскрибировать")
        self.transcribe_button.setEnabled(False)
        self.transcribe_button.setMinimumHeight(38)
        self.transcribe_button.clicked.connect(self._request_transcription)
        layout.addWidget(self.transcribe_button)

        self.status_label = QLabel("Готово к работе")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)

        result_label = QLabel("Результат")
        result_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(result_label)

        self.result_edit = QPlainTextEdit()
        self.result_edit.setPlaceholderText("Здесь появится распознанный текст")
        layout.addWidget(self.result_edit, 1)

        result_buttons = QHBoxLayout()
        result_buttons.addStretch(1)
        self.copy_button = QPushButton("Копировать")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_result)
        result_buttons.addWidget(self.copy_button)
        self.save_button = QPushButton("Сохранить как…")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self._save_result)
        result_buttons.addWidget(self.save_button)
        layout.addLayout(result_buttons)

        hint = QLabel("Диктовка по Ctrl+Space продолжает работать в фоне через значок в трее.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #777;")
        layout.addWidget(hint)

    def _choose_file(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Выберите аудио или видео",
            "",
            MEDIA_FILE_FILTER,
        )
        if path:
            self.select_file(path)

    def select_file(self, path: str | Path) -> None:
        if self._busy:
            return
        selected = Path(path)
        self._selected_path = selected
        self.path_edit.setText(str(selected))
        self.path_edit.setToolTip(str(selected))
        self.result_edit.clear()
        self.copy_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.transcribe_button.setEnabled(selected.is_file() and not self._busy)
        self.status_label.setText("Файл выбран. Нажмите «Транскрибировать».")

    def _request_transcription(self) -> None:
        if self._busy or self._selected_path is None:
            return
        if not self._selected_path.is_file():
            self.show_error("Выбранный файл больше не существует.")
            return
        self.transcription_requested.emit(str(self._selected_path))

    def set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = busy
        self.choose_button.setEnabled(not busy)
        self.transcribe_button.setEnabled(
            not busy
            and self._selected_path is not None
            and self._selected_path.is_file()
        )
        self.progress.setVisible(busy)
        if message:
            self.status_label.setText(message)
        if busy:
            self.copy_button.setEnabled(False)
            self.save_button.setEnabled(False)

    def set_result(self, text: str, engine_name: str) -> None:
        clean_text = text.strip()
        self.set_busy(False)
        self.result_edit.setPlainText(clean_text)
        if clean_text:
            self.status_label.setText(f"Готово. Движок: {engine_name}")
            self.copy_button.setEnabled(True)
            self.save_button.setEnabled(True)
        else:
            self.status_label.setText("Готово, но речь в файле не обнаружена.")

    def show_error(self, message: str) -> None:
        self.set_busy(False, f"Ошибка: {message}")
        QMessageBox.warning(self, "RechType — ошибка", message)

    def _copy_result(self) -> None:
        text = self.result_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText("Текст скопирован в буфер обмена.")

    def _save_result(self) -> None:
        text = self.result_edit.toPlainText()
        if not text:
            return
        suggested: str | Path = "transcription.txt"
        if self._selected_path:
            suggested = self._selected_path.with_name(
                f"{self._selected_path.stem}-transcription.txt"
            )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Сохранить транскрипцию",
            str(suggested),
            "Текстовые файлы (*.txt);;Все файлы (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(text + "\n", encoding="utf-8")
        except OSError as error:
            self.show_error(f"Не удалось сохранить файл:\n{error}")
            return
        self.status_label.setText(f"Текст сохранён: {path}")

    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self._busy:
            event.ignore()
            return
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self._busy:
            event.ignore()
            return
        local_paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if local_paths:
            self.select_file(local_paths[0])
            event.acceptProposedAction()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        event.ignore()
        self.hide()

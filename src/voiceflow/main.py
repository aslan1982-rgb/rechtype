"""RechType — основной модуль приложения.

Горячая клавиша (по умолчанию Ctrl+Space):
  - Первое нажатие начинает запись
  - Второе нажатие останавливает запись и вставляет распознанный текст
"""

import gc
import shutil
import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog
)
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QUrl
from PyQt6.QtGui import QIcon, QAction, QDesktopServices
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from voiceflow import __version__
from voiceflow.config import load_config, save_config
from voiceflow.audio import AudioRecorder
from voiceflow.recognizer import (
    DEFAULT_FILE_MODEL_ID,
    FILE_MODEL_SPECS,
    create_file_recognizer,
    create_recognizer,
)
from voiceflow.history import TranscriptionHistory
from voiceflow.overlay import RecordingOverlay
from voiceflow.hotkey import GlobalHotkeyListener
from voiceflow.media import media_to_wav_bytes
from voiceflow.paste import paste_text
from voiceflow.paste_clipboard import paste_text_clipboard
from voiceflow.window import TranscriptionWindow


SINGLE_INSTANCE_NAME = "RechType-Desktop-v1"
DOWNLOAD_DISK_MARGIN_BYTES = 512 * 1024 * 1024


def _file_model_download_fits(primary, download_bytes: int) -> bool:
    """Account for an incomplete checkpoint that the loader will replace."""
    disk_probe = Path(primary.model_dir)
    while not disk_probe.exists() and disk_probe != disk_probe.parent:
        disk_probe = disk_probe.parent
    try:
        free_bytes = shutil.disk_usage(disk_probe).free
    except OSError:
        # Let the loader surface a concrete error if capacity cannot be read.
        return True

    reclaimable_bytes = 0
    try:
        checkpoint = Path(primary.checkpoint_path)
        if checkpoint.is_file():
            reclaimable_bytes = checkpoint.stat().st_size
    except (OSError, TypeError):
        pass
    return (
        free_bytes + reclaimable_bytes
        >= int(download_bytes) + DOWNLOAD_DISK_MARGIN_BYTES
    )


class RecognitionWorker(QThread):
    """Фоновый поток для распознавания речи."""

    text_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, wav_bytes, recognizer):
        super().__init__()
        self.wav_bytes = wav_bytes
        self.recognizer = recognizer

    def run(self):
        try:
            text = self.recognizer.recognize(self.wav_bytes)
            self.text_ready.emit(text)
        except Exception as e:
            self.error_occurred.emit(str(e))


class FileRecognitionWorker(QThread):
    """Decode a local audio/video file and recognize it off the GUI thread."""

    text_ready = pyqtSignal(str, str, object)
    error_occurred = pyqtSignal(str)

    def __init__(self, media_path: str, recognizer):
        super().__init__()
        self.media_path = media_path
        self.recognizer = recognizer

    def run(self):
        try:
            wav_bytes = media_to_wav_bytes(self.media_path)
            text = self.recognizer.recognize(wav_bytes)
            self.text_ready.emit(
                text,
                self.recognizer.engine_name,
                getattr(self.recognizer, "last_fallback_reason", None),
            )
        except Exception as error:
            self.error_occurred.emit(str(error))


class AudioLevelThread(QThread):
    """Поток обновления уровня звука."""

    level_updated = pyqtSignal(float)

    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder
        self._running = True

    def run(self):
        while self._running:
            level = self.recorder.get_audio_level()
            self.level_updated.emit(level)
            time.sleep(0.05)

    def stop(self):
        self._running = False


class RechTypeApp(QObject):
    """Основной класс приложения."""

    toggle_recording_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.recorder = AudioRecorder(microphone_index=self.config.get("microphone_index"))
        self.recognizer = create_recognizer(self.config)
        self.history = TranscriptionHistory()
        self.overlay = RecordingOverlay()
        self.transcription_window = TranscriptionWindow(
            default_model=self.config.get(
                "file_gigaam_model", DEFAULT_FILE_MODEL_ID
            )
        )
        self.transcription_window.transcription_requested.connect(
            self._start_file_transcription
        )

        self._recording = False
        self._processing = False
        self._pending_wav_bytes = None
        self._listener = None
        self._level_thread = None
        self.worker = None
        self._file_worker = None
        self._file_recognizer_id = None
        self._file_recognizer = None
        self._file_result = None
        self._file_error_message = None

        # RegisterHotKey runs a native message loop on a worker thread. Qt
        # safely queues this signal back to the GUI thread.
        self.toggle_recording_requested.connect(self._toggle_recording)

        self._setup_tray()
        self._setup_hotkey()

    def _setup_tray(self):
        """Создать иконку в системном трее."""
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self._create_icon())

        menu = QMenu()

        open_action = QAction("🗎 Открыть RechType", menu)
        open_action.triggered.connect(self.show_main_window)
        menu.addAction(open_action)

        file_action = QAction("🎧 Транскрибировать файл", menu)
        file_action.triggered.connect(self.show_main_window)
        menu.addAction(file_action)

        menu.addSeparator()

        mic_action = QAction("🎤 Выбрать микрофон", menu)
        mic_action.triggered.connect(self._select_microphone)
        menu.addAction(mic_action)

        hotkey_action = QAction("⌨️ Горячая клавиша", menu)
        hotkey_action.triggered.connect(self._change_hotkey)
        menu.addAction(hotkey_action)

        correction_action = QAction("📝 Исправить последнюю диктовку", menu)
        correction_action.triggered.connect(self._correct_last_transcription)
        menu.addAction(correction_action)

        learning_folder_action = QAction("📂 Папка обучающих данных", menu)
        learning_folder_action.triggered.connect(self._open_learning_folder)
        menu.addAction(learning_folder_action)

        menu.addSeparator()

        about_action = QAction("ℹ️ О программе", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        exit_action = QAction("❌ Выход", menu)
        exit_action.triggered.connect(self._exit)
        menu.addAction(exit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

        self.tray_icon.showMessage(
            "RechType",
            "Откройте окно для транскрибации файла или нажмите Ctrl+Space для диктовки.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def show_main_window(self):
        """Show and focus the file transcription window."""
        self.transcription_window.show()
        self.transcription_window.raise_()
        self.transcription_window.activateWindow()

    def _create_icon(self):
        """Создать иконку для трея."""
        from PyQt6.QtGui import QPixmap, QPainter, QBrush, QColor

        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(100, 200, 100)))
        painter.setPen(QColor(50, 150, 50))
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()
        return QIcon(pixmap)

    def _setup_hotkey(self):
        """Зарегистрировать системную горячую клавишу."""
        hotkey_str = self.config.get("hotkey", "ctrl+space")
        try:
            self._listener = self._start_hotkey_listener(hotkey_str)
            print(f"[RechType] Горячая клавиша-переключатель активна: {hotkey_str}")
        except Exception as e:
            print(f"[RechType] Ошибка настройки горячей клавиши: {e}")
            QMessageBox.critical(None, "Ошибка", f"Не удалось настроить горячую клавишу:\n{e}")

    def _start_hotkey_listener(self, hotkey_str: str) -> GlobalHotkeyListener:
        listener = GlobalHotkeyListener(hotkey_str, self.toggle_recording_requested.emit)
        return listener.start_and_wait()

    def _toggle_recording(self):
        """Первое нажатие запускает запись, второе — останавливает."""
        if self._processing:
            self.tray_icon.showMessage(
                "RechType",
                "Подождите: идёт распознавание предыдущей записи.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            return
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Начать запись."""
        if self._recording or self._processing:
            return
        print("[RechType] Начало записи...")
        try:
            self.recorder.start()
        except Exception as error:
            print(f"[RechType] Ошибка начала записи: {error}")
            self.tray_icon.showMessage(
                "RechType — Ошибка микрофона",
                str(error),
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )
            return
        self._recording = True
        self.overlay.show()

        self._level_thread = AudioLevelThread(self.recorder)
        self._level_thread.level_updated.connect(self.overlay.set_audio_level)
        self._level_thread.start()

    def _stop_recording(self):
        """Остановить запись и запустить распознавание."""
        if not self._recording:
            return
        print("[RechType] Остановка записи...")
        self._recording = False
        self.overlay.hide()

        if self._level_thread:
            self._level_thread.stop()
            self._level_thread.wait(1000)

        wav_bytes = self.recorder.stop()
        print(f"[RechType] Аудио записано: {len(wav_bytes)} байт")

        if len(wav_bytes) < 1000:
            print("[RechType] Запись слишком короткая, пропускаем")
            self._processing = False
            return

        self._pending_wav_bytes = wav_bytes
        self._processing = True
        self.worker = RecognitionWorker(wav_bytes, self.recognizer)
        self.worker.text_ready.connect(self._on_text_ready)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_text_ready(self, text: str):
        """Обработка готового текста."""
        print(f"[RechType] Распознано: {text}")
        try:
            if text.strip():
                try:
                    self.history.record(
                        self._pending_wav_bytes,
                        text,
                        getattr(self.recognizer, "engine_name", "unknown"),
                    )
                except Exception as history_error:
                    print(f"[RechType] Не удалось сохранить историю: {history_error}")
                self._type_text(text)
                fallback_reason = getattr(self.recognizer, "last_fallback_reason", None)
                if fallback_reason:
                    self.tray_icon.showMessage(
                        "RechType — резервный режим",
                        "GigaAM временно недоступна, эта запись распознана через Vosk.",
                        QSystemTrayIcon.MessageIcon.Warning,
                        4000,
                    )
        finally:
            self._pending_wav_bytes = None
            self._processing = False

    def _on_error(self, error: str):
        """Обработка ошибки."""
        self._processing = False
        self._pending_wav_bytes = None
        print(f"[RechType] Ошибка распознавания: {error}")
        self.tray_icon.showMessage(
            "RechType — Ошибка",
            f"Не удалось распознать речь:\n{error}",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def _start_file_transcription(self, media_path: str, model_id: str):
        """Start decoding and recognizing one selected media file."""
        if self._recording:
            self.transcription_window.show_error(
                "Сначала остановите запись с микрофона повторным нажатием горячей клавиши."
            )
            return
        if self._processing:
            self.transcription_window.show_error(
                "Дождитесь завершения текущего распознавания."
            )
            return

        try:
            if self._file_recognizer_id != model_id or self._file_recognizer is None:
                # Retain only the last file model. Keeping both 220M and 600M
                # models resident would waste several gigabytes of RAM.
                self._file_recognizer = None
                self._file_recognizer_id = None
                gc.collect()
                self._file_recognizer = create_file_recognizer(
                    self.config, model_id
                )
                self._file_recognizer_id = model_id
        except (OSError, TypeError, ValueError) as error:
            self.transcription_window.show_error(str(error))
            return

        if self.config.get("file_gigaam_model") != model_id:
            self.config["file_gigaam_model"] = model_id
            try:
                save_config(self.config)
            except OSError as error:
                print(f"[RechType] Не удалось сохранить выбор модели: {error}")

        primary = getattr(self._file_recognizer, "primary", None)
        model_needs_download = bool(
            primary is not None
            and getattr(primary, "allow_download", False)
            and not getattr(primary, "model_available", True)
        )
        if model_needs_download:
            download_bytes = int(
                FILE_MODEL_SPECS.get(model_id, {}).get("download_bytes", 0)
            )
            if not _file_model_download_fits(primary, download_bytes):
                self.transcription_window.show_error(
                    "Недостаточно места для загрузки выбранной модели. "
                    "Освободите не менее 2,7 ГиБ и повторите попытку."
                )
                return

        self._processing = True
        self._file_result = None
        self._file_error_message = None
        status_message = (
            f"Подготавливаю файл и загружаю {FILE_MODEL_SPECS[model_id]['label']} "
            "(около 2,18 ГиБ). Не закрывайте приложение…"
            if model_needs_download
            else "Извлекаю аудиодорожку и распознаю речь. Для длинного файла это может занять время…"
        )
        self.transcription_window.set_busy(True, status_message)
        self._file_worker = FileRecognitionWorker(
            media_path, self._file_recognizer
        )
        self._file_worker.text_ready.connect(self._on_file_text_ready)
        self._file_worker.error_occurred.connect(self._on_file_error)
        self._file_worker.finished.connect(self._on_file_worker_finished)
        self._file_worker.start()

    def _on_file_text_ready(
        self, text: str, engine_name: str, fallback_reason: str | None
    ):
        """Keep a file result until its worker has fully stopped."""
        self._file_result = (text, engine_name, fallback_reason)

    def _on_file_error(self, error: str):
        """Keep a worker error until its thread has fully stopped."""
        self._file_error_message = error

    def _on_file_worker_finished(self):
        worker = self.sender()
        if worker is not self._file_worker:
            if worker is not None:
                worker.deleteLater()
            return
        self._file_worker = None
        self._processing = False
        error = self._file_error_message
        result = self._file_result
        self._file_error_message = None
        self._file_result = None
        if worker is not None:
            worker.deleteLater()
        if error:
            self.transcription_window.show_error(error)
            self.show_main_window()
            return
        if result is None:
            self.transcription_window.show_error("Транскрибация завершилась без результата.")
            self.show_main_window()
            return

        text, engine_name, fallback_reason = result
        self.transcription_window.set_result(text, engine_name)
        self.show_main_window()
        if text.strip():
            self.tray_icon.showMessage(
                "RechType",
                "Транскрибация файла завершена.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        if fallback_reason:
            self.tray_icon.showMessage(
                "RechType — резервный режим",
                "GigaAM временно недоступна, файл распознан через Vosk.",
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )

    def _correct_last_transcription(self):
        """Let the user explicitly create a trusted audio/text pair."""
        record = self.history.last_record()
        if not record:
            QMessageBox.information(None, "Исправление", "История диктовок пока пуста.")
            return
        initial_text = record.get("corrected_text") or record.get("raw_text", "")
        text, ok = QInputDialog.getMultiLineText(
            None,
            "Исправить последнюю диктовку",
            "Исправьте текст и нажмите OK. Аудио и исправление останутся только на этом компьютере:",
            initial_text,
        )
        if not ok:
            return
        try:
            self.history.correct_last(text)
        except Exception as error:
            QMessageBox.warning(None, "Исправление", str(error))
            return
        self.tray_icon.showMessage(
            "RechType",
            "Исправление сохранено в локальный обучающий набор.",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

    def _open_learning_folder(self):
        """Open the private local correction dataset on explicit user request."""
        self.history.base_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.history.base_dir)))

    def _type_text(self, text: str):
        """Вставить Unicode-текст, используя буфер обмена как fallback."""
        # Give Windows a moment to process the physical hotkey key-up events.
        time.sleep(0.15)
        try:
            event_count = paste_text(text)
            print(f"[RechType] SendInput отправил событий: {event_count}")
            print(f"[RechType] Текст вставлен: {text[:50]}...")
            return
        except Exception as direct_error:
            print(f"[RechType] Прямая вставка не удалась: {direct_error}")

        try:
            event_count = paste_text_clipboard(text)
            print(f"[RechType] Fallback Ctrl+V отправил событий: {event_count}")
            print(f"[RechType] Текст вставлен через буфер: {text[:50]}...")
        except Exception as fallback_error:
            print(f"[RechType] Ошибка вставки через буфер: {fallback_error}")
            self.tray_icon.showMessage(
                "RechType — Ошибка вставки",
                "Windows не разрешила вставить текст. "
                "Если целевое приложение запущено от администратора, "
                "запустите RechType с теми же правами.",
                QSystemTrayIcon.MessageIcon.Warning,
                7000,
            )

    def _select_microphone(self):
        """Диалог выбора микрофона."""
        mics = self.recorder.list_microphones()
        if not mics:
            QMessageBox.warning(None, "Микрофоны", "Микрофоны не найдены!")
            return

        items = [f"{idx}: {name}" for idx, name in mics]

        text, ok = QInputDialog.getItem(
            None, "Выбор микрофона", "Микрофон:",
            ["По умолчанию"] + items, 0, False
        )
        if ok and text:
            if text == "По умолчанию":
                self.config["microphone_index"] = None
            else:
                idx = int(text.split(":")[0])
                self.config["microphone_index"] = idx
            save_config(self.config)
            self.recorder = AudioRecorder(microphone_index=self.config["microphone_index"])
            self.tray_icon.showMessage("RechType", f"Микрофон: {text}",
                QSystemTrayIcon.MessageIcon.Information, 2000)

    def _change_hotkey(self):
        """Изменить горячую клавишу."""
        text, ok = QInputDialog.getText(
            None, "Горячая клавиша",
            "Комбинация (например: ctrl+space, alt+f2):",
            text=self.config.get("hotkey", "ctrl+space")
        )
        if ok and text:
            hotkey_str = text.lower().strip()
            if hotkey_str == self.config.get("hotkey", "ctrl+space"):
                return
            try:
                new_listener = self._start_hotkey_listener(hotkey_str)
            except Exception as error:
                QMessageBox.warning(
                    None,
                    "Горячая клавиша",
                    f"Не удалось назначить сочетание:\n{error}",
                )
                return

            old_listener = self._listener
            self._listener = new_listener
            if old_listener:
                old_listener.stop()
            self.config["hotkey"] = new_listener.spec.canonical
            save_config(self.config)
            self.tray_icon.showMessage("RechType", f"Горячая клавиша: {new_listener.spec.canonical}",
                QSystemTrayIcon.MessageIcon.Information, 2000)

    def _show_about(self):
        """Показать информацию о программе."""
        QMessageBox.information(
            None, "О программе",
            "<h2>RechType</h2>"
            f"<p><b>Версия:</b> {__version__}</p>"
            "<p>Приложение для голосовой диктовки с локальным распознаванием речи.</p>"
            "<p><b>Файлы:</b> транскрибация аудио и видео в главном окне</p>"
            "<p><b>Диктовка:</b> GigaAM v3 e2e RNNT (Vosk как резерв)</p>"
            "<p><b>Файлы:</b> выбираемая GigaAM Multilingual Large 600M или v3 e2e RNNT</p>"
            "<p><b>Обучение:</b> исправления сохраняются локально через меню в трее</p>"
            "<p><b>Горячая клавиша:</b> Ctrl+Space (нажать для старта/остановки)</p>"
            "<p>Распознавание выполняется локально. Сеть нужна только для первой загрузки Large-модели.</p>"
        )

    def _tray_activated(self, reason):
        """Обработка клика по иконке трея."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_main_window()

    def _exit(self):
        """Завершить работу."""
        recognition_running = self.worker is not None and self.worker.isRunning()
        file_recognition_running = (
            self._file_worker is not None and self._file_worker.isRunning()
        )
        if recognition_running or file_recognition_running:
            QMessageBox.information(
                self.transcription_window,
                "RechType",
                "Дождитесь завершения распознавания перед выходом.",
            )
            return
        self._recording = False
        if self._listener:
            self._listener.stop()
        if self._level_thread:
            self._level_thread.stop()
        self.recorder.close()
        self.transcription_window.close()
        self.tray_icon.hide()
        QApplication.quit()


def _notify_running_instance() -> bool:
    """Ask an existing RechType process to show its window, if one exists."""
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_NAME)
    if not socket.waitForConnected(350):
        return False
    socket.write(b"show")
    socket.waitForBytesWritten(350)
    socket.disconnectFromServer()
    return True


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RechType")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)

    if _notify_running_instance():
        return 0

    QLocalServer.removeServer(SINGLE_INSTANCE_NAME)
    instance_server = QLocalServer()
    if not instance_server.listen(SINGLE_INSTANCE_NAME):
        QMessageBox.critical(None, "RechType", "Не удалось запустить единственный экземпляр приложения.")
        return 1

    # Отладочная версия: НЕ скрываем консоль!
    # try:
    #     import ctypes
    #     ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    # except:
    #     pass

    rechtype = RechTypeApp()

    def handle_instance_message():
        while instance_server.hasPendingConnections():
            socket = instance_server.nextPendingConnection()
            if socket is None:
                continue
            socket.waitForReadyRead(350)
            if bytes(socket.readAll()).strip() == b"show":
                rechtype.show_main_window()
            socket.disconnectFromServer()

    instance_server.newConnection.connect(handle_instance_message)
    if "--background" not in sys.argv and "--minimized" not in sys.argv:
        rechtype.show_main_window()
    return app.exec()


if __name__ == "__main__":
    main()

# Сторонние компоненты

RechType использует стороннее программное обеспечение и модели. Каждый компонент сохраняет собственную лицензию.

## Основные компоненты

| Компонент | Назначение | Лицензия upstream |
|---|---|---|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | интерфейс и системный трей | GPL v3 или коммерческая лицензия Riverbank |
| [Qt](https://www.qt.io/licensing/open-source-lgpl-obligations) | нативный GUI-фреймворк | LGPL/GPL или коммерческая лицензия, в зависимости от модуля |
| [GigaAM](https://github.com/salute-developers/GigaAM) | основное распознавание русской речи | MIT |
| [Vosk API](https://github.com/alphacep/vosk-api) | резервное распознавание | Apache-2.0 |
| [Vosk models](https://alphacephei.com/vosk/models) | модель `vosk-model-small-ru-0.22` | Apache-2.0 |
| [PyTorch](https://github.com/pytorch/pytorch) | выполнение GigaAM | BSD-3-Clause |
| [NumPy](https://github.com/numpy/numpy) | обработка аудиомассивов | BSD-3-Clause |
| [SciPy](https://github.com/scipy/scipy) | численные операции | BSD-3-Clause |
| [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) | запись с микрофона | MIT |
| [PyAV](https://github.com/PyAV-Org/PyAV) | чтение аудио- и видеоконтейнеров | BSD-3-Clause |
| [FFmpeg 8.1.2](https://ffmpeg.org/) | декодирование медиаданных | встроенная библиотека сообщает LGPL v3 или новее |
| Библиотеки кодеков из [pyav-ffmpeg 8.1.2-1](https://github.com/PyAV-Org/pyav-ffmpeg/releases/tag/8.1.2-1) | поддержка форматов FFmpeg | отдельные лицензии, включая GPL, LGPL, BSD, MIT, Apache-2.0 и Zlib; см. `THIRD_PARTY_LICENSES/media` |

Часть JPEG-кода FFmpeg происходит из Independent JPEG Group: **this software
is based in part on the work of the Independent JPEG Group**. Полные IJG и
x86inc/ISC-уведомления находятся в `THIRD_PARTY_LICENSES/media`.

Полный список транзитивных зависимостей определяется `requirements.txt` и метаданными установленного окружения.

## Правила для бинарных релизов

Сборка должна включать каталог `THIRD_PARTY_LICENSES` с применимыми текстами лицензий и уведомлениями из установленных Python-пакетов, Qt, PyAV, FFmpeg и библиотек кодеков. Исходный код соответствующей версии FFmpeg, точные версии зависимостей и сценарии сборки доступны в проектах [FFmpeg](https://ffmpeg.org/download.html) и [pyav-ffmpeg](https://github.com/PyAV-Org/pyav-ffmpeg). Модели нельзя переименовывать или распространять с заявлением об авторстве RechType. Перед каждым публичным релизом сопровождающий повторно проверяет актуальные условия upstream-компонентов.

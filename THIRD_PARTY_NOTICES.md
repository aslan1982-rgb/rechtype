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

Полный список транзитивных зависимостей определяется `requirements.txt` и метаданными установленного окружения.

## Правила для бинарных релизов

Сборка должна включать применимые тексты лицензий и уведомления из установленных Python-пакетов и Qt. Модели нельзя переименовывать или распространять с заявлением об авторстве RechType. Перед каждым публичным релизом сопровождающий повторно проверяет актуальные условия upstream-компонентов.

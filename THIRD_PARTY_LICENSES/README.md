# Лицензии сторонних компонентов

Этот каталог входит в бинарный архив RechType и содержит копии лицензий и
уведомлений сторонних компонентов. Файлы не заменяют условия соответствующих
лицензий; при расхождении применяется текст лицензии самого компонента.

## Python и нативные зависимости

- `python/` содержит неизменённые `LICENSE`, `COPYING` и `NOTICE` из метаданных
  wheel-пакетов окружения, использованного для сборки. В частности, там есть
  тексты для PyQt6/Qt, PyTorch/TorchAudio, PyAV, GigaAM, NumPy, SciPy, PyAudio,
  SoundFile, Hydra/OmegaConf и транзитивных Python-зависимостей.
- `runtime/` содержит лицензии Python 3.11, Vosk и модели Vosk,
  SentencePiece, ONNX Runtime, libsndfile, PortAudio и OpenSSL.
- Бесплатный wheel `PyQt6==6.11.0`, включённый в эту сборку, распространяется
  по `GPL-3.0-only`; wheel библиотек Qt использует `LGPL-3.0-only`.

## QtBase 6.11.0

В сборку входят ровно шесть файлов Qt: `Qt6Core.dll`, `Qt6Gui.dll`,
`Qt6Network.dll`, `Qt6Widgets.dll`, `qwindows.dll` и `opengl32sw.dll`.
Каталог `qt/qtbase-6.11.0/` содержит выбранные для них исходные
`qt_attribution.json`, все указанные в них `LicenseFile` и необходимые тексты
лицензий с сохранением путей из архива QtBase `v6.11.0`. Файл
`qt/qtbase-6.11.0/MANIFEST.md` фиксирует состав, версии и SHA-256 всех шести
бинарных файлов.

Поставляемый Qt программный OpenGL-рендерер `opengl32sw.dll` идентифицирован
как Mesa llvmpipe 11.2.2 со статическим LLVM 3.6.2. Их точные лицензии и
официальные уведомления Qt находятся в
`qt/qtbase-6.11.0/opengl32sw/`.

## FFmpeg и медиабиблиотеки

Windows wheel `av==18.1.0` использует FFmpeg 8.1.2 и бинарную сборку
[`pyav-ffmpeg` 8.1.2-1](https://github.com/PyAV-Org/pyav-ffmpeg/releases/tag/8.1.2-1).
Встроенная функция `avcodec_license()` сообщает для библиотек FFmpeg:
`LGPL version 3 or later`. Wheel также содержит отдельные библиотеки кодеков;
они сохраняют собственные условия:

| Компонент | Версия сборки | Лицензия / файл |
|---|---:|---|
| FFmpeg | 8.1.2 | LGPL-3.0-or-later + IJG/ISC notices — `media/FFmpeg-LGPL-3.0-or-later.txt`, companion `media/FFmpeg-GPL-3.0.txt`, `media/FFmpeg-IJG-NOTICE.txt`, `media/x86inc-ISC-notices.txt` |
| LAME | 3.100 | LGPL-2.0-or-later — `media/LAME-LGPL-2.0.txt`, `media/LAME-LICENSE.txt` |
| Opus | 1.6.1 | BSD-3-Clause — `media/Opus-BSD-3-Clause.txt` |
| dav1d | 1.5.3 | BSD-2-Clause + AOMPL-1.0 + ISC notice — `media/dav1d-*`, `media/x86inc-ISC-notices.txt` |
| SVT-AV1 | 4.1.0 | BSD-3-Clause-Clear + AOMPL-1.0; bundled fastfeat BSD-3-Clause and x86inc ISC — `media/SVT-AV1-*`, `media/x86inc-ISC-notices.txt` |
| libvpx | 1.16.0 | BSD-3-Clause + WebM patent grant + ISC notice — `media/libvpx-*`, `media/x86inc-ISC-notices.txt` |
| libwebp / libwebpmux / libsharpyuv | 1.6.0 | BSD-3-Clause + WebM patent grant — `media/libwebp-*` |
| OpenCORE-AMR | 0.1.6 | Apache-2.0 + upstream notices — `media/OpenCORE-AMR-Apache-2.0.txt`, `media/OpenCORE-AMR-NOTICE.txt` |
| x264 | `b35605a` | GPL-2.0-or-later + ISC notice — `media/x264-GPL-2.0-or-later.txt`, `media/x86inc-ISC-notices.txt` |
| x265 | 4.2 | GPL-2.0-or-later + ISC notice — `media/x265-GPL-2.0-or-later.txt`, `media/x265-source-header-notice.txt`, `media/x86inc-ISC-notices.txt` |
| AMF headers / nv-codec-headers | 1.5.0 / n13.0.19.0 | MIT-style header notices — `media/AMF-headers-MIT.txt`, `media/NV-codec-headers-*` |
| oneVPL | 2.16.0 | MIT — `media/oneVPL-MIT.txt` |
| zlib | системная сборка MinGW | Zlib — `media/zlib-Zlib.txt` |
| libiconv | системная сборка MinGW | LGPL-2.1-or-later — `media/libiconv-LGPL-2.1.txt` |
| GCC/MinGW runtime | GCC 16.1.0; точная версия MinGW-w64 не записана в wheel | GPL-3.0-or-later WITH GCC-exception-3.1 и уведомления MinGW/winpthreads — `media/GCC-*`, `media/MinGW-*`, `media/winpthreads-*` |

Исходники точных версий FFmpeg и кодеков перечислены вместе с SHA-256 в
[`scripts/pkg.py`](https://github.com/PyAV-Org/pyav-ffmpeg/blob/8.1.2-1/scripts/pkg.py).
Исходный код RechType и инструкция воспроизводимой сборки находятся в том же
GitHub-релизе/теге, что и бинарный архив.

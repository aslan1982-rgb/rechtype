# Подготовка релиза

## 1. Проверки перед сборкой

```powershell
python -m pip install -r requirements-test.txt
python -m pytest -q
python -m compileall -q src tools
```

Проверьте, что в Git нет `DATASET`, записей пользователя, `config.json`, моделей, архивов и исполняемых файлов.

## 2. Полное окружение и модели

```powershell
python -m pip install -r requirements-build.txt
python tools\download_models.py
```

Для воспроизводимой сборки используйте Python 3.11 x64 и короткий путь без кириллицы.

## 3. Сборка

```powershell
python -m PyInstaller --noconfirm --clean rechtype.spec
```

Если модели уже находятся вне репозитория, укажите их корневую папку без копирования:

```powershell
$env:RECHTYPE_MODEL_ROOT = "D:\models"
python -m PyInstaller --noconfirm --clean rechtype.spec
```

Результат находится в `dist\RechType`.

## 4. Проверка

- Запустите программу на чистой Windows 10 или 11 без установленного Python и ffmpeg.
- Убедитесь, что используется `GigaAM v3_e2e_rnnt`, а не резервный Vosk.
- Проверьте запись дольше 25 секунд, таймер, остановку вторым нажатием и вставку в несколько приложений.
- С очищенным `PATH` проверьте импорт WAV, MP3 и видео MP4 с аудиодорожкой.
- Проверьте понятную ошибку для видео без аудиодорожки и повреждённого файла.
- Убедитесь, что повторный запуск открывает существующее окно, а `--background` оставляет его скрытым.
- Проверьте, что приложение не создаёт и не отправляет сетевые запросы во время диктовки.

Для машинной end-to-end проверки файла используйте скрытый режим сборки:

```powershell
dist\RechType\RechType.exe --media-self-test work\sample.mp4 work\media-report.json
```

## 5. Архив и контрольная сумма

```powershell
$archive = "RechType-v0.0.2-Windows-x64.zip"
$checksum = "RechType-v0.0.2-Windows-x64-SHA256.txt"
Copy-Item README.md, LICENSE, THIRD_PARTY_NOTICES.md, RELEASE-NOTES-v0.0.2.txt dist\RechType
Copy-Item THIRD_PARTY_LICENSES dist\RechType -Recurse
Compress-Archive -Path dist\RechType -DestinationPath $archive
$sha256 = (Get-FileHash $archive -Algorithm SHA256).Hash
"$sha256  $archive" | Set-Content $checksum -Encoding ascii
```

Архив не добавляется в Git. Прикрепите его и файл с SHA-256 к GitHub Release соответствующего тега.

## 6. Лицензии

В бинарный архив должны войти `README.md`, `LICENSE`, `THIRD_PARTY_NOTICES.md`, каталог `THIRD_PARTY_LICENSES`, заметки текущего релиза и применимые тексты лицензий сторонних пакетов и моделей. Перед публикацией повторно проверьте актуальные условия PyQt6, Qt, GigaAM, Vosk, PyAV и включённой в wheel сборки FFmpeg.

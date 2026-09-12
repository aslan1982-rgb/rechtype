# Модели

Большие модели распознавания не хранятся в Git.

Запустите из корня репозитория:

```powershell
python tools\download_models.py
```

После выполнения для базовой сборки ожидаются:

```text
models/
├── gigaam/
│   ├── v3_e2e_rnnt.ckpt
│   └── v3_e2e_rnnt_tokenizer.model
└── vosk-model-small-ru-0.22/
```

Потоковая диктовка всегда использует GigaAM v3 e2e RNNT с резервным переходом на Vosk. Для распознавания файла пользователь может выбрать GigaAM v3 e2e RNNT или GigaAM Multilingual Large 600M; Large-модель выбрана по умолчанию.

При первом выборе Large-модели приложение один раз скачивает checkpoint размером около 2,18 ГиБ в пользовательский каталог:

```text
%LOCALAPPDATA%\RechType\models\gigaam\multilingual_large_ctc.ckpt
```

После загрузки Large-модель работает офлайн. Она не хранится в Git и не входит в базовый release archive: размер raw checkpoint превышает лимит GitHub в 2 ГиБ на один asset.

Лицензии и источники моделей перечислены в `THIRD_PARTY_NOTICES.md`.

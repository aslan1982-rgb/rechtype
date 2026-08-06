# Модели

Большие модели распознавания не хранятся в Git.

Запустите из корня репозитория:

```powershell
python tools\download_models.py
```

После выполнения ожидаются:

```text
models/
├── gigaam/
│   ├── v3_e2e_rnnt.ckpt
│   └── v3_e2e_rnnt_tokenizer.model
└── vosk-model-small-ru-0.22/
```

Лицензии и источники моделей перечислены в `THIRD_PARTY_NOTICES.md`.

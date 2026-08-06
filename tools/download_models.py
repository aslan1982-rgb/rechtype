"""Download the ASR models required by source and PyInstaller builds."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
VOSK_NAME = "vosk-model-small-ru-0.22"
VOSK_URL = f"https://alphacephei.com/vosk/models/{VOSK_NAME}.zip"


def download_vosk() -> None:
    destination = MODELS_DIR / VOSK_NAME
    if destination.is_dir():
        print(f"Vosk already exists: {destination}")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rechtype-model-") as temp_dir:
        archive_path = Path(temp_dir) / f"{VOSK_NAME}.zip"
        print(f"Downloading Vosk from {VOSK_URL}")
        urllib.request.urlretrieve(VOSK_URL, archive_path)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if not names or any(
                Path(name).is_absolute() or ".." in Path(name).parts for name in names
            ):
                raise ValueError("Vosk archive contains an unsafe path")
            archive.extractall(temp_dir)
        extracted = Path(temp_dir) / VOSK_NAME
        if not extracted.is_dir():
            raise FileNotFoundError(f"Expected {VOSK_NAME} in the downloaded archive")
        shutil.move(str(extracted), destination)
    print(f"Vosk is ready: {destination}")


def download_gigaam() -> None:
    destination = MODELS_DIR / "gigaam"
    checkpoint = destination / "v3_e2e_rnnt.ckpt"
    tokenizer = destination / "v3_e2e_rnnt_tokenizer.model"
    if checkpoint.is_file() and tokenizer.is_file():
        print(f"GigaAM already exists: {destination}")
        return

    import gigaam

    destination.mkdir(parents=True, exist_ok=True)
    print("Downloading and verifying GigaAM v3 e2e RNNT...")
    gigaam.load_model(
        "v3_e2e_rnnt",
        device="cpu",
        fp16_encoder=False,
        use_flash=False,
        download_root=str(destination),
    )
    print(f"GigaAM is ready: {destination}")


def main() -> None:
    download_vosk()
    download_gigaam()
    print("All models are ready.")


if __name__ == "__main__":
    main()

"""Private local history and correction data for future ASR adaptation."""

from __future__ import annotations

import io
import json
import os
import wave
from datetime import datetime
from pathlib import Path


def default_learning_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    preferred = root / "RechType" / "learning"
    legacy = root / "VoiceFlow Local" / "learning"
    # Existing users keep their correction history after the product rename.
    if not preferred.exists() and legacy.exists():
        return legacy
    return preferred


class TranscriptionHistory:
    """Store audio, raw text, and explicit user corrections only on this PC."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else default_learning_dir()
        self.records_dir = self.base_dir / "records"
        self.manifest_path = self.base_dir / "training-manifest.tsv"
        self._last_record_path: Path | None = None

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _duration_seconds(wav_bytes: bytes) -> float:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            return wav.getnframes() / wav.getframerate()

    def record(self, wav_bytes: bytes, raw_text: str, engine: str) -> dict:
        now = datetime.now().astimezone()
        record_id = now.strftime("%Y%m%d-%H%M%S-%f")
        record_dir = self.records_dir / now.strftime("%Y-%m-%d") / record_id
        record_dir.mkdir(parents=True, exist_ok=False)
        audio_path = record_dir / "audio.wav"
        metadata_path = record_dir / "record.json"
        audio_path.write_bytes(wav_bytes)
        metadata = {
            "schema_version": 1,
            "id": record_id,
            "created_at": now.isoformat(),
            "engine": engine,
            "duration_seconds": round(self._duration_seconds(wav_bytes), 3),
            "audio_path": str(audio_path),
            "raw_text": raw_text,
            "corrected_text": None,
            "corrected_at": None,
        }
        self._write_json(metadata_path, metadata)
        self._last_record_path = metadata_path
        return metadata

    def _find_last_path(self) -> Path | None:
        if self._last_record_path and self._last_record_path.exists():
            return self._last_record_path
        if not self.records_dir.exists():
            return None
        paths = sorted(self.records_dir.glob("*/*/record.json"), reverse=True)
        self._last_record_path = paths[0] if paths else None
        return self._last_record_path

    def last_record(self) -> dict | None:
        path = self._find_last_path()
        if not path:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def correct_last(self, corrected_text: str) -> dict:
        path = self._find_last_path()
        if not path:
            raise LookupError("История диктовок пока пуста")
        text = corrected_text.strip()
        if not text:
            raise ValueError("Исправленный текст не может быть пустым")
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["corrected_text"] = text
        metadata["corrected_at"] = datetime.now().astimezone().isoformat()
        self._write_json(path, metadata)
        (path.parent / "corrected.txt").write_text(text, encoding="utf-8")
        self.build_training_manifest()
        return metadata

    def build_training_manifest(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        rows = ["path\tduration\ttranscription"]
        if self.records_dir.exists():
            for path in sorted(self.records_dir.glob("*/*/record.json")):
                metadata = json.loads(path.read_text(encoding="utf-8"))
                corrected = metadata.get("corrected_text")
                if not corrected:
                    continue
                clean_text = " ".join(str(corrected).split())
                rows.append(
                    f"{metadata['audio_path']}\t{metadata['duration_seconds']}\t{clean_text}"
                )
        self.manifest_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return self.manifest_path

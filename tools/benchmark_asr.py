"""Reproducible WER/CER benchmark for RechType recognizers."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voiceflow.recognizer import (  # noqa: E402
    FILE_MODEL_SPECS,
    GigaAMRecognizer,
    VoskRecognizer,
)


def tokens(text: str) -> list[str]:
    return re.findall(r"[а-яёa-z0-9]+", text.lower())


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_item in reference:
        current = [previous[0] + 1]
        for index, hypothesis_item in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1] + (reference_item != hypothesis_item),
                )
            )
        previous = current
    return previous[-1]


def metrics(reference: str, hypothesis: str) -> dict[str, float | int]:
    reference_words = tokens(reference)
    hypothesis_words = tokens(hypothesis)
    reference_chars = list("".join(reference_words))
    hypothesis_chars = list("".join(hypothesis_words))
    word_edits = edit_distance(reference_words, hypothesis_words)
    char_edits = edit_distance(reference_chars, hypothesis_chars)
    return {
        "reference_words": len(reference_words),
        "hypothesis_words": len(hypothesis_words),
        "word_edits": word_edits,
        "wer": word_edits / len(reference_words),
        "char_edits": char_edits,
        "cer": char_edits / len(reference_chars),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--engine", choices=["gigaam", "vosk"], required=True)
    parser.add_argument(
        "--gigaam-model",
        choices=FILE_MODEL_SPECS,
        default="v3_e2e_rnnt",
    )
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.engine == "gigaam":
        recognizer = GigaAMRecognizer(
            model_name=args.gigaam_model,
            model_dir=args.model_dir,
            allow_download=args.gigaam_model == "multilingual_large_ctc",
        )
    else:
        recognizer = VoskRecognizer(model_path=args.model_dir)

    started = time.perf_counter()
    transcript = recognizer.recognize(args.audio.read_bytes())
    elapsed = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(transcript, encoding="utf-8")
    report = {
        "engine": recognizer.engine_name,
        "elapsed_seconds": elapsed,
        **metrics(args.reference.read_text(encoding="utf-8"), transcript),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

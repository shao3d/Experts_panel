#!/usr/bin/env python3
"""Local ASR helper for the video ingest pipeline (faster-whisper, CPU int8).

Runs under a Python that has `faster_whisper` installed (system python3.11),
not necessarily the backend venv. Writes a JSON transcript with timestamps and
optional word-level timings. Language is auto-detected unless --language is set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="faster-whisper ASR for video ingest")
    parser.add_argument("audio", help="audio file (m4a/wav/webm/mp3)")
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument(
        "--model",
        default="mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        help="HuggingFace model id or local CTranslate2 dir",
    )
    parser.add_argument("--language", default=None, help="force language, default auto-detect")
    parser.add_argument("--initial-prompt", default=None, help="glossary biasing for names/terms")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--no-vad", action="store_true", help="disable Silero VAD")
    parser.add_argument("--no-words", action="store_true", help="skip word-level timings")
    args = parser.parse_args()

    audio = os.path.abspath(args.audio)
    if not os.path.exists(audio):
        sys.exit(f"audio not found: {audio}")

    from faster_whisper import WhisperModel

    print(f"[asr] model: {args.model} (cpu, int8) | vad: {not args.no_vad}", flush=True)
    load_started = time.time()
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    print(f"[asr] model loaded in {time.time() - load_started:.1f}s", flush=True)

    started = time.time()
    segments_iter, info = model.transcribe(
        audio,
        language=args.language,
        beam_size=args.beam_size,
        vad_filter=not args.no_vad,
        word_timestamps=not args.no_words,
        initial_prompt=args.initial_prompt,
    )
    audio_duration = info.duration

    segments = []
    last_report = time.time()
    for seg in segments_iter:
        segments.append(seg)
        now = time.time()
        if now - last_report >= 60:
            elapsed = now - started
            if audio_duration:
                pct = seg.end / audio_duration * 100
                eta = (elapsed / max(seg.end, 0.5)) * max(audio_duration - seg.end, 0)
                print(
                    f"[asr] {seg.end:.0f}/{audio_duration:.0f}s ({pct:.0f}%), "
                    f"elapsed {elapsed / 60:.1f}m, ETA ~{eta / 60:.1f}m",
                    flush=True,
                )
            else:
                print(f"[asr] elapsed {elapsed / 60:.1f}m...", flush=True)
            last_report = now

    wall = time.time() - started
    words_count = sum(len(s.words) for s in segments if s.words)

    payload = {
        "audio": audio,
        "model": args.model,
        "compute_type": "int8",
        "language": info.language,
        "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 4),
        "language_forced": args.language,
        "vad": not args.no_vad,
        "audio_duration_s": round(audio_duration, 2),
        "wall_time_s": round(wall, 2),
        "rt_factor": round(wall / audio_duration, 3) if audio_duration else None,
        "segments_count": len(segments),
        "words_count": words_count,
        "segments": [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in segments
        ],
    }
    if not args.no_words:
        payload["words"] = [
            {"word": w.word, "start": round(w.start, 2), "end": round(w.end, 2)}
            for s in segments
            for w in (s.words or [])
        ]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)

    print(
        f"[asr] audio {audio_duration:.0f}s transcribed in {wall:.0f}s "
        f"(x{payload['rt_factor']}) | language={info.language} "
        f"(p={payload['language_probability']})",
        flush=True,
    )
    print(f"[asr] segments: {len(segments)}, words: {words_count}", flush=True)
    print(f"[asr] saved: {args.out}", flush=True)


if __name__ == "__main__":
    main()

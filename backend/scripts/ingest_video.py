#!/usr/bin/env python3
"""Video ingest stage 1: transcript + chunked frame triage + window plan.

Produces working artifacts only: no database writes, no LLM calls. The output
directory is a self-contained review package. Long videos are processed in
chunks (10-15 min with overlap) so a downstream LLM pass never has to hold the
whole video at once: it reads one chunk, writes its segments JSON to disk, and
forgets the frames.

Pipeline:
  1. media metadata (ffprobe)
  2. audio track (provided or extracted)
  3. ASR with a domain glossary (faster-whisper via a separate Python)
  4. chunk ranges with overlap
  5. per chunk: coarse frame grid (native resolution) + contact sheets
  6. per chunk: per-second frame-change curve (numpy) -> "hot" windows
  7. per chunk: speech-cue windows from the transcript
  8. per chunk: dense extraction for the union of windows, deduped, capped
  9. --combine: merge per-chunk segments JSON into one video-level JSON
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.cli.bootstrap import bootstrap_cli  # noqa: E402

BACKEND_DIR, logger = bootstrap_cli(__file__, logger_name="cli.ingest_video")

DEFAULT_ASR_MODEL = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
DEFAULT_GLOSSARY = (
    "Seedance, Higgsfield, Kling, Veo, Runway, Pika, Luma, Dream Machine, "
    "MiniMax Hailuo, Wan, Sora, Midjourney, ComfyUI, Stable Diffusion, Flux, "
    "Nano Banana, Seedream, negatives, guidance, keyframe"
)
CUES_EN = (
    "look at", "you can see", "see how", "in the prompt", "the prompt", "prompt",
    "settings", "select", "click", "press", "choose", "duration", "resolution",
    "aspect ratio", "generate", "credits", "interface", "on screen",
)
CUES_RU = (
    "промт", "настройк", "нажми", "выбер", "разрешен", "кадр", "интерфейс",
    "кнопк", "генер", "кредит", "на экране",
)


def run_ffmpeg(args: list[str], description: str) -> None:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({description}): {result.stderr[-400:]}")


def probe_media(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), None
    )
    audio_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None
    )
    fps = None
    if video_stream and video_stream.get("r_frame_rate"):
        num, _, den = video_stream["r_frame_rate"].partition("/")
        try:
            fps = round(float(num) / float(den or 1), 3)
        except (ValueError, ZeroDivisionError):
            fps = None
    return {
        "duration_s": round(float(data["format"].get("duration", 0.0)), 2),
        "size_bytes": int(data["format"].get("size", 0) or 0),
        "container": data["format"].get("format_name"),
        "video": {
            "codec": (video_stream or {}).get("codec_name"),
            "width": (video_stream or {}).get("width"),
            "height": (video_stream or {}).get("height"),
            "fps": fps,
        }
        if video_stream
        else None,
        "audio": {
            "codec": (audio_stream or {}).get("codec_name"),
            "sample_rate": (audio_stream or {}).get("sample_rate"),
            "channels": (audio_stream or {}).get("channels"),
        }
        if audio_stream
        else None,
    }


def ensure_audio(video: Path, out_dir: Path, provided: Path | None) -> Path:
    if provided is not None:
        if not provided.exists():
            raise FileNotFoundError(f"audio not found: {provided}")
        return provided
    audio_path = out_dir / "audio.wav"
    run_ffmpeg(
        ["-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(audio_path)],
        "audio extraction",
    )
    return audio_path


def run_asr(
    audio: Path,
    out_json: Path,
    asr_python: str,
    model: str,
    glossary: str,
    language: str | None,
) -> dict:
    helper = Path(__file__).resolve().parent / "asr_whisper.py"
    command = [
        asr_python, str(helper), str(audio),
        "--out", str(out_json),
        "--model", model,
        "--initial-prompt", glossary,
    ]
    if language:
        command += ["--language", language]
    logger.info("ASR start: model=%s language=%s", model, language or "auto")
    result = subprocess.run(command, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ASR failed with exit code {result.returncode}")
    with open(out_json, encoding="utf-8") as handle:
        return json.load(handle)


def build_chunk_ranges(duration: float, chunk_minutes: float, overlap_s: float) -> list[tuple[float, float]]:
    if chunk_minutes <= 0:
        return [(0.0, duration)]
    chunk_len = chunk_minutes * 60.0
    step = max(60.0, chunk_len - overlap_s)
    ranges: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - 0.5:
        end = min(start + chunk_len, duration)
        ranges.append((round(start, 2), round(end, 2)))
        if end >= duration:
            break
        start += step
    return ranges


def _frame_token(absolute_s: float) -> str:
    return f"{int(round(absolute_s * 10)):08d}"


def extract_frames(
    video: Path,
    out_dir: Path,
    start_s: float,
    end_s: float,
    fps: float,
    prefix: str,
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(f"{prefix}_*.jpg"):
        stale.unlink()
    duration = max(0.5, end_s - start_s)
    run_ffmpeg(
        [
            "-y", "-ss", f"{start_s:.3f}", "-t", f"{duration:.3f}", "-i", str(video),
            "-vf", f"fps={fps}", "-q:v", "3", str(out_dir / f"{prefix}_%06d.jpg"),
        ],
        f"frames {prefix}",
    )
    frames: list[dict] = []
    for index, path in enumerate(sorted(out_dir.glob(f"{prefix}_*.jpg")), start=1):
        time_s = start_s + (index - 1) / fps
        target = out_dir / f"{prefix}_{_frame_token(time_s)}.jpg"
        if path.name != target.name:
            path.rename(target)
        frames.append({"file": target.name, "time_s": round(time_s, 2)})
    return frames


def build_change_curve(video: Path, start_s: float, end_s: float) -> list[float]:
    import numpy as np

    duration = max(1.0, end_s - start_s)
    result = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-ss", f"{start_s:.3f}", "-t", f"{duration:.3f}",
            "-i", str(video), "-vf", "fps=1,scale=160:90,format=gray",
            "-f", "rawvideo", "-",
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("failed to build change curve")
    frame_size = 90 * 160
    raw = np.frombuffer(result.stdout, dtype=np.uint8)
    count = len(raw) // frame_size
    if count < 2:
        return []
    frames = raw[: count * frame_size].reshape(count, 90, 160).astype(np.int16)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))
    return [float(x) for x in diffs]


def change_windows(
    curve: list[float], start_s: float, threshold: float | None, gap: int
) -> tuple[list[dict], float | None]:
    if not curve:
        return [], None
    import numpy as np

    values = np.asarray(curve, dtype=float)
    if threshold is None:
        threshold = max(6.0, float(np.percentile(values, 85)))
    hot = np.where(values >= threshold)[0]
    windows: list[dict] = []
    if len(hot):
        first = prev = int(hot[0])
        for raw_index in hot[1:]:
            index = int(raw_index)
            if index - prev > gap:
                windows.append(_window_from_indices(first, prev, values, start_s))
                first = index
            prev = index
        windows.append(_window_from_indices(first, prev, values, start_s))
    return windows, threshold


def _window_from_indices(first: int, last: int, values, start_s: float) -> dict:
    return {
        "start_s": round(start_s + first, 2),
        "end_s": round(start_s + last + 1, 2),
        "sources": ["change"],
        "peak": round(float(values[first : last + 1].max()), 2),
    }


def cue_windows(transcript: dict | None, start_s: float, end_s: float, pad: float) -> list[dict]:
    if not transcript:
        return []
    cues = [c.lower() for c in (*CUES_EN, *CUES_RU)]
    windows: list[dict] = []
    for segment in transcript.get("segments", []):
        seg_start = float(segment.get("start", 0.0))
        seg_end = float(segment.get("end", 0.0))
        if seg_end < start_s or seg_start > end_s:
            continue
        text = (segment.get("text") or "").lower()
        if any(cue in text for cue in cues):
            windows.append(
                {
                    "start_s": round(max(start_s, seg_start - pad), 2),
                    "end_s": round(min(end_s, seg_end + pad), 2),
                    "sources": ["cue"],
                    "peak": None,
                }
            )
    return windows


def merge_windows(groups: list[list[dict]], gap: float = 3.0) -> list[dict]:
    merged: list[dict] = []
    for window in sorted([w for group in groups for w in group], key=lambda w: w["start_s"]):
        if merged and window["start_s"] <= merged[-1]["end_s"] + gap:
            current = merged[-1]
            current["end_s"] = max(current["end_s"], window["end_s"])
            current["sources"] = sorted(set(current["sources"]) | set(window["sources"]))
            peaks = [p for p in (current.get("peak"), window.get("peak")) if p is not None]
            current["peak"] = max(peaks) if peaks else None
        else:
            merged.append(dict(window))
    return merged


def split_long_windows(windows: list[dict], max_len: float) -> list[dict]:
    result: list[dict] = []
    for window in windows:
        start = float(window["start_s"])
        end = float(window["end_s"])
        while end - start > max_len:
            result.append({**window, "start_s": start, "end_s": start + max_len})
            start += max_len
        if end > start:
            result.append({**window, "start_s": start, "end_s": end})
    return result


def cap_windows(windows: list[dict], limit: int) -> tuple[list[dict], int]:
    if limit <= 0 or len(windows) <= limit:
        return windows, 0
    ranked = sorted(
        windows,
        key=lambda w: (0 if "cue" in w["sources"] else 1, -(w.get("peak") or 0.0)),
    )
    kept = sorted(ranked[:limit], key=lambda w: w["start_s"])
    return kept, len(windows) - limit


def extract_dense_for_window(
    video: Path,
    out_dir: Path,
    chunk_index: int,
    window_index: int,
    window: dict,
    dense_fps: float,
    curve: list[float],
    curve_start_s: float,
    min_change: float,
    max_gap: float,
) -> dict:
    prefix = f"c{chunk_index:02d}_w{window_index:02d}"
    frames = extract_frames(
        video, out_dir, float(window["start_s"]), float(window["end_s"]), dense_fps, prefix
    )
    kept: list[dict] = []
    last_kept_time = None
    for frame in frames:
        time_s = float(frame["time_s"])
        second = int(math.floor(time_s))
        index = second - int(curve_start_s)
        change = curve[index] if 0 <= index < len(curve) else 0.0
        keep = (
            last_kept_time is None
            or change >= min_change
            or (time_s - last_kept_time) >= max_gap
        )
        if keep:
            last_kept_time = time_s
            kept.append({**frame, "change": round(change, 2)})
        else:
            (out_dir / frame["file"]).unlink()
    return {
        "index": window_index,
        "prefix": prefix,
        "start_s": window["start_s"],
        "end_s": window["end_s"],
        "sources": window["sources"],
        "extracted": len(frames),
        "kept": len(kept),
        "frames": kept,
    }


def cap_frames(report: dict, out_dir: Path, limit: int) -> int:
    if limit <= 0 or report["kept"] <= limit:
        return 0
    step = len(report["frames"]) / limit
    keep_indices = {int(i * step) for i in range(limit)}
    removed = 0
    for index, frame in enumerate(report["frames"]):
        if index not in keep_indices:
            path = out_dir / frame["file"]
            if path.exists():
                path.unlink()
            removed += 1
    report["frames"] = [f for i, f in enumerate(report["frames"]) if i in keep_indices]
    report["kept"] = len(report["frames"])
    return removed


def contact_sheets(frames_dir: Path, out_dir: Path, prefix: str, tile: str = "5x5") -> list[dict]:
    if not list(frames_dir.glob("*.jpg")):
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(f"{prefix}_*.jpg"):
        stale.unlink()
    run_ffmpeg(
        [
            "-y", "-f", "image2", "-pattern_type", "glob",
            "-i", str(frames_dir / "*.jpg"),
            "-vf", f"scale=384:-1,tile={tile}",
            "-vsync", "0", str(out_dir / f"{prefix}_%02d.jpg"),
        ],
        f"contact sheets {prefix}",
    )
    return [{"file": p.name} for p in sorted(out_dir.glob(f"{prefix}_*.jpg"))]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def process_chunk(
    video: Path,
    chunk_dir: Path,
    chunk_index: int,
    start_s: float,
    end_s: float,
    args: argparse.Namespace,
    transcript: dict | None,
) -> dict:
    logger.info("chunk %02d: %.0f-%.0fs", chunk_index, start_s, end_s)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    coarse_dir = chunk_dir / "frames_coarse"
    coarse = extract_frames(video, coarse_dir, start_s, end_s, 1.0 / args.cadence, f"c{chunk_index:02d}f")
    sheets_coarse = contact_sheets(coarse_dir, chunk_dir / "sheets_coarse", f"c{chunk_index:02d}coarse")

    curve = build_change_curve(video, start_s, end_s)
    change_w, effective_threshold = change_windows(curve, start_s, args.diff_threshold, args.diff_gap)
    cue_w = cue_windows(transcript, start_s, end_s, args.cue_pad)
    merged = merge_windows([change_w, cue_w])
    split = split_long_windows(merged, args.max_window_s)
    windows, dropped_by_cap = cap_windows(split, args.max_windows_per_chunk)

    dense_dir = chunk_dir / "frames_dense"
    dense_dir.mkdir(parents=True, exist_ok=True)
    for stale in dense_dir.glob("*.jpg"):
        stale.unlink()
    dense_report: list[dict] = []
    for index, window in enumerate(windows, start=1):
        report = extract_dense_for_window(
            video, dense_dir, chunk_index, index, window, args.dense_fps,
            curve, start_s, args.dense_min_change, args.dense_max_gap,
        )
        dense_report.append(report)

    total_kept = sum(r["kept"] for r in dense_report)
    trimmed = 0
    if args.max_dense_frames_per_chunk and total_kept > args.max_dense_frames_per_chunk:
        per_window = max(1, args.max_dense_frames_per_chunk // max(1, len(dense_report)))
        for report in dense_report:
            trimmed += cap_frames(report, dense_dir, per_window)

    for report in dense_report:
        window_dir = chunk_dir / "_window_tmp"
        window_dir.mkdir(parents=True, exist_ok=True)
        for stale in window_dir.glob("*.jpg"):
            stale.unlink()
        for frame in report["frames"]:
            source = dense_dir / frame["file"]
            if source.exists():
                shutil.copy2(source, window_dir / frame["file"])
        report["sheets"] = contact_sheets(
            window_dir, chunk_dir / "sheets_dense", f"{report['prefix']}", tile="5x5"
        )
    shutil.rmtree(chunk_dir / "_window_tmp", ignore_errors=True)

    transcript_slice = [
        s for s in (transcript or {}).get("segments", [])
        if float(s.get("end", 0)) > start_s and float(s.get("start", 0)) < end_s
    ]
    chunk_meta = {
        "chunk_index": chunk_index,
        "start_s": start_s,
        "end_s": end_s,
        "duration_s": round(end_s - start_s, 2),
        "coarse_frames": len(coarse),
        "coarse_sheets": sheets_coarse,
        "threshold": effective_threshold,
        "change_curve_mean": round(sum(curve) / len(curve), 2) if curve else None,
        "windows": windows,
        "dense": dense_report,
        "dense_frames_total": sum(r["kept"] for r in dense_report),
        "dense_frames_trimmed": trimmed,
        "windows_dropped_by_cap": dropped_by_cap,
        "transcript": transcript_slice,
    }
    write_json(chunk_dir / "chunk_meta.json", chunk_meta)

    logger.info(
        "chunk %02d done: coarse=%d dense=%d (trimmed %d, windows dropped %d)",
        chunk_index, len(coarse), chunk_meta["dense_frames_total"], trimmed, dropped_by_cap,
    )
    return {
        "chunk_index": chunk_index,
        "dir": str(chunk_dir),
        "start_s": start_s,
        "end_s": end_s,
        "coarse_frames": len(coarse),
        "coarse_sheets": len(sheets_coarse),
        "windows": len(windows),
        "dense_frames": chunk_meta["dense_frames_total"],
        "dense_sheets": sum(len(r.get("sheets", [])) for r in dense_report),
    }


def find_chunk_segment_files(out_dir: Path) -> list[Path]:
    return sorted((out_dir / "chunks").glob("chunk_*/segments.json"))


def combine_chunks(out_dir: Path, overlap_s: float) -> dict:
    files = find_chunk_segment_files(out_dir)
    if not files:
        raise SystemExit(f"no chunk segments.json found under {out_dir / 'chunks'}")
    segments: list[dict] = []
    metadata: dict = {}
    for path in files:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        metadata = metadata or payload.get("video_metadata", {})
        segments.extend(payload.get("segments", []))
    segments.sort(key=lambda s: float(s.get("timestamp_seconds", 0)))
    deduped: list[dict] = []
    for segment in segments:
        duplicate = None
        for existing in reversed(deduped[-6:]):
            same_topic = existing.get("topic_id") == segment.get("topic_id")
            close_in_time = abs(
                float(existing.get("timestamp_seconds", 0)) - float(segment.get("timestamp_seconds", 0))
            ) <= overlap_s
            if same_topic and close_in_time:
                duplicate = existing
                break
        if duplicate is None:
            deduped.append(segment)
            continue
        if len(json.dumps(segment, ensure_ascii=False)) > len(json.dumps(duplicate, ensure_ascii=False)):
            deduped[deduped.index(duplicate)] = segment
    payload = {
        "video_metadata": {**metadata, "chunks_combined": len(files), "segments": len(deduped)},
        "segments": deduped,
    }
    write_json(out_dir / "segments.json", payload)
    logger.info("combine: %d chunk files -> %d segments", len(files), len(deduped))
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Video ingest stage 1 (no DB, no LLM)")
    parser.add_argument("--video", required=False, help="video file (native resolution source)")
    parser.add_argument("--audio", default=None, help="audio file; extracted from video if omitted")
    parser.add_argument("--out", default=None, help="output directory (default output/video_ingest/<id>)")
    parser.add_argument("--video-id", default=None, help="identifier for the output directory")
    parser.add_argument("--cadence", type=float, default=5.0, help="coarse frame grid, seconds")
    parser.add_argument("--dense-fps", type=float, default=1.0, help="dense sampling rate for hot windows")
    parser.add_argument("--diff-threshold", type=float, default=None, help="change threshold (default p85)")
    parser.add_argument("--diff-gap", type=int, default=3, help="merge gap for change windows, seconds")
    parser.add_argument("--cue-pad", type=float, default=10.0, help="padding around speech cues, seconds")
    parser.add_argument("--dense-min-change", type=float, default=4.0, help="keep dense frame if change >= this")
    parser.add_argument("--dense-max-gap", type=float, default=18.0, help="keep a frame at least every N seconds")
    parser.add_argument("--asr-python", default="python3.11", help="interpreter with faster_whisper")
    parser.add_argument("--asr-model", default=DEFAULT_ASR_MODEL)
    parser.add_argument("--glossary", default=DEFAULT_GLOSSARY, help="ASR biasing prompt")
    parser.add_argument("--language", default=None, help="force ASR language (default auto-detect)")
    parser.add_argument("--skip-asr", action="store_true")
    parser.add_argument("--transcript", default=None, help="existing transcript JSON to reuse")
    parser.add_argument("--chunk-minutes", type=float, default=0.0, help="chunk size, 0 disables chunking")
    parser.add_argument("--chunk-overlap-s", type=float, default=25.0, help="overlap between chunks, seconds")
    parser.add_argument("--max-window-s", type=float, default=90.0, help="split long windows into chunks")
    parser.add_argument("--max-windows-per-chunk", type=int, default=8)
    parser.add_argument("--max-dense-frames-per-chunk", type=int, default=60)
    parser.add_argument("--combine", action="store_true", help="merge chunks/*/segments.json into segments.json")
    return parser.parse_args()


def resolve_out_dir(args: argparse.Namespace, video: Path | None) -> Path:
    if args.out:
        return Path(args.out).expanduser().resolve()
    video_id = args.video_id or (video.stem if video else "video")
    return (BACKEND_DIR.parent / "output" / "video_ingest" / video_id).resolve()


def main() -> None:
    args = parse_args()

    if args.combine:
        out_dir = resolve_out_dir(args, None)
        payload = combine_chunks(out_dir, args.chunk_overlap_s)
        print(f"combined segments: {len(payload['segments'])} -> {out_dir / 'segments.json'}")
        return

    if not args.video:
        raise SystemExit("--video is required unless --combine is used")
    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        raise SystemExit(f"video not found: {video}")

    out_dir = resolve_out_dir(args, video)
    out_dir.mkdir(parents=True, exist_ok=True)
    video_id = args.video_id or video.stem
    logger.info("ingest: %s -> %s", video.name, out_dir)
    logger.info(
        "mode: %s",
        f"chunked ({args.chunk_minutes} min, overlap {args.chunk_overlap_s}s)"
        if args.chunk_minutes > 0
        else "single pass",
    )

    media = probe_media(video)
    logger.info(
        "media: %.1fs | %sx%s @%s | audio=%s",
        media["duration_s"],
        (media["video"] or {}).get("width"),
        (media["video"] or {}).get("height"),
        (media["video"] or {}).get("fps"),
        bool(media["audio"]),
    )

    if args.audio is None and not media["audio"]:
        raise SystemExit(
            "video has no audio stream; pass --audio <file> (video-only downloads need a separate audio track)"
        )
    audio_path = ensure_audio(video, out_dir, Path(args.audio).resolve() if args.audio else None)

    transcript: dict | None = None
    if args.transcript:
        with open(Path(args.transcript).expanduser().resolve(), encoding="utf-8") as handle:
            transcript = json.load(handle)
        logger.info("transcript reused: %s", args.transcript)
    elif not args.skip_asr:
        asr_python = shutil.which(args.asr_python)
        if not asr_python:
            raise SystemExit(
                f"ASR interpreter not found: {args.asr_python} (pass --asr-python or --skip-asr)"
            )
        transcript = run_asr(
            audio_path, out_dir / "transcript.json", asr_python,
            args.asr_model, args.glossary, args.language,
        )
    if transcript is not None:
        write_json(out_dir / "transcript.json", transcript)
        logger.info(
            "transcript: %d segments, language=%s",
            transcript.get("segments_count", len(transcript.get("segments", []))),
            transcript.get("language"),
        )

    write_json(
        out_dir / "meta.json",
        {
            "video_id": video_id,
            "source": str(video),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "media": media,
            "audio_path": str(audio_path),
            "transcript": bool(transcript),
            "chunking": {
                "chunk_minutes": args.chunk_minutes,
                "chunk_overlap_s": args.chunk_overlap_s,
                "max_windows_per_chunk": args.max_windows_per_chunk,
                "max_dense_frames_per_chunk": args.max_dense_frames_per_chunk,
                "cadence_s": args.cadence,
                "dense_fps": args.dense_fps,
            },
        },
    )

    ranges = build_chunk_ranges(media["duration_s"], args.chunk_minutes, args.chunk_overlap_s)
    chunks_root = out_dir / "chunks"
    chunks_root.mkdir(parents=True, exist_ok=True)
    reports = []
    for index, (start_s, end_s) in enumerate(ranges, start=1):
        chunk_dir = chunks_root / f"chunk_{index:02d}"
        if args.chunk_minutes <= 0:
            chunk_dir = out_dir
        reports.append(process_chunk(video, chunk_dir, index, start_s, end_s, args, transcript))

    write_json(
        out_dir / "chunks_index.json",
        {
            "duration_s": media["duration_s"],
            "chunking": {"chunk_minutes": args.chunk_minutes, "chunk_overlap_s": args.chunk_overlap_s},
            "chunks": reports,
            "totals": {
                "coarse_frames": sum(r["coarse_frames"] for r in reports),
                "dense_frames": sum(r["dense_frames"] for r in reports),
                "windows": sum(r["windows"] for r in reports),
            },
        },
    )

    print()
    print("=" * 64)
    print(f"video:        {video_id} ({media['duration_s']}s)")
    print(f"transcript:   {'yes' if transcript else 'no'}")
    print(f"chunks:       {len(reports)}")
    print(f"coarse:       {sum(r['coarse_frames'] for r in reports)} frames, "
          f"{sum(r['coarse_sheets'] for r in reports)} sheets")
    print(f"windows:      {sum(r['windows'] for r in reports)}")
    print(f"dense frames: {sum(r['dense_frames'] for r in reports)} kept")
    print(f"output:       {out_dir}")
    print("=" * 64)


if __name__ == "__main__":
    main()

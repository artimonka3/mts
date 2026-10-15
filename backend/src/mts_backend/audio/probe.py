"""Bounded decoder calls; no file extension or client MIME trust."""

import asyncio
import json
import shutil
from pathlib import Path

from mts_backend.core.business import BusinessError


async def probe(path, settings):
    if not shutil.which("ffprobe"):
        raise BusinessError(503, "decoder_unavailable", "Audio decoder is not installed.")
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-show_entries",
        "format=duration,format_name:stream=codec_type,channels",
        "-of",
        "json",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), settings.decoder_timeout_seconds)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise BusinessError(422, "decoder_timeout", "Audio decoder timed out.") from None
    try:
        meta = json.loads(stdout)
        streams = [s for s in meta["streams"] if s["codec_type"] == "audio"]
        duration = float(meta["format"]["duration"])
        if process.returncode or not streams or duration <= 0:
            raise ValueError
        if duration > settings.audio_max_seconds:
            raise BusinessError(422, "audio_too_long", "Audio exceeds maximum duration.")
        formats = meta["format"]["format_name"].split(",")
        allowed = {
            "wav",
            "mp3",
            "ogg",
            "flac",
            "matroska",
            "webm",
            "mov",
            "mp4",
            "m4a",
            "aac",
            "mpegts",
        }
        if not set(formats) & allowed:
            raise BusinessError(415, "unsupported_media_type", "Audio format is not supported.")
        mime = (
            "audio/wav"
            if "wav" in formats
            else "audio/mpeg"
            if "mp3" in formats
            else "audio/ogg"
            if "ogg" in formats
            else "audio/webm"
            if "webm" in formats
            else "audio/mp4"
        )
        return {
            "duration_ms": round(duration * 1000),
            "channels": streams[0].get("channels"),
            "mime": mime,
        }
    except (ValueError, KeyError, IndexError, TypeError):
        raise BusinessError(422, "invalid_audio", "Audio cannot be decoded.") from None


async def prepare(path, target, settings):
    if not shutil.which("ffmpeg"):
        raise BusinessError(503, "decoder_unavailable", "Audio decoder is not installed.")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        str(path),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        "-f",
        "wav",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await asyncio.wait_for(process.wait(), settings.decoder_timeout_seconds)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise BusinessError(422, "decoder_timeout", "Audio decoder timed out.") from None
    if process.returncode:
        raise BusinessError(422, "invalid_audio", "Audio cannot be decoded.")
    # Only classify near-zero signal, not speech detection. VAD remains unavailable.
    import array
    import wave

    with wave.open(str(target), "rb") as wav:
        samples = array.array("h", wav.readframes(wav.getnframes()))
    if not samples or max(abs(x) for x in samples) < 16:
        raise BusinessError(422, "silent_audio", "Audio contains near-zero signal.")
    return Path(target).read_bytes()

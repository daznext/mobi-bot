from __future__ import annotations

import asyncio
import shutil
import subprocess
import zipfile
from pathlib import Path


class ConversionError(RuntimeError):
    pass


SUPPORTED_EXTENSIONS = (".fb2", ".fb2.zip", ".epub", ".zip")


def is_supported_book(filename: str) -> bool:
    lowered = filename.lower()
    return any(lowered.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def mobi_name(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".fb2.zip"):
        return filename[:-8] + ".mobi"
    if lowered.endswith(".zip"):
        return filename[:-4] + ".mobi"
    return str(Path(filename).with_suffix(".mobi").name)


def prepare_source(source: Path, work_dir: Path) -> Path:
    if source.name.lower().endswith(".zip"):
        return _extract_fb2_from_zip(source, work_dir)
    return source


def _extract_fb2_from_zip(source: Path, work_dir: Path) -> Path:
    extract_dir = work_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(source) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir() and Path(info.filename).name.lower().endswith(".fb2")
            ]
            if not candidates:
                raise ConversionError("ZIP archive does not contain an FB2 file.")

            candidates.sort(key=lambda item: item.file_size, reverse=True)
            selected = candidates[0]
            target = extract_dir / Path(selected.filename).name

            with archive.open(selected) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile as exc:
        raise ConversionError("Invalid ZIP archive.") from exc

    return target


async def convert_to_mobi(
    ebook_convert_bin: str,
    source: Path,
    destination: Path,
    timeout_seconds: int = 300,
) -> None:
    converter = shutil.which(ebook_convert_bin) if "/" not in ebook_convert_bin else ebook_convert_bin
    if not converter:
        raise ConversionError("ebook-convert was not found. Install Calibre or set EBOOK_CONVERT_BIN.")

    destination.parent.mkdir(parents=True, exist_ok=True)

    process = await asyncio.create_subprocess_exec(
        converter,
        str(source),
        str(destination),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise ConversionError("Conversion timed out.") from exc

    if process.returncode != 0 or not destination.exists():
        details = (stderr or stdout).decode("utf-8", errors="replace").strip()
        if len(details) > 1000:
            details = details[-1000:]
        raise ConversionError(f"Conversion failed: {details or 'unknown error'}")

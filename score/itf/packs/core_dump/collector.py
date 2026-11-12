"""Explicit, repeatable core-dump collection independent of the test runner."""

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path

from .extract import Command, Transfer, extract_core_dumps

logger = logging.getLogger(__name__)


class CoreDumpCollector:
    def __init__(self, command: Command, files: Transfer):
        self._command = command
        self._files = files
        self._collected: dict[str, str] = {}

    def collect(self, output_dir: str) -> list[str]:
        """Copy new or changed dumps, returning their local paths without removing remote files."""
        output = Path(output_dir).resolve()
        collected = []
        with tempfile.TemporaryDirectory(prefix="itf-core-dumps-") as staging:
            for downloaded in extract_core_dumps(self._command, self._files, staging):
                source = Path(downloaded)
                relative = source.relative_to(staging)
                destination = output / relative
                if not destination.resolve().is_relative_to(output):
                    logger.warning("Skipping output path escaping the collection directory: %s", destination)
                    continue
                try:
                    digest = hashlib.sha256()
                    with source.open(mode="rb") as content:
                        for chunk in iter(lambda: content.read(65536), b""):
                            digest.update(chunk)
                    fingerprint = digest.hexdigest()
                    key = relative.as_posix()
                    if self._collected.get(key) == fingerprint:
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source), str(destination))
                    self._collected[key] = fingerprint
                    collected.append(str(destination))
                except OSError:
                    logger.warning("Failed to store core dump %s", relative, exc_info=True)
        return collected

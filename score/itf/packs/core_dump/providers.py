"""Core-dump collection composed from command and file-transfer slots."""

from score.itf.core import capability

from .collector import CoreDumpCollector
from .extract import Command, Transfer


@capability("diagnostics.core_dump", label="collector")
def make_collector(command: Command, files: Transfer) -> CoreDumpCollector:
    return CoreDumpCollector(command, files)

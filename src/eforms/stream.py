"""Stream-parse a TED ZIP archive, yielding Notice objects."""
from __future__ import annotations

import logging
import zipfile
from collections.abc import Iterator
from pathlib import Path

from .models import Notice
from .parser import parse

logger = logging.getLogger(__name__)


def stream_notices(zip_path: str | Path) -> Iterator[Notice]:
    """Open a TED monthly/daily ZIP and yield parsed Notices."""
    with zipfile.ZipFile(zip_path) as zf:
        xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
        logger.info("ZIP contains %d XML files", len(xml_names))

        for name in xml_names:
            try:
                data = zf.read(name)
                yield parse(data)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to parse %s: %s", name, exc)
                continue

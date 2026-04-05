"""Stream-parse TED archives, yielding Notice objects.

TED packages come in two formats:
  - Monthly: .tar.gz containing daily .tar.gz files, each containing XML
  - Daily:   .tar.gz containing a directory of XML files
  - Legacy:  .zip containing XML files (for manually prepared archives)
"""
from __future__ import annotations

import io
import logging
import os
import tarfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from .models import Notice
from .parser import parse

logger = logging.getLogger(__name__)

_PARSE_ERROR_MSG = "Failed to parse %s: %s"


def stream_notices(archive_path: str | Path) -> Iterator[Notice]:
    """Open a TED archive and yield parsed Notices.

    Auto-detects the archive format (monthly tar.gz, daily tar.gz, or zip).
    """
    path = Path(archive_path)
    name = path.name.lower()

    if name.endswith(".zip"):
        yield from _stream_zip(path)
    elif name.endswith((".tar.gz", ".tgz", ".tar")):
        yield from _stream_tar(path)
    else:
        # Try tar first (monthly packages have no extension sometimes)
        try:
            yield from _stream_tar(path)
        except tarfile.TarError:
            yield from _stream_zip(path)


def stream_xml_dir(directory: str | Path) -> Iterator[Notice]:
    """Parse all XML files in a directory (for extracted packages)."""
    xml_dir = Path(directory)
    xml_files = sorted(xml_dir.rglob("*.xml"))
    logger.info("Directory contains %d XML files", len(xml_files))
    for path in xml_files:
        try:
            yield parse(path.read_bytes())
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning(_PARSE_ERROR_MSG, path.name, exc)


def _stream_tar(path: Path) -> Iterator[Notice]:
    """Stream from a tar.gz — handles both monthly and daily formats."""
    with tarfile.open(path, "r:*") as tf:
        for member in tf.getmembers():
            if member.name.endswith(".xml"):
                # Daily package: XML files directly
                try:
                    f = tf.extractfile(member)
                    if f is None:
                        continue
                    yield parse(f.read())
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.warning(_PARSE_ERROR_MSG, member.name, exc)
            elif member.name.endswith((".tar.gz", ".tgz")):
                # Monthly package: nested daily tar.gz files
                logger.info("Opening nested daily package: %s", member.name)
                f = tf.extractfile(member)
                if f is None:
                    continue
                yield from _stream_nested_tar(f, member.name)


def _stream_nested_tar(
    fileobj: io.BufferedReader, name: str,
) -> Iterator[Notice]:
    """Stream XML from a nested tar.gz within a monthly package."""
    try:
        with tarfile.open(fileobj=fileobj, mode="r:gz") as inner:
            for member in inner.getmembers():
                if not member.name.endswith(".xml"):
                    continue
                try:
                    f = inner.extractfile(member)
                    if f is None:
                        continue
                    yield parse(f.read())
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.warning(
                        "Failed to parse %s/%s: %s",
                        name, member.name, exc,
                    )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to open nested archive %s: %s", name, exc)


def _stream_zip(path: Path) -> Iterator[Notice]:
    """Stream from a ZIP archive (legacy or manually prepared)."""
    with zipfile.ZipFile(path) as zf:
        xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
        logger.info("ZIP contains %d XML files", len(xml_names))
        for name in xml_names:
            try:
                yield parse(zf.read(name))
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.warning(_PARSE_ERROR_MSG, name, exc)

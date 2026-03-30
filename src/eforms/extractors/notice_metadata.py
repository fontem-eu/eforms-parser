"""Extract top-level notice metadata (ID, type, dates)."""
from __future__ import annotations

from lxml import etree

from ..namespaces import NS


def extract_notice_id(root: etree._Element) -> str | None:
    """Extract BT-701 Notice Identifier (cbc:ID at root level)."""
    el = root.find("cbc:ID", NS)
    return el.text.strip() if el is not None and el.text else None


def extract_issue_date(root: etree._Element) -> str | None:
    """Extract notice issue date."""
    el = root.find("cbc:IssueDate", NS)
    return el.text.strip() if el is not None and el.text else None


def extract_notice_type(root: etree._Element) -> str | None:
    """Extract the notice sub-type code."""
    el = root.find(
        ".//cbc:NoticeTypeCode", NS
    )
    return el.text.strip() if el is not None and el.text else None

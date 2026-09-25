"""Extract procedure-level fields (title, CPV, description, procedure type)."""
from __future__ import annotations

from lxml import etree

from ..languages import to_iso639_1
from .notice_metadata import extract_notice_language
from ..namespaces import NS


def extract_title(root: etree._Element) -> str | None:
    """Extract the main procurement project title."""
    el = root.find(".//cac:ProcurementProject/cbc:Name", NS)
    return el.text.strip() if el is not None and el.text else None


def extract_title_language(root: etree._Element) -> str | None:
    """ISO 639-1 language of the title :func:`extract_title` returns.

    Read from that element's own ``languageID``: the language of the text,
    which on a multilingual notice need not be the notice's. Falls back to
    ``cbc:NoticeLanguageCode``; None when the title is absent or neither
    code is recognisable.
    """
    el = root.find(".//cac:ProcurementProject/cbc:Name", NS)
    if el is None or not el.text or not el.text.strip():
        return None
    return (to_iso639_1(el.get("languageID"))
            or to_iso639_1(extract_notice_language(root)))


def extract_description(root: etree._Element) -> str | None:
    """Extract the main procurement project description."""
    el = root.find(".//cac:ProcurementProject/cbc:Description", NS)
    if el is not None and el.text:
        text = el.text.strip()
        return text[:500] if len(text) > 500 else text
    return None


def extract_cpv_main(root: etree._Element) -> str | None:
    """Extract the main CPV code."""
    el = root.find(
        ".//cac:ProcurementProject/cac:MainCommodityClassification/"
        "cbc:ItemClassificationCode[@listName='cpv']",
        NS,
    )
    return el.text.strip() if el is not None and el.text else None


def extract_procedure_type(root: etree._Element) -> str | None:
    """Extract the procedure type code."""
    el = root.find(
        ".//cac:TenderingProcess/"
        "cbc:ProcedureCode[@listName='procurement-procedure-type']",
        NS,
    )
    return el.text.strip() if el is not None and el.text else None

def extract_nuts(root: etree._Element) -> str | None:
    """Extract the place-of-performance NUTS code.

    eForms puts the location under ``ProcurementProject/RealizedLocation``.
    Some notices repeat the same NUTS on every lot; if the procurement-
    project location isn't set we fall back to the first lot's location.
    A regional-only notice can carry only the country half — treat those
    as no NUTS and let the country column handle it.
    """
    for xpath in (
        ".//cac:ProcurementProject/cac:RealizedLocation"
        "/cac:Address/cbc:CountrySubentityCode[@listName='nuts']",
        ".//cac:ProcurementProjectLot/cac:ProcurementProject"
        "/cac:RealizedLocation/cac:Address"
        "/cbc:CountrySubentityCode[@listName='nuts']",
    ):
        el = root.find(xpath, NS)
        if el is not None and el.text and el.text.strip():
            return el.text.strip()
    return None

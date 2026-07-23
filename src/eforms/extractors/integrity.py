"""Tender-integrity extractors — inputs to the Single Market Scoreboard /
DIGIWHIST CRI red flags (award criteria, submission deadline, framework,
EU funding). All return None when the element is absent so older or
sparse notices degrade gracefully."""
from __future__ import annotations

from lxml import etree

from ..namespaces import NS


def extract_award_criterion_type(root: etree._Element) -> str | None:
    """Summarise the award criteria as ``price`` (lowest-price only) or
    ``meat`` (most-economically-advantageous — any quality/cost criterion).
    """
    codes = {
        el.text.strip().lower()
        for el in root.findall(
            ".//cac:AwardingTerms/cac:AwardingCriterion/"
            "cac:SubordinateAwardingCriterion/"
            "cbc:AwardingCriterionTypeCode[@listName='award-criterion-type']",
            NS,
        )
        if el is not None and el.text
    }
    if not codes:
        return None
    return "price" if codes == {"price"} else "meat"


def extract_submission_deadline(root: etree._Element) -> str | None:
    """Tender submission cut-off date (the bidding window close)."""
    el = root.find(
        ".//cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndDate",
        NS,
    )
    return el.text.strip()[:10] if el is not None and el.text else None


def extract_is_framework(root: etree._Element) -> bool | None:
    """True when the procedure sets up a framework agreement, False when it
    explicitly doesn't, None when not stated."""
    el = root.find(
        ".//cac:TenderingProcess/cac:ContractingSystem/"
        "cbc:ContractingSystemTypeCode[@listName='framework-agreement']",
        NS,
    )
    if el is None or not el.text:
        return None
    return el.text.strip().lower().startswith("fa")


def extract_eu_funding(root: etree._Element) -> tuple[bool | None, str | None]:
    """(eu_funded, funding_programme) from any declared EU co-financing."""
    el = root.find(".//efac:Funding/cbc:FundingProgramCode", NS)
    if el is None or not el.text:
        # No funding block at all → unknown, not "definitely not EU funded".
        return None, None
    programme = el.text.strip()
    return True, programme

"""Every lot total a notice publishes, not only the first.

Buyers type money, reference numbers and placeholders into the
received-tenders field: 2,416,436 on 148462-2026, 800,000 on 541842-2024,
999 on about 1,500 notices (fontem-prod, 2026-10-01). Some publish a sane
total beside the bad one, and a cleaning stage can only fall back to it
if the parser hands it over. ``tenders_received`` is unchanged: it is
still the first total, chosen as before.

The fixtures are unmodified TED downloads.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from eforms.extractors.awards import (
    extract_lot_submission_totals, extract_lot_tender_counts,
)
from eforms.parser import parse

_FIXTURES = Path(__file__).parent / "fixtures"

_NS = (
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" '
    'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" '
    'xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1" '
    'xmlns:efbc="http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1" '
    'xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1"'
)


def _lot(*stats: tuple[str, str]) -> etree._Element:
    body = "".join(
        '<efac:ReceivedSubmissionsStatistics>'
        f'<efbc:StatisticsCode listName="received-submission-type">{code}</efbc:StatisticsCode>'
        f'<efbc:StatisticsNumeric>{num}</efbc:StatisticsNumeric>'
        '</efac:ReceivedSubmissionsStatistics>'
        for code, num in stats)
    return etree.fromstring(
        f'<ContractAwardNotice {_NS}><ext:UBLExtensions><ext:UBLExtension>'
        '<ext:ExtensionContent><efext:EformsExtension><efac:NoticeResult>'
        f'<efac:LotResult><efac:TenderLot><cbc:ID>LOT-0001</cbc:ID></efac:TenderLot>{body}'
        '</efac:LotResult></efac:NoticeResult></efext:EformsExtension>'
        '</ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>'
        '</ContractAwardNotice>'.encode())


def test_plain_totals_come_before_electronic_ones():
    root = _lot(("t-esubm", "1"), ("tenders", "67494"), ("t-sme", "1"))
    assert extract_lot_submission_totals(root) == {"LOT-0001": (67494, 1)}
    # The count itself is chosen exactly as before.
    assert extract_lot_tender_counts(root) == {"LOT-0001": 67494}


def test_a_repeated_code_keeps_every_value_in_document_order():
    root = _lot(("t-esubm", "325350"), ("t-sme", "0"), ("t-esubm", "3"))
    assert extract_lot_submission_totals(root) == {"LOT-0001": (325350, 3)}


def test_subgroups_and_zeros_are_never_totals():
    root = _lot(("t-sme", "2"), ("tenders", "0"), ("t-micro", "1"))
    assert not extract_lot_submission_totals(root)
    assert not extract_lot_tender_counts(root)


def test_a_notice_hands_the_second_total_to_its_award():
    # 154038-2026 (FRA): t-esubm 325350, then t-esubm 3 on the same lot.
    notice = parse((_FIXTURES / "eforms_can_two_esubm_totals_fr_154038-2026.xml").read_bytes())
    awards = [a for a in notice.awards if a.lot_id == "LOT-0001"]
    assert awards
    for award in awards:
        assert award.tenders_received == 325350
        assert award.submission_totals == (325350, 3)


def test_a_contradicted_total_arrives_with_its_contradiction():
    # 776313-2025 (SVN): "tenders" 67494 on LOT-0001 while its own
    # t-esubm is 1; the other lots publish 1 throughout.
    notice = parse((_FIXTURES / "eforms_can_count_contradicted_si_776313-2025.xml").read_bytes())
    totals = {a.lot_id: a.submission_totals for a in notice.awards}
    assert totals["LOT-0001"] == (67494, 1)
    assert totals["LOT-0002"] == (1, 1)


def test_legacy_dialect_carries_its_one_figure():
    notice = parse((_FIXTURES / "ted_export_r207_award_oldgen_179996-2013.xml").read_bytes())
    for award in notice.awards:
        expected = (award.tenders_received,) if award.tenders_received else ()
        assert award.submission_totals == expected

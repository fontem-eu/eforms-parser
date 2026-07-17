"""Award extraction across the one-to-MANY edges of the eForms result chain.

Both `LotResult → LotTender` and `TenderingParty → Tenderer` are
one-to-many in real notices, and taking only the first match of each
(the historical bug) silently dropped most named suppliers: measured
across 55 real CANs, 162 awards were recorded where 474 named selected
suppliers existed.

Every fixture here is an unmodified notice downloaded from ted.europa.eu.
The expected counts below were computed from the fixtures themselves, not
assumed.
"""
from collections import Counter
from pathlib import Path

from eforms.parser import parse

_FIXTURES = Path(__file__).parent / "fixtures"

# A Romanian multi-supplier framework: 21 LotResults reference 272
# LotTenders between them (RES-0005 alone references 11), every LotResult
# is `selec-w`, and the tenders are ranked 1..3 in a cascade.
_FRAMEWORK = _FIXTURES / "eforms_can_framework_multi_supplier_324249-2024.xml"

# An Italian CAN whose TPA-0002 is a 3-member consortium of joint bidders.
_CONSORTIUM = _FIXTURES / "eforms_can_consortium_3_tenderers_324264-2024.xml"

# A Hungarian CAN: 23 LotResults referencing 62 LotTenders, one of which
# closed with no winner (`clos-nw`).
_MANY_TENDERS = _FIXTURES / "eforms_can_many_tenders_few_named_324192-2024.xml"


def _parse(path: Path):
    return parse(path.read_bytes())


# ── Multi-supplier framework: LotResult → MANY LotTenders ─────────────────


def test_framework_emits_an_award_per_referenced_lot_tender():
    """All 272 referenced LotTenders become awards, not just 21 (one per
    LotResult, which is what keeping only the first reference produced)."""
    notice = _parse(_FRAMEWORK)
    assert len(notice.awards) == 272


def test_framework_single_lot_result_yields_all_eleven_tenders():
    """RES-0005 references 11 LotTenders; it is the only LotResult for
    LOT-0005, so the lot must carry all 11 awards rather than 1."""
    notice = _parse(_FRAMEWORK)
    lot_awards = [a for a in notice.awards if a.lot_id == "LOT-0005"]
    assert len(lot_awards) == 11


def test_framework_recovers_every_named_supplier():
    """14 distinct suppliers are named; the first-reference-only path
    surfaced only 11 of them."""
    notice = _parse(_FRAMEWORK)
    assert len({a.contractor_org_id for a in notice.awards}) == 14


def test_framework_carries_cascade_rank():
    """`cbc:RankCode` on the LotTender becomes Award.rank (an int)."""
    notice = _parse(_FRAMEWORK)
    assert Counter(a.rank for a in notice.awards) == {1: 230, 2: 26, 3: 16}


def test_framework_lot_results_are_all_winners():
    """Every LotResult here is `selec-w`."""
    notice = _parse(_FRAMEWORK)
    assert all(a.is_winner for a in notice.awards)


# ── Consortium: TenderingParty → MANY Tenderers ───────────────────────────


def test_consortium_all_three_members_are_extracted():
    """TPA-0002's three joint bidders all appear — keeping only the first
    Tenderer stored BRUNO SRL alone and vanished the other two."""
    notice = _parse(_CONSORTIUM)
    members = [a for a in notice.awards if a.tendering_party_id == "TPA-0002"]
    assert len(members) == 3
    assert {a.contractor_org_id for a in members} == {
        "ORG-0004", "ORG-0005", "ORG-0006",
    }
    assert {notice.organizations[a.contractor_org_id].name for a in members} == {
        "BRUNO SRL",
        "CO. E SE - COSTRUZIONI E SERVIZI - S.R.L.",
        "ZECCHINI GROUP S.R.L.",
    }


def test_consortium_members_share_the_full_undivided_value():
    """TED publishes no per-member split, so each member carries the FULL
    tender value and is flagged so consumers can deduplicate."""
    notice = _parse(_CONSORTIUM)
    members = [a for a in notice.awards if a.tendering_party_id == "TPA-0002"]
    assert all(a.value == 1947708.0 for a in members)
    assert all(a.currency == "EUR" for a in members)
    assert all(a.is_consortium_member for a in members)
    assert all(a.lot_id == "LOT-0003" for a in members)


def test_consortium_value_is_countable_once_via_tendering_party():
    """The flag + tendering_party_id let a consumer avoid booking the same
    money three times: naive summation would treble this lot to 5.8M."""
    notice = _parse(_CONSORTIUM)
    naive_total = sum(a.value for a in notice.awards if a.lot_id == "LOT-0003")
    deduplicated = {
        (a.tendering_party_id, a.lot_id): a.value
        for a in notice.awards
        if a.lot_id == "LOT-0003"
    }
    assert naive_total == 5843124.0          # 3 x the real price — wrong
    assert sum(deduplicated.values()) == 1947708.0


def test_consortium_sole_bidders_are_not_flagged_as_members():
    """Single-Tenderer parties keep is_consortium_member False, so the flag
    stays a reliable deduplication signal."""
    notice = _parse(_CONSORTIUM)
    solo = [a for a in notice.awards if a.tendering_party_id != "TPA-0002"]
    assert len(solo) == 3
    assert not any(a.is_consortium_member for a in solo)


def test_consortium_notice_total_award_count():
    """4 LotResults, one of which is a 3-member consortium → 6 awards
    (was 4 when only the first Tenderer survived)."""
    assert len(_parse(_CONSORTIUM).awards) == 6


# ── Never invent bidders TED did not name ────────────────────────────────


def test_many_tenders_extracts_only_named_suppliers():
    """62 LotTenders are referenced across 23 LotResults, and every award
    resolves to an organisation the notice actually names. We surface what
    TED published — never a placeholder for an unnamed bidder."""
    notice = _parse(_MANY_TENDERS)
    assert len(notice.awards) == 62
    assert all(a.contractor_org_id in notice.organizations for a in notice.awards)
    assert all(notice.organizations[a.contractor_org_id].name
               for a in notice.awards)


def test_many_tenders_never_exceeds_the_reported_bidder_count():
    """TED does not publish losing bidders. This notice has no consortia,
    so awards per lot must never outnumber the tenders received for it —
    fabricating a bidder to close the gap would break this."""
    notice = _parse(_MANY_TENDERS)
    per_lot = Counter(a.lot_id for a in notice.awards)
    received = {a.lot_id: a.tenders_received for a in notice.awards}
    assert per_lot
    assert all(per_lot[lot] <= received[lot] for lot in per_lot)


def test_many_tenders_marks_the_no_winner_result():
    """The single `clos-nw` LotResult yields an award flagged is_winner
    False; the other 61 are selected winners."""
    notice = _parse(_MANY_TENDERS)
    non_winners = [a for a in notice.awards if not a.is_winner]
    assert len(non_winners) == 1
    assert non_winners[0].lot_id == "LOT-0006"
    assert non_winners[0].contractor_org_id == "ORG-0016"

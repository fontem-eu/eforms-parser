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


# ── Winners come from SettledContract refs, not the LotResult code ────────
#
# Hungarian (EKR) and Swedish eSender notices attach EVERY received tender
# to the `selec-w` LotResult; only the SettledContract→LotTender reference
# identifies which tender actually won. Treating the LotResult code as the
# winner flag marks named LOSING bidders as winners and their bid amounts
# as award values.


def test_hungarian_losing_bidder_is_not_a_winner():
    """LOT-0001's LotResult references TEN-5913 AND TEN-6121, but its
    SettledContract (CON-0001) references only TEN-6121. TEN-5913
    (Ecogarden) is a named LOSER and must not be flagged as a winner."""
    notice = _parse(_MANY_TENDERS)
    lot = {a.contractor_org_id: a for a in notice.awards if a.lot_id == "LOT-0001"}
    loser = lot["ORG-0004"]   # TEN-5913
    winner = lot["ORG-0005"]  # TEN-6121
    assert notice.organizations["ORG-0004"].name.startswith("Ecogarden")
    assert notice.organizations["ORG-0005"].name.startswith("Nemes Bau Plusz")
    assert not loser.is_winner
    assert winner.is_winner


def test_hungarian_winner_count_matches_settled_contract_refs():
    """22 tenders are referenced by SettledContracts, so exactly 22 of the
    62 awards are winners; the other 40 are named losing bidders."""
    notice = _parse(_MANY_TENDERS)
    winners = [a for a in notice.awards if a.is_winner]
    assert len(winners) == 22
    assert len(notice.awards) - len(winners) == 40


def test_hungarian_losers_keep_their_bid_but_not_the_contract_dates():
    """A loser's `value` is its BID amount (kept — named losing bidders are
    the point), but the SettledContract dates belong only to the tender the
    contract actually references, never to a loser."""
    notice = _parse(_MANY_TENDERS)
    losers = [a for a in notice.awards if not a.is_winner]
    assert all(a.award_date is None for a in losers)
    assert all(a.conclusion_date is None for a in losers)
    ecogarden = next(a for a in losers
                     if a.lot_id == "LOT-0001" and a.contractor_org_id == "ORG-0004")
    assert ecogarden.value == 4930000.0  # bid amount, NOT an award value
    dated_winners = [a for a in notice.awards if a.is_winner and a.lot_id != "LOT-0006"]
    assert all(a.award_date == "2024-04-17" for a in dated_winners)
    assert all(a.conclusion_date == "2024-05-13" for a in dated_winners)


def test_hungarian_no_winner_lot_stays_a_loser():
    """LOT-0006 closed `clos-nw`; its SettledContract references no tender,
    so its single named bidder remains a non-winner under the new rule."""
    notice = _parse(_MANY_TENDERS)
    lot6 = [a for a in notice.awards if a.lot_id == "LOT-0006"]
    assert len(lot6) == 1
    assert not lot6[0].is_winner
    assert lot6[0].contractor_org_id == "ORG-0016"


def test_framework_settled_refs_cover_every_tender_so_all_stay_winners():
    """The 202 SettledContracts collectively reference all 272 LotTenders:
    a multi-supplier framework settles one contract per supplier, so no
    previously-correct winner may flip to loser."""
    notice = _parse(_FRAMEWORK)
    assert len(notice.awards) == 272
    assert all(a.is_winner for a in notice.awards)


def test_framework_dates_come_from_each_tenders_own_contract():
    """A LotResult references MANY SettledContracts (LOT-0005: 9), one per
    supplier. Each award must carry the conclusion date of the contract
    that references ITS tender — not the first contract's date smeared
    across all suppliers of the lot."""
    notice = _parse(_FRAMEWORK)
    lot5 = {a.conclusion_date for a in notice.awards if a.lot_id == "LOT-0005"}
    assert lot5 == {
        "2021-08-04", "2021-08-23", "2022-02-17", "2022-05-19", "2023-01-25",
        "2023-03-23", "2023-06-12", "2023-12-04", "2024-02-15",
    }
    assert len({a.conclusion_date for a in notice.awards}) == 130


def test_consortium_winners_unchanged_by_settled_contract_rule():
    """Every LotResult here references exactly the tender its
    SettledContract settles — all 6 awards stay winners."""
    notice = _parse(_CONSORTIUM)
    assert len(notice.awards) == 6
    assert all(a.is_winner for a in notice.awards)


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

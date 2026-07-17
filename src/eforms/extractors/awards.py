"""Extract award results — lot→tender→contractor mapping + values."""
from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from ..models import Award
from ..namespaces import NS
from .notice_metadata import _clean_date

_CBC_ID = "cbc:ID"

# cbc:TenderResultCode value marking a selected (winning) tender. The
# other code seen in the wild is "clos-nw" (closed, no winner).
_WINNER_CODE = "selec-w"

_RESULT_PATH = (
    ".//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension/efac:NoticeResult"
)


def extract_total_value(root: etree._Element) -> tuple[float | None, str | None]:
    """Extract the notice-level total award value and currency."""
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return None, None
    amount_el = result_el.find("cbc:TotalAmount", NS)
    if amount_el is None or not amount_el.text:
        return None, None
    try:
        value = float(amount_el.text.strip())
    except ValueError:
        return None, None
    currency = amount_el.get("currencyID")
    return value, currency


def extract_lot_tender_counts(root: etree._Element) -> dict[str, int]:
    """lot_id -> number of tenders received, from each LotResult's
    ReceivedSubmissionsStatistics (the 'tenders' total). Drives the
    single-bidder indicator."""
    counts: dict[str, int] = {}
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return counts
    for lot_result in result_el.findall("efac:LotResult", NS):
        lot_id_el = lot_result.find("efac:TenderLot/cbc:ID", NS)
        if lot_id_el is None or not lot_id_el.text:
            continue
        lot_id = lot_id_el.text.strip()
        for stat in lot_result.findall("efac:ReceivedSubmissionsStatistics", NS):
            code = (stat.findtext(
                "efbc:StatisticsCode", default="", namespaces=NS) or "").strip().lower()
            num = (stat.findtext(
                "efbc:StatisticsNumeric", default="", namespaces=NS) or "").strip()
            if code == "tenders" and num.isdigit() and int(num) > 0:
                # 0 received tenders on an awarded lot is contradictory
                # (you can't award a tender nobody bid on) — it's an
                # incomplete-statistics artifact, so treat it as "not
                # recorded" (skip) rather than a real zero.
                counts[lot_id] = int(num)
                break
    return counts


def _ref_text(parent: etree._Element, path: str) -> str | None:
    """Stripped text of the first `path` match, or None when absent/blank."""
    el = parent.find(path, NS)
    if el is None or not el.text or not el.text.strip():
        return None
    return el.text.strip()


@dataclass
class _TenderInfo:
    """A LotTender: who bid, for how much, at which cascade rank."""

    tpa_ref: str | None = None
    value: float | None = None
    currency: str | None = None
    rank: int | None = None


@dataclass
class _LotResultContext:
    """The per-LotResult facts shared by every Award it produces."""

    lot_id: str = ""
    is_winner: bool = True
    award_date: str | None = None
    conclusion_date: str | None = None


@dataclass
class _NoticeResultIndex:
    """Resolved lookup tables for the eForms award indirection chain."""

    # TenderingParty ID → EVERY named Tenderer org id. A consortium of
    # joint bidders lists one Tenderer per member; keeping only the first
    # (the historical bug) silently dropped the co-bidders.
    tpa_to_orgs: dict[str, list[str]] = field(default_factory=dict)
    tenders: dict[str, _TenderInfo] = field(default_factory=dict)
    award_dates: dict[str, str] = field(default_factory=dict)
    conclusion_dates: dict[str, str] = field(default_factory=dict)


def _build_tpa_to_orgs(result_el: etree._Element) -> dict[str, list[str]]:
    """TenderingParty ID → list of every named Tenderer org id."""
    mapping: dict[str, list[str]] = {}
    for tpa in result_el.findall("efac:TenderingParty", NS):
        tpa_id = _ref_text(tpa, _CBC_ID)
        if tpa_id is None:
            continue
        orgs = [
            el.text.strip()
            for el in tpa.findall("efac:Tenderer/cbc:ID", NS)
            if el.text and el.text.strip()
        ]
        if orgs:
            mapping[tpa_id] = orgs
    return mapping


def _tender_amount(lt: etree._Element) -> tuple[float | None, str | None]:
    """(value, currency) from a LotTender's payable amount."""
    val_el = lt.find("cac:LegalMonetaryTotal/cbc:PayableAmount", NS)
    if val_el is None or not val_el.text:
        return None, None
    try:
        value = float(val_el.text.strip())
    except ValueError:
        value = None
    return value, val_el.get("currencyID")


def _tender_rank(lt: etree._Element) -> int | None:
    """Cascade position from `cbc:RankCode`, or None when unranked."""
    rank = _ref_text(lt, "cbc:RankCode")
    if rank is None or not rank.isdigit():
        return None
    return int(rank)


def _build_tenders(result_el: etree._Element) -> dict[str, _TenderInfo]:
    """LotTender ID → its bidder ref, price and rank."""
    tenders: dict[str, _TenderInfo] = {}
    for lt in result_el.findall("efac:LotTender", NS):
        lt_id = _ref_text(lt, _CBC_ID)
        if lt_id is None:
            continue
        value, currency = _tender_amount(lt)
        tenders[lt_id] = _TenderInfo(
            tpa_ref=_ref_text(lt, "efac:TenderingParty/cbc:ID"),
            value=value,
            currency=currency,
            rank=_tender_rank(lt),
        )
    return tenders


def _build_contract_dates(
    result_el: etree._Element,
) -> tuple[dict[str, str], dict[str, str]]:
    """(SettledContract ID → award date, SettledContract ID → conclusion date)."""
    award_dates: dict[str, str] = {}
    conclusion_dates: dict[str, str] = {}
    for sc in result_el.findall("efac:SettledContract", NS):
        sc_id = _ref_text(sc, _CBC_ID)
        if sc_id is None:
            continue
        for path, target in (
            ("cbc:AwardDate", award_dates),
            # Contract conclusion/signing date (IssueDate on SettledContract)
            ("cbc:IssueDate", conclusion_dates),
        ):
            raw = _ref_text(sc, path)
            cleaned = _clean_date(raw) if raw else None
            if cleaned:
                target[sc_id] = cleaned
    return award_dates, conclusion_dates


def _build_index(result_el: etree._Element) -> _NoticeResultIndex:
    """Resolve every lookup table the LotResult pass joins against."""
    award_dates, conclusion_dates = _build_contract_dates(result_el)
    return _NoticeResultIndex(
        tpa_to_orgs=_build_tpa_to_orgs(result_el),
        tenders=_build_tenders(result_el),
        award_dates=award_dates,
        conclusion_dates=conclusion_dates,
    )


def _lot_result_context(
    lr: etree._Element, index: _NoticeResultIndex
) -> _LotResultContext | None:
    """Per-LotResult facts, or None when it names no lot."""
    lot_id_el = lr.find("efac:TenderLot/cbc:ID", NS)
    if lot_id_el is None:
        return None
    # A LotResult that omits cbc:TenderResultCode predates the field and
    # only ever records a winner — default True rather than demoting
    # every legacy award to a non-winner.
    code = _ref_text(lr, "cbc:TenderResultCode")
    sc_ref = _ref_text(lr, "efac:SettledContract/cbc:ID") or ""
    return _LotResultContext(
        lot_id=lot_id_el.text.strip() if lot_id_el.text else "",
        is_winner=code is None or code == _WINNER_CODE,
        award_date=index.award_dates.get(sc_ref),
        conclusion_date=index.conclusion_dates.get(sc_ref),
    )


def _awards_for_tender(
    tender_id: str, ctx: _LotResultContext, index: _NoticeResultIndex
) -> list[Award]:
    """One Award per named Tenderer behind `tender_id`.

    Consortium members each carry the FULL tender value — TED publishes no
    per-member split — flagged via `is_consortium_member` so consumers can
    deduplicate instead of summing the same money once per member.
    """
    info = index.tenders.get(tender_id)
    if info is None or info.tpa_ref is None:
        return []
    orgs = index.tpa_to_orgs.get(info.tpa_ref, [])
    is_consortium = len(orgs) > 1
    return [
        Award(
            lot_id=ctx.lot_id,
            contractor_org_id=org_id,
            value=info.value,
            currency=info.currency,
            award_date=ctx.award_date,
            conclusion_date=ctx.conclusion_date,
            rank=info.rank,
            is_winner=ctx.is_winner,
            tendering_party_id=info.tpa_ref,
            is_consortium_member=is_consortium,
        )
        for org_id in orgs
    ]


def _awards_for_lot_result(
    lr: etree._Element, index: _NoticeResultIndex
) -> list[Award]:
    """Every Award a single LotResult yields.

    A LotResult may reference MANY LotTenders (multi-supplier framework
    agreements and ranked cascades), so this fans out rather than taking
    the first reference only.
    """
    ctx = _lot_result_context(lr, index)
    if ctx is None:
        return []
    awards: list[Award] = []
    for ref in lr.findall("efac:LotTender/cbc:ID", NS):
        if ref.text and ref.text.strip():
            awards.extend(_awards_for_tender(ref.text.strip(), ctx, index))
    return awards


def extract_awards(root: etree._Element) -> list[Award]:
    """Extract per-lot award results.

    Real eForms structure (indirection chain):
      TenderingParty (TPA-0001) → Tenderer* → org IDs (ORG-0002…)
      LotTender (TEN-0001) → TenderingParty ref (TPA-0001), value, rank
      SettledContract (CON-0001) → has AwardDate
      LotResult → refs LotTender*, TenderLot, SettledContract

    Both starred edges are one-to-MANY, so one Award is emitted per
    (LotResult × LotTender × Tenderer). Only suppliers TED actually names
    produce an Award — losing bidders are never published, so an unnamed
    bidder is simply absent rather than invented.
    """
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return []
    index = _build_index(result_el)
    awards: list[Award] = []
    for lr in result_el.findall("efac:LotResult", NS):
        awards.extend(_awards_for_lot_result(lr, index))
    return awards

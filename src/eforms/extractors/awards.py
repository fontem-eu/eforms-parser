"""Extract award results — lot→tender→contractor mapping + values."""
from __future__ import annotations

from dataclasses import dataclass, field

from lxml import etree

from ..models import Award
from ..namespaces import NS
from .money import read_amount
from .notice_metadata import _clean_date

_CBC_ID = "cbc:ID"

# cbc:TenderResultCode value marking a selected (winning) tender. The
# other code seen in the wild is "clos-nw" (closed, no winner).
_WINNER_CODE = "selec-w"

_RESULT_PATH = (
    ".//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension/efac:NoticeResult"
)


def _total_amount(
    root: etree._Element,
) -> tuple[float | None, str | None, str | None]:
    """(value, currency, raw) of the NoticeResult's ``cbc:TotalAmount``."""
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return None, None, None
    return read_amount(result_el.find("cbc:TotalAmount", NS))


def extract_total_value(root: etree._Element) -> tuple[float | None, str | None]:
    """Extract the notice-level total award value and currency."""
    value, currency, _raw = _total_amount(root)
    if value is None:
        return None, None
    return value, currency


def extract_total_value_raw(root: etree._Element) -> str | None:
    """Verbatim ``cbc:TotalAmount`` text behind :func:`extract_total_value`,
    kept even when it does not parse — an unparseable total is still a
    published fact a cleaning stage wants to see."""
    return _total_amount(root)[2]


def _lot_total_submissions(lot_result: etree._Element) -> int | None:
    """The lot's received-tenders total, if the notice publishes one.

    Buyers publish the received-submission statistics under different
    codes of the same codelist: "tenders" is the plain total, but a
    large share of notices (audited 2026-07-26: 7 of 8 sampled
    missing-count notices across FR/PL/PT/DE) carry only "t-esubm" —
    the electronic-submissions total. E-submission is mandatory for
    covered EU procurement, so when "tenders" is absent, "t-esubm" is
    the total in practice. The plain total wins when both exist;
    sub-group codes (t-sme, t-micro, ...) are never used as the total.
    Zero on an awarded lot is contradictory (you can't award a tender
    nobody bid on) — an incomplete-statistics artifact, skipped.
    """
    plain = electronic = None
    for stat in lot_result.findall("efac:ReceivedSubmissionsStatistics", NS):
        code = (stat.findtext(
            "efbc:StatisticsCode", default="", namespaces=NS) or "").strip().lower()
        num = (stat.findtext(
            "efbc:StatisticsNumeric", default="", namespaces=NS) or "").strip()
        if not num.isdigit() or int(num) <= 0:
            continue
        if code == "tenders" and plain is None:
            plain = int(num)
        elif code == "t-esubm" and electronic is None:
            electronic = int(num)
    return plain if plain is not None else electronic


def extract_lot_tender_counts(root: etree._Element) -> dict[str, int]:
    """lot_id -> number of tenders received, from each LotResult's
    ReceivedSubmissionsStatistics. Drives the single-bidder indicator;
    total resolution rules live in :func:`_lot_total_submissions`."""
    counts: dict[str, int] = {}
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return counts
    for lot_result in result_el.findall("efac:LotResult", NS):
        lot_id_el = lot_result.find("efac:TenderLot/cbc:ID", NS)
        if lot_id_el is None or not lot_id_el.text:
            continue
        total = _lot_total_submissions(lot_result)
        if total is not None:
            counts[lot_id_el.text.strip()] = total
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
    # `cbc:PayableAmount` text `value` came from — the decimal presence
    # a float cannot carry.
    value_raw: str | None = None
    rank: int | None = None
    # `efac:TenderReference/cbc:ID` — the bidder's own tender reference.
    tender_reference: str | None = None


@dataclass
class _ContractDates:
    """The dates of one SettledContract: cleaned award and conclusion
    dates, plus the award date exactly as published (`award_raw` keeps
    the "2000-01-01" placeholder `award` nulls)."""

    award: str | None = None
    award_raw: str | None = None
    conclusion: str | None = None


@dataclass
class _FrameworkValues:
    """BT-709 / BT-660 from one LotResult's `efac:FrameworkAgreementValues`."""

    max_value: float | None = None
    max_currency: str | None = None
    reestimated_value: float | None = None
    reestimated_currency: str | None = None


@dataclass
class _LotResultContext:
    """The per-LotResult facts for the awards it produces.

    `is_winner` and `dates` are FALLBACK facts: they apply only to
    notices that emit no SettledContract→LotTender references at all;
    when those references exist they override both (see
    `_resolve_outcome`). `framework` is a fact about the lot itself and
    applies to every award of the LotResult.
    """

    lot_id: str = ""
    is_winner: bool = True
    dates: _ContractDates = field(default_factory=_ContractDates)
    framework: _FrameworkValues = field(default_factory=_FrameworkValues)


@dataclass
class _NoticeResultIndex:
    """Resolved lookup tables for the eForms award indirection chain."""

    # TenderingParty ID → EVERY named Tenderer org id. A consortium of
    # joint bidders lists one Tenderer per member; keeping only the first
    # (the historical bug) silently dropped the co-bidders.
    tpa_to_orgs: dict[str, list[str]] = field(default_factory=dict)
    tenders: dict[str, _TenderInfo] = field(default_factory=dict)
    # SettledContract ID → its dates (fallback path only).
    contract_dates: dict[str, _ContractDates] = field(default_factory=dict)
    # Every LotTender ID referenced by any SettledContract. When
    # non-empty this is the notice's authoritative winner set: Hungarian
    # (EKR) and Swedish eSender notices attach ALL received tenders to a
    # `selec-w` LotResult, and only the SettledContract reference tells
    # winners from named losers.
    settled_tender_ids: set[str] = field(default_factory=set)
    # LotTender ID → dates of the SettledContract that references it.
    # Keyed per tender because one LotResult may reference many
    # SettledContracts (one per framework supplier), each with its own
    # dates; loser tenders belong to no contract and get none.
    tender_dates: dict[str, _ContractDates] = field(default_factory=dict)


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


def _tender_rank(lt: etree._Element) -> int | None:
    """Cascade position from `cbc:RankCode`, or None when unranked."""
    rank = _ref_text(lt, "cbc:RankCode")
    if rank is None or not rank.isdigit():
        return None
    return int(rank)


def _build_tenders(result_el: etree._Element) -> dict[str, _TenderInfo]:
    """LotTender ID → its bidder ref, price (number and text), rank and
    the bidder's own tender reference."""
    tenders: dict[str, _TenderInfo] = {}
    for lt in result_el.findall("efac:LotTender", NS):
        lt_id = _ref_text(lt, _CBC_ID)
        if lt_id is None:
            continue
        value, currency, value_raw = read_amount(
            lt.find("cac:LegalMonetaryTotal/cbc:PayableAmount", NS))
        tenders[lt_id] = _TenderInfo(
            tpa_ref=_ref_text(lt, "efac:TenderingParty/cbc:ID"),
            value=value,
            currency=currency,
            value_raw=value_raw,
            rank=_tender_rank(lt),
            tender_reference=_ref_text(lt, "efac:TenderReference/cbc:ID"),
        )
    return tenders


def _build_contract_dates(result_el: etree._Element) -> dict[str, _ContractDates]:
    """SettledContract ID → its dates.

    `cbc:AwardDate` is kept twice: cleaned (sentinels such as the
    "2000-01-01" placeholder become None, as everywhere else) and
    verbatim, because the placeholder is itself the signal a scale
    census keys on. `cbc:IssueDate` on the SettledContract is the
    contract conclusion/signing date.
    """
    dates: dict[str, _ContractDates] = {}
    for sc in result_el.findall("efac:SettledContract", NS):
        sc_id = _ref_text(sc, _CBC_ID)
        if sc_id is None:
            continue
        award_raw = _ref_text(sc, "cbc:AwardDate")
        conclusion_raw = _ref_text(sc, "cbc:IssueDate")
        dates[sc_id] = _ContractDates(
            award=_clean_date(award_raw) if award_raw else None,
            award_raw=award_raw,
            conclusion=_clean_date(conclusion_raw) if conclusion_raw else None,
        )
    return dates


def _build_settled_tender_refs(result_el: etree._Element) -> dict[str, list[str]]:
    """SettledContract ID → the LotTender IDs it references (winners)."""
    refs: dict[str, list[str]] = {}
    for sc in result_el.findall("efac:SettledContract", NS):
        sc_id = _ref_text(sc, _CBC_ID)
        if sc_id is None:
            continue
        tender_ids = [
            el.text.strip()
            for el in sc.findall("efac:LotTender/cbc:ID", NS)
            if el.text and el.text.strip()
        ]
        if tender_ids:
            refs[sc_id] = tender_ids
    return refs


def _build_index(result_el: etree._Element) -> _NoticeResultIndex:
    """Resolve every lookup table the LotResult pass joins against."""
    contract_dates = _build_contract_dates(result_el)
    index = _NoticeResultIndex(
        tpa_to_orgs=_build_tpa_to_orgs(result_el),
        tenders=_build_tenders(result_el),
        contract_dates=contract_dates,
    )
    for sc_id, tender_ids in _build_settled_tender_refs(result_el).items():
        for tender_id in tender_ids:
            index.settled_tender_ids.add(tender_id)
            if sc_id in contract_dates:
                index.tender_dates[tender_id] = contract_dates[sc_id]
    return index


def _lot_framework_values(lr: etree._Element) -> _FrameworkValues:
    """BT-709 / BT-660 of the LotResult, or all-None when it has no
    `efac:FrameworkAgreementValues` (a plain contract)."""
    values = lr.find("efac:FrameworkAgreementValues", NS)
    if values is None:
        return _FrameworkValues()
    max_value, max_currency, _ = read_amount(
        values.find("cbc:MaximumValueAmount", NS))
    reestimated, reestimated_currency, _ = read_amount(
        values.find("efbc:ReestimatedValueAmount", NS))
    return _FrameworkValues(
        max_value=max_value,
        max_currency=max_currency,
        reestimated_value=reestimated,
        reestimated_currency=reestimated_currency,
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
        dates=index.contract_dates.get(sc_ref, _ContractDates()),
        framework=_lot_framework_values(lr),
    )


def _resolve_outcome(
    tender_id: str, ctx: _LotResultContext, index: _NoticeResultIndex
) -> tuple[bool, _ContractDates]:
    """(is_winner, contract dates) for one referenced tender.

    When the notice emits any SettledContract→LotTender reference, that
    reference set is the authoritative winner list: Hungarian (EKR) and
    Swedish eSender notices attach EVERY received tender to the `selec-w`
    LotResult, so the LotResult code alone would crown named LOSING
    bidders as winners. The decision is scoped per NOTICE, not per lot —
    in every observed notice either all settled contracts carry the
    references or none do (the one contract without them in the corpus
    belongs to a `clos-nw` lot, whose tender is a loser either way).

    Contract dates attach only to the tender the settling contract
    actually references — losers are not party to any contract and get
    none (raw included).

    Fallback (no references anywhere in the notice — some countries never
    emit them): the LotResult's `cbc:TenderResultCode` rule and its
    contract's dates, unchanged from before.
    """
    if index.settled_tender_ids:
        return (
            tender_id in index.settled_tender_ids,
            index.tender_dates.get(tender_id, _ContractDates()),
        )
    return ctx.is_winner, ctx.dates


def _awards_for_tender(
    tender_id: str, ctx: _LotResultContext, index: _NoticeResultIndex
) -> list[Award]:
    """One Award per named Tenderer behind `tender_id`.

    Consortium members each carry the FULL tender value — TED publishes no
    per-member split — flagged via `is_consortium_member` so consumers can
    deduplicate instead of summing the same money once per member.

    Non-winner awards (named losing bidders) are emitted on purpose —
    they are the only public record of who ELSE bid. Their `value` is the
    losing BID amount, not an award value: consumers must never sum
    non-winner values into contract totals.
    """
    info = index.tenders.get(tender_id)
    if info is None or info.tpa_ref is None:
        return []
    is_winner, dates = _resolve_outcome(tender_id, ctx, index)
    orgs = index.tpa_to_orgs.get(info.tpa_ref, [])
    is_consortium = len(orgs) > 1
    return [
        Award(
            lot_id=ctx.lot_id,
            contractor_org_id=org_id,
            value=info.value,
            currency=info.currency,
            award_date=dates.award,
            conclusion_date=dates.conclusion,
            rank=info.rank,
            is_winner=is_winner,
            tendering_party_id=info.tpa_ref,
            is_consortium_member=is_consortium,
            award_date_raw=dates.award_raw,
            tender_reference=info.tender_reference,
            value_raw=info.value_raw,
            framework_max_value=ctx.framework.max_value,
            framework_max_value_currency=ctx.framework.max_currency,
            framework_reestimated_value=ctx.framework.reestimated_value,
            framework_reestimated_value_currency=ctx.framework.reestimated_currency,
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
      LotTender (TEN-0001) → TenderingParty ref (TPA-0001), value, rank,
                             TenderReference
      SettledContract (CON-0001) → has AwardDate, refs LotTender*
      LotResult → refs LotTender*, TenderLot, SettledContract*,
                  FrameworkAgreementValues (BT-709 / BT-660)

    Both starred Tenderer/LotTender edges are one-to-MANY, so one Award
    is emitted per (LotResult × LotTender × Tenderer). Only suppliers TED
    actually names produce an Award — an unnamed bidder is simply absent
    rather than invented. Some eSenders (Hungarian EKR, Swedish) DO name
    losing bidders by attaching every received tender to the LotResult;
    those yield Awards with `is_winner=False`, decided by the
    SettledContract→LotTender references (see `_resolve_outcome`).
    """
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return []
    index = _build_index(result_el)
    awards: list[Award] = []
    for lr in result_el.findall("efac:LotResult", NS):
        awards.extend(_awards_for_lot_result(lr, index))
    return awards

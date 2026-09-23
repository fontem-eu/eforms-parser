"""Framework-agreement terms (data-backlog Part 5, C6).

Until 0.12 the parser kept one bit about frameworks — ``is_framework``.
A framework node needs its ceiling, its re-estimated value, its duration
and how many operators it admits, and each of those sits in the eForms
XML under its own business term, at its own level:

* BT-271 ``efbc:FrameworkMaximumAmount`` — the procedure's framework
  maximum, an eForms extension inside the UBL amount container
  ``cac:ProcurementProject/cac:RequestedTenderTotal``. eForms also
  publishes it per lot and per lots-group (same path under
  ``cac:ProcurementProjectLot``); this module reads the PROCEDURE one
  only, with a root-relative path so a lot's figure can never stand in
  for it.
* BT-118 ``efbc:OverallMaximumFrameworkContractsAmount`` — the ceiling
  restated on the ``efac:NoticeResult``; used when BT-271 is absent.
* BT-1118 ``efbc:OverallApproximateFrameworkContractsAmount`` — the
  notice-level re-estimate on the ``efac:NoticeResult``.
* BT-709 ``cbc:MaximumValueAmount`` / BT-660 ``efbc:ReestimatedValueAmount``
  under each LotResult's ``efac:FrameworkAgreementValues``. Per lot, so
  they ride on the awards (:class:`~eforms.models.Award`); they stand in
  for the notice-level figure only when the notice has exactly ONE
  LotResult — never summed.
* BT-36 ``cbc:DurationMeasure`` under the lot's
  ``cac:ProcurementProject/cac:PlannedPeriod``. eForms has no separate
  framework-duration term: for a lot whose contracting system sets up a
  framework agreement (``cbc:ContractingSystemTypeCode
  [@listName='framework-agreement']`` = ``fa-*``) the lot's duration IS
  the framework's. Read only from such lots, so a plain contract's
  "6 WEEK" never masquerades as a framework term.
* BT-113 ``cbc:MaximumOperatorQuantity`` under the lot's
  ``cac:TenderingProcess/cac:FrameworkAgreement``.

Every fixture under ``tests/fixtures`` was probed for each path. BT-118
alone (without BT-271), BT-1118 and BT-113 occur in none of them and are
covered by inline XML in the tests, with absence asserted on the real
notices.

The grouping key (0.13)
-----------------------

The terms above describe one notice's own framework. What ties the
notices OF one framework agreement together is a separate datum, and
0.13 adds it:

* OPT-100 ``efac:NoticeResult/efac:SettledContract/
  cac:NoticeDocumentReference/cbc:ID`` — the "Framework Notice
  Identifier". The framework-establishing award notice and every
  call-off under it carry the IDENTICAL value; TED indexes it as the
  expert-search field ``framework-notice-id``. Present in 274/351
  (78.1%) of sampled call-off award notices; TED-wide, across
  framework-flagged award notices, 28.8% in 2024, 89.4% in 2025 and
  98.3% in 2026. Read from the NoticeResult's own SettledContract
  records, not with a ``.//`` sweep: each LotResult repeats a
  one-line ``efac:SettledContract`` stub that references a record by
  id and carries no reference of its own (761784-2024: 7 records, 7
  stubs).
* BT-125 ``cac:TenderingProcess/cac:NoticeDocumentReference/cbc:ID`` —
  the previous-notice reference, a weaker fallback worth about
  +10.8pp of coverage. Read ONLY when a lot sets up a framework
  agreement: on any other procedure BT-125 is simply "the notice
  before this one" and points at an unrelated prior information
  notice (324192-2024, a non-framework Hungarian award, publishes
  413145-2023 there). Root-relative like BT-271 above — a lot's
  previous-notice reference is a statement about that lot.

Both terms carry the same two value forms as the modification back-link
BT-1501 — a publication number or an eForms notice UUID with its
version suffix — so :func:`~eforms.extractors.notice_metadata.split_back_link`
is what normalises them. One notice can write one form in OPT-100 and
the other in BT-125: 761784-2024 publishes ``536632-2024`` in OPT-100
and ``00536632-2024`` in BT-125. TED's own index returns that
framework's two award notices for the unpadded form and nothing at all
for the padded one, so both sides are normalised onto the unpadded form
before anything groups on them.

It is a grouping key and nothing more. About 80% of the time the notice
it names is a call for competition, which this platform does not ingest
(prod holds award and modification notices only), so it resolves to a
contract we hold roughly 13.6% of the time. Nothing in the data says
which side of a framework a notice is on: an establishment and a
call-off both carry the key, and both carry ``is_framework`` (344/351
confirmed call-offs do).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterator

from lxml import etree

from ..namespaces import NS
from .awards import _RESULT_PATH
from .money import read_amount
from .notice_metadata import split_back_link

_EXTENSION = (
    "ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension"
)
# Root-relative on purpose (no ".//"): the lot-level BT-271 lives under
# cac:ProcurementProjectLot/cac:ProcurementProject/... and must not match.
_PROCEDURE_MAX = (
    f"cac:ProcurementProject/cac:RequestedTenderTotal/{_EXTENSION}/"
    "efbc:FrameworkMaximumAmount"
)
_NOTICE_MAX = f"{_RESULT_PATH}/efbc:OverallMaximumFrameworkContractsAmount"
_NOTICE_REESTIMATED = f"{_RESULT_PATH}/efbc:OverallApproximateFrameworkContractsAmount"
_LOT_RESULTS = f"{_RESULT_PATH}/efac:LotResult"
_LOTS = ".//cac:ProcurementProjectLot"
_LOT_FA_CODE = (
    "cac:TenderingProcess/cac:ContractingSystem/"
    "cbc:ContractingSystemTypeCode[@listName='framework-agreement']"
)
_LOT_DURATION = "cac:ProcurementProject/cac:PlannedPeriod/cbc:DurationMeasure"
_LOT_MAX_OPERATORS = (
    "cac:TenderingProcess/cac:FrameworkAgreement/cbc:MaximumOperatorQuantity"
)

# OPT-100, on the NoticeResult's own SettledContract records. The
# LotResults' ``efac:SettledContract`` stubs sit one level deeper and only
# reference a record by id, so this path skips them by construction.
_SETTLED_NOTICE_REF = (
    f"{_RESULT_PATH}/efac:SettledContract/cac:NoticeDocumentReference/cbc:ID"
)
# BT-125 at procedure level. Root-relative on purpose (no ".//"), like
# _PROCEDURE_MAX above: the lot-level previous-notice reference is a
# statement about one lot and must not stand in for the procedure's.
_PREVIOUS_NOTICE_REF = "cac:TenderingProcess/cac:NoticeDocumentReference/cbc:ID"

_SOURCE_OPT_100 = "opt-100"
_SOURCE_BT_125 = "bt-125"

# eForms ``duration-unit`` codes with an exact month equivalent. WEEK and
# DAY have none and stay raw-only rather than rounded.
_MONTHS_PER_UNIT = {"MONTH": 1, "YEAR": 12}


@dataclass
class FrameworkTerms:  # pylint: disable=too-many-instance-attributes
    """Notice-level framework-agreement terms, every field None when the
    notice does not publish it. Names match the ``framework_*`` fields of
    :class:`~eforms.models.Notice` one to one."""

    max_value: float | None = None
    max_value_currency: str | None = None
    max_value_raw: str | None = None
    reestimated_value: float | None = None
    reestimated_value_currency: str | None = None
    duration_months: int | None = None
    duration_raw: str | None = None
    max_operators: int | None = None


def _first_amount(
    root: etree._Element, *paths: str
) -> tuple[float | None, str | None, str | None]:
    """(value, currency, raw) of the first of ``paths`` that is published."""
    for path in paths:
        value, currency, raw = read_amount(root.find(path, NS))
        if raw is not None:
            return value, currency, raw
    return None, None, None


def _single_lot_result_amount(
    root: etree._Element, tag: str
) -> tuple[float | None, str | None, str | None]:
    """The LotResult's ``efac:FrameworkAgreementValues/<tag>`` when the
    notice has exactly one LotResult; all-None otherwise. A multi-lot
    notice has one figure per lot and no honest single one."""
    lot_results = root.findall(_LOT_RESULTS, NS)
    if len(lot_results) != 1:
        return None, None, None
    return read_amount(
        lot_results[0].find(f"efac:FrameworkAgreementValues/{tag}", NS))


def _framework_lots(root: etree._Element) -> Iterator[etree._Element]:
    """The lots whose contracting system sets up a framework agreement."""
    for lot in root.findall(_LOTS, NS):
        code = lot.findtext(_LOT_FA_CODE, default="", namespaces=NS) or ""
        if code.strip().lower().startswith("fa"):
            yield lot


def _duration(lot: etree._Element) -> tuple[int | None, str | None]:
    """(months, raw) of the lot's BT-36 duration. ``raw`` is
    "<number> <unitCode>" whenever published; ``months`` only when the
    unit converts exactly and the number is a whole one."""
    el = lot.find(_LOT_DURATION, NS)
    if el is None or not el.text or not el.text.strip():
        return None, None
    number = el.text.strip()
    unit = (el.get("unitCode") or "").strip()
    raw = f"{number} {unit}".strip()
    factor = _MONTHS_PER_UNIT.get(unit.upper())
    if factor is None or not number.isdigit():
        return None, raw
    return int(number) * factor, raw


def _framework_duration(root: etree._Element) -> tuple[int | None, str | None]:
    """The first framework lot's published duration."""
    for lot in _framework_lots(root):
        months, raw = _duration(lot)
        if raw is not None:
            return months, raw
    return None, None


def _max_operators(root: etree._Element) -> int | None:
    """BT-113 from the first lot that publishes it (the element only
    exists inside a ``cac:FrameworkAgreement``, so no framework gate)."""
    for lot in root.findall(_LOTS, NS):
        text = (lot.findtext(_LOT_MAX_OPERATORS, default="", namespaces=NS) or "").strip()
        if text.isdigit():
            return int(text)
    return None


def extract_framework_terms(root: etree._Element) -> FrameworkTerms:
    """Every notice-level framework term the notice publishes."""
    max_value, max_currency, max_raw = _first_amount(
        root, _PROCEDURE_MAX, _NOTICE_MAX)
    if max_raw is None:
        max_value, max_currency, max_raw = _single_lot_result_amount(
            root, "cbc:MaximumValueAmount")
    reestimated, reestimated_currency, reestimated_raw = _first_amount(
        root, _NOTICE_REESTIMATED)
    if reestimated_raw is None:
        reestimated, reestimated_currency, _ = _single_lot_result_amount(
            root, "efbc:ReestimatedValueAmount")
    duration_months, duration_raw = _framework_duration(root)
    return FrameworkTerms(
        max_value=max_value,
        max_value_currency=max_currency,
        max_value_raw=max_raw,
        reestimated_value=reestimated,
        reestimated_value_currency=reestimated_currency,
        duration_months=duration_months,
        duration_raw=duration_raw,
        max_operators=_max_operators(root),
    )


@dataclass
class FrameworkNoticeReference:
    """The framework grouping key a notice publishes, or all-empty when it
    publishes none. Field names map one to one onto the
    ``framework_notice_id*`` fields of :class:`~eforms.models.Notice`."""

    notice_id: str | None = None
    notice_id_raw: str | None = None
    notice_id_source: str | None = None
    notice_id_conflict: bool = False


def normalise_framework_notice_id(raw: str | None) -> str | None:
    """The canonical grouping key behind a framework notice reference.

    OPT-100 and BT-125 carry the same two value forms as the modification
    back-link BT-1501 — a publication number (``536632-2024``) or an
    eForms notice UUID with its version suffix
    (``45d7e260-cdfb-4ae3-a3d9-fdc8beea8b77-01``, as 156-2025 writes it) —
    so :func:`split_back_link` already knows how to tell them apart and
    strips the zero padding and the version suffix respectively. Which of
    the two a value is does not matter here: either way it is a key, so
    the two return slots collapse into one. Anything that is neither form
    is kept verbatim (trimmed) — an unrecognised key still groups a
    framework with itself, and a rewritten one would group it with
    nothing.
    """
    publication_number, notice_id = split_back_link(raw)
    return publication_number or notice_id


def _published_ids(root: etree._Element, path: str) -> list[str]:
    """Trimmed text of every ``path`` match that has any, in document order."""
    return [
        el.text.strip()
        for el in root.findall(path, NS)
        if el.text and el.text.strip()
    ]


def _agreed_key(raws: list[str]) -> tuple[str | None, str | None, bool]:
    """(key, raw, conflict) across a notice's SettledContract references.

    The contracts of one notice normally name one framework. Counted on
    the NORMALISED value, so a notice that writes the same framework
    padded on one contract and unpadded on another agrees with itself and
    is not reported as a conflict. When they genuinely disagree the most
    common value wins, ties going to the first in document order, and
    ``conflict`` says so rather than letting the majority hide it.
    """
    keyed = [(normalise_framework_notice_id(raw), raw) for raw in raws]
    keyed = [(key, raw) for key, raw in keyed if key]
    if not keyed:
        return None, None, False
    counts = Counter(key for key, _ in keyed)
    # max() over a Counter keeps insertion (document) order on ties.
    key = max(counts, key=counts.get)
    raw = next(published for candidate, published in keyed if candidate == key)
    return key, raw, len(counts) > 1


def extract_framework_notice_reference(
    root: etree._Element,
) -> FrameworkNoticeReference:
    """The framework grouping key: OPT-100, else BT-125 on a framework
    procedure. Never a pointer to a contract we hold — see the module
    docstring."""
    key, raw, conflict = _agreed_key(_published_ids(root, _SETTLED_NOTICE_REF))
    if key is not None:
        return FrameworkNoticeReference(
            notice_id=key,
            notice_id_raw=raw,
            notice_id_source=_SOURCE_OPT_100,
            notice_id_conflict=conflict,
        )
    # The gate: off a framework procedure BT-125 is an unrelated prior
    # notice, and reading it would invent framework siblings.
    if next(_framework_lots(root), None) is None:
        return FrameworkNoticeReference()
    # eForms allows one previous-notice reference per procedure.
    previous = _published_ids(root, _PREVIOUS_NOTICE_REF)
    if not previous:
        return FrameworkNoticeReference()
    return FrameworkNoticeReference(
        notice_id=normalise_framework_notice_id(previous[0]),
        notice_id_raw=previous[0],
        notice_id_source=_SOURCE_BT_125,
    )

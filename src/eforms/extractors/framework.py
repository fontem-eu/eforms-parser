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
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from lxml import etree

from ..namespaces import NS
from .awards import _RESULT_PATH
from .money import read_amount

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

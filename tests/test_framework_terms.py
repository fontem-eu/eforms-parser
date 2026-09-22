"""Framework-agreement terms (data-backlog Part 5, C6).

A :FrameworkAgreement node needs its ceiling, its re-estimate, its
duration and its operator cap; until 0.12 the parser kept only the
``is_framework`` bit. Each term has its own eForms business term and
level (see ``eforms.extractors.framework``); these tests pin every path
against unmodified TED downloads and cover the ones no fixture carries
(BT-118 alone, BT-1118, BT-113) with inline XML, asserting their absence
on the real notices.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eforms.namespaces import NS
from eforms.parser import parse

_FIXTURES = Path(__file__).parent / "fixtures"

# Italian CAN: 4 lots, each `fa-mix`, 24 MONTH; BT-271 on the procedure
# (EUR 11 255 517) restated as BT-118; BT-709 per LotResult.
_CONSORTIUM = "eforms_can_consortium_3_tenderers_324264-2024.xml"
# Romanian multi-supplier framework: 21 lots `fa-wo-rc`, 36 MONTH; BT-271
# on the procedure (RON 18 653 880.2); BT-709 AND BT-660 on all 21 LotResults.
_FRAMEWORK = "eforms_can_framework_multi_supplier_324249-2024.xml"
# Hungarian CAN: 23 lots, framework-agreement = none, 12 MONTH each.
_MANY_TENDERS = "eforms_can_many_tenders_few_named_324192-2024.xml"
# German award: framework-agreement = none, 6 WEEK.
_DE_AWARD = "eforms_can_standard_de_award_of_562407_201338-2026.xml"
# Portuguese modification: no ContractingSystem at all.
_PT_MODIFICATION = "eforms_can_modif_pt_orphan_award_540529-2026.xml"

_NS_DECL = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
_EXT_OPEN = (
    "<ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>"
    "<efext:EformsExtension>"
)
_EXT_CLOSE = (
    "</efext:EformsExtension>"
    "</ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>"
)


def _parse(name: str):
    return parse((_FIXTURES / name).read_bytes())


def _notice(*parts: str) -> bytes:
    return f'<?xml version="1.0"?><Root {_NS_DECL}>{"".join(parts)}</Root>'.encode()


def _lot(lot_id: str, fa_code: str | None, duration: str = "", extra: str = "") -> str:
    system = (
        "<cac:ContractingSystem><cbc:ContractingSystemTypeCode "
        f"listName=\"framework-agreement\">{fa_code}</cbc:ContractingSystemTypeCode>"
        "</cac:ContractingSystem>"
    ) if fa_code is not None else ""
    return (
        f"<cac:ProcurementProjectLot><cbc:ID schemeName=\"Lot\">{lot_id}</cbc:ID>"
        f"<cac:TenderingProcess>{system}{extra}</cac:TenderingProcess>"
        f"<cac:ProcurementProject><cac:PlannedPeriod>{duration}</cac:PlannedPeriod>"
        "</cac:ProcurementProject></cac:ProcurementProjectLot>"
    )


def _lot_result(res_id: str, lot_id: str, values: str = "") -> str:
    return (
        f"<efac:LotResult><cbc:ID>{res_id}</cbc:ID>"
        f"{values}<efac:TenderLot><cbc:ID>{lot_id}</cbc:ID></efac:TenderLot>"
        "</efac:LotResult>"
    )


def _result(*lot_results: str, extra: str = "") -> str:
    body = extra + "".join(lot_results)
    return f"{_EXT_OPEN}<efac:NoticeResult>{body}</efac:NoticeResult>{_EXT_CLOSE}"


# ── Real notices ───────────────────────────────────────────────────────────


def test_italian_framework_reads_the_procedure_ceiling_and_duration():
    notice = _parse(_CONSORTIUM)
    assert notice.is_framework is True
    # BT-271 under cac:ProcurementProject/cac:RequestedTenderTotal
    assert notice.framework_max_value == 11255517.0
    assert notice.framework_max_value_currency == "EUR"
    assert notice.framework_max_value_raw == "11255517"
    # 4 LotResults publish BT-709 but no BT-660; no BT-1118 either
    assert notice.framework_reestimated_value is None
    assert notice.framework_reestimated_value_currency is None
    # BT-36 of the `fa-mix` lots
    assert notice.framework_duration_months == 24
    assert notice.framework_duration_raw == "24 MONTH"
    # BT-113 is not published
    assert notice.framework_max_operators is None


def test_italian_framework_carries_each_lots_ceiling_on_its_awards():
    """BT-709 is per LotResult: LOT-0003's three consortium members all
    carry the same lot ceiling, as `tenders_received` would."""
    notice = _parse(_CONSORTIUM)
    per_lot = {(a.lot_id, a.framework_max_value, a.framework_max_value_currency)
               for a in notice.awards}
    assert per_lot == {
        ("LOT-0001", 1705713.0, "EUR"),
        ("LOT-0002", 2217896.0, "EUR"),
        ("LOT-0003", 1947708.0, "EUR"),
        ("LOT-0004", 1515405.0, "EUR"),
    }
    assert all(a.framework_reestimated_value is None for a in notice.awards)


def test_romanian_framework_reads_procedure_ceiling_not_a_lot_sum():
    notice = _parse(_FRAMEWORK)
    assert notice.is_framework is True
    assert notice.framework_max_value == 18653880.2
    assert notice.framework_max_value_currency == "RON"
    assert notice.framework_max_value_raw == "18653880.2"
    # 21 LotResults each publish BT-660: no single honest notice figure,
    # and never a sum — the per-lot values live on the awards.
    assert notice.framework_reestimated_value is None
    assert notice.framework_duration_months == 36
    assert notice.framework_duration_raw == "36 MONTH"
    assert notice.framework_max_operators is None


def test_romanian_framework_awards_carry_their_lots_max_and_reestimate():
    notice = _parse(_FRAMEWORK)
    assert len(notice.awards) == 272
    assert all(a.framework_max_value_currency == "RON" for a in notice.awards)
    assert all(a.framework_reestimated_value_currency == "RON" for a in notice.awards)
    lot5 = {(a.framework_max_value, a.framework_reestimated_value)
            for a in notice.awards if a.lot_id == "LOT-0005"}
    assert lot5 == {(100000.0, 470000.0)}
    first_lots = {(a.lot_id, a.framework_max_value) for a in notice.awards
                  if a.lot_id in {"LOT-0001", "LOT-0002", "LOT-0003", "LOT-0004"}}
    assert first_lots == {
        ("LOT-0001", 187500.0), ("LOT-0002", 121500.0),
        ("LOT-0003", 97200.0), ("LOT-0004", 60000.0),
    }
    # one FrameworkAgreementValues block per lot → 21 distinct lot ceilings
    assert len({(a.lot_id, a.framework_max_value) for a in notice.awards}) == 21


@pytest.mark.parametrize("fixture", [_MANY_TENDERS, _DE_AWARD, _PT_MODIFICATION])
def test_non_framework_notices_publish_no_framework_terms(fixture):
    """The Hungarian lots run 12 MONTH and the German one 6 WEEK, but
    neither sets up a framework: a plain contract's duration must not
    surface as a framework term."""
    notice = _parse(fixture)
    assert notice.is_framework is not True
    assert notice.framework_max_value is None
    assert notice.framework_max_value_currency is None
    assert notice.framework_max_value_raw is None
    assert notice.framework_reestimated_value is None
    assert notice.framework_reestimated_value_currency is None
    assert notice.framework_duration_months is None
    assert notice.framework_duration_raw is None
    assert notice.framework_max_operators is None
    assert all(a.framework_max_value is None for a in notice.awards)
    assert all(a.framework_reestimated_value is None for a in notice.awards)


# ── Paths no fixture carries: SDK-derived, inline ─────────────────────────


def test_notice_result_ceiling_is_the_fallback_for_a_missing_procedure_one():
    """BT-118 on the NoticeResult, when BT-271 is absent."""
    xml = _notice(_result(
        _lot_result("RES-0001", "LOT-0001"), _lot_result("RES-0002", "LOT-0002"),
        extra='<efbc:OverallMaximumFrameworkContractsAmount currencyID="EUR">'
              '5000000.00</efbc:OverallMaximumFrameworkContractsAmount>'
              '<efbc:OverallApproximateFrameworkContractsAmount currencyID="EUR">'
              '4200000</efbc:OverallApproximateFrameworkContractsAmount>',
    ))
    notice = parse(xml)
    assert notice.framework_max_value == 5000000.0
    assert notice.framework_max_value_currency == "EUR"
    assert notice.framework_max_value_raw == "5000000.00"
    # BT-1118: the notice-level re-estimate
    assert notice.framework_reestimated_value == 4200000.0
    assert notice.framework_reestimated_value_currency == "EUR"


def test_procedure_ceiling_wins_over_the_notice_result_one():
    xml = _notice(
        "<cac:ProcurementProject><cac:RequestedTenderTotal>"
        f'{_EXT_OPEN}<efbc:FrameworkMaximumAmount currencyID="EUR">'
        f"7000000</efbc:FrameworkMaximumAmount>{_EXT_CLOSE}"
        "</cac:RequestedTenderTotal></cac:ProcurementProject>",
        _result(extra='<efbc:OverallMaximumFrameworkContractsAmount currencyID="EUR">'
                      '5000000.00</efbc:OverallMaximumFrameworkContractsAmount>'),
    )
    notice = parse(xml)
    assert notice.framework_max_value == 7000000.0
    assert notice.framework_max_value_raw == "7000000"


def test_lot_level_ceiling_never_stands_in_for_the_procedure_one():
    """BT-271-Lot sits at the same relative path under the lot; a
    root-relative lookup must not pick it up as the procedure figure."""
    lot_max = (
        "<cac:ProcurementProjectLot><cbc:ID>LOT-0001</cbc:ID><cac:ProcurementProject>"
        f'<cac:RequestedTenderTotal>{_EXT_OPEN}<efbc:FrameworkMaximumAmount '
        f'currencyID="EUR">900</efbc:FrameworkMaximumAmount>{_EXT_CLOSE}'
        "</cac:RequestedTenderTotal></cac:ProcurementProject></cac:ProcurementProjectLot>"
    )
    notice = parse(_notice(
        lot_max, _result(_lot_result("RES-0001", "LOT-0001"), _lot_result("RES-0002", "LOT-0002"))))
    assert notice.framework_max_value is None
    assert notice.framework_max_value_raw is None


def test_single_lot_result_values_stand_in_for_the_notice_figures():
    """One LotResult: its BT-709 / BT-660 ARE the notice's ceiling and
    re-estimate when nothing notice-level is published."""
    values = (
        '<efac:FrameworkAgreementValues>'
        '<cbc:MaximumValueAmount currencyID="RON">120000</cbc:MaximumValueAmount>'
        '<efbc:ReestimatedValueAmount currencyID="RON">95000.5</efbc:ReestimatedValueAmount>'
        '</efac:FrameworkAgreementValues>'
    )
    notice = parse(_notice(_result(_lot_result("RES-0001", "LOT-0001", values))))
    assert notice.framework_max_value == 120000.0
    assert notice.framework_max_value_currency == "RON"
    assert notice.framework_max_value_raw == "120000"
    assert notice.framework_reestimated_value == 95000.5
    assert notice.framework_reestimated_value_currency == "RON"


def test_several_lot_results_are_never_summed_into_a_notice_figure():
    values = (
        '<efac:FrameworkAgreementValues>'
        '<cbc:MaximumValueAmount currencyID="RON">120000</cbc:MaximumValueAmount>'
        '<efbc:ReestimatedValueAmount currencyID="RON">95000</efbc:ReestimatedValueAmount>'
        '</efac:FrameworkAgreementValues>'
    )
    notice = parse(_notice(_result(
        _lot_result("RES-0001", "LOT-0001", values), _lot_result("RES-0002", "LOT-0002", values))))
    assert notice.framework_max_value is None
    assert notice.framework_reestimated_value is None


@pytest.mark.parametrize(
    "duration_xml, months, raw",
    [
        ('<cbc:DurationMeasure unitCode="MONTH">48</cbc:DurationMeasure>', 48, "48 MONTH"),
        ('<cbc:DurationMeasure unitCode="YEAR">4</cbc:DurationMeasure>', 48, "4 YEAR"),
        # no exact month equivalent: raw only, never rounded
        ('<cbc:DurationMeasure unitCode="WEEK">6</cbc:DurationMeasure>', None, "6 WEEK"),
        ('<cbc:DurationMeasure unitCode="DAY">90</cbc:DurationMeasure>', None, "90 DAY"),
        # not a whole number: raw only
        ('<cbc:DurationMeasure unitCode="MONTH">1.5</cbc:DurationMeasure>', None, "1.5 MONTH"),
        ("", None, None),
    ],
)
def test_framework_duration_converts_only_exact_units(duration_xml, months, raw):
    notice = parse(_notice(_lot("LOT-0001", "fa-wo-rc", duration_xml)))
    assert notice.is_framework is True
    assert notice.framework_duration_months == months
    assert notice.framework_duration_raw == raw


def test_framework_duration_comes_from_the_first_framework_lot():
    """A plain lot before the framework lot contributes nothing; the
    framework lot's duration is the notice's."""
    xml = _notice(
        _lot("LOT-0001", "none",
             '<cbc:DurationMeasure unitCode="MONTH">3</cbc:DurationMeasure>'),
        _lot("LOT-0002", "fa-w-rc",
             '<cbc:DurationMeasure unitCode="MONTH">24</cbc:DurationMeasure>'),
    )
    notice = parse(xml)
    assert notice.framework_duration_months == 24
    assert notice.framework_duration_raw == "24 MONTH"


def test_framework_max_operators_from_the_lots_framework_agreement():
    """BT-113 `cac:TenderingProcess/cac:FrameworkAgreement/cbc:MaximumOperatorQuantity`."""
    xml = _notice(_lot(
        "LOT-0001", "fa-w-rc",
        extra="<cac:FrameworkAgreement><cbc:MaximumOperatorQuantity>3"
              "</cbc:MaximumOperatorQuantity></cac:FrameworkAgreement>",
    ))
    assert parse(xml).framework_max_operators == 3


def test_framework_max_operators_ignores_a_non_numeric_value():
    xml = _notice(_lot(
        "LOT-0001", "fa-w-rc",
        extra="<cac:FrameworkAgreement><cbc:MaximumOperatorQuantity>several"
              "</cbc:MaximumOperatorQuantity></cac:FrameworkAgreement>",
    ))
    assert parse(xml).framework_max_operators is None

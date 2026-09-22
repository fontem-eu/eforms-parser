"""Raw signals the cleaning stage keys on (data-backlog Part 5, C4/C5).

The loader used to see placeholder award dates only to discard them, and
amounts only as floats. The watermarks that mark Portugal's eForms
gateway (``AwardDate 2000-01-01``, ``TenderReference "0.0"``) and the
decimal presence of an amount were documented but never persisted, which
is why a census of the damage was impossible. These fields carry the
published text next to the cleaned value; the cleaned value is unchanged.

Every ``tests/fixtures`` notice is an unmodified TED download; expected
values were read from the XML, not assumed. None of the six eForms
fixtures carries a contract-level watermark (their SettledContracts
either publish a real ``cbc:AwardDate`` or none at all, and no
``TenderReference`` is ``0.0``), so the watermark shape is an inline
notice modelled on 646890-2026 (Beja, EUR 24 474 133 with no decimals).
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from lxml import etree

from eforms.extractors.money import read_amount
from eforms.parser import parse

_FIXTURES = Path(__file__).parent / "fixtures"

_CONSORTIUM = "eforms_can_consortium_3_tenderers_324264-2024.xml"
_FRAMEWORK = "eforms_can_framework_multi_supplier_324249-2024.xml"
_MANY_TENDERS = "eforms_can_many_tenders_few_named_324192-2024.xml"
_DE_MODIFICATION = "eforms_can_modif_de_562407-2026.xml"
_PT_MODIFICATION = "eforms_can_modif_pt_orphan_award_540529-2026.xml"
_DE_AWARD = "eforms_can_standard_de_award_of_562407_201338-2026.xml"
_LEGACY_SOLE = "ted_export_f03_award_sole_winner_217109-2022.xml"
_LEGACY_CONSORTIUM = "ted_export_f03_award_consortium_233491-2019.xml"
_LEGACY_OLDGEN = "ted_export_r207_award_oldgen_179996-2013.xml"


def _parse(name: str):
    return parse((_FIXTURES / name).read_bytes())


# ── Envelope: language, SDK version, root TenderResult placeholder ─────────


@pytest.mark.parametrize(
    "fixture, language, sdk, tender_result_date",
    [
        (_CONSORTIUM, "ITA", "eforms-sdk-1.11", "2000-01-01Z"),
        (_FRAMEWORK, "RON", "eforms-sdk-1.6", "2000-01-01+02:00"),
        (_MANY_TENDERS, "HUN", "eforms-sdk-1.7", "2000-01-01Z"),
        (_DE_MODIFICATION, "DEU", "eforms-sdk-1.13", "2000-01-01Z"),
        (_PT_MODIFICATION, "POR", "eforms-sdk-1.14", "2000-01-01Z"),
        (_DE_AWARD, "DEU", "eforms-sdk-1.13", "2000-01-01Z"),
    ],
)
def test_envelope_fields_are_read_verbatim(fixture, language, sdk, tender_result_date):
    """`cbc:NoticeLanguageCode`, `cbc:CustomizationID` and the root
    `cac:TenderResult/cbc:AwardDate` — which every eForms award notice in
    the corpus fills with the 2000-01-01 placeholder — come through as
    written, timezone suffix included."""
    notice = _parse(fixture)
    assert notice.notice_language == language
    assert notice.customization_id == sdk
    assert notice.tender_result_award_date_raw == tender_result_date


# ── SettledContract award date: cleaned AND verbatim ──────────────────────


def test_settled_contract_award_date_keeps_the_published_text():
    """The German award publishes a real date with TED's offset: the
    cleaned field strips it, the raw field keeps it."""
    award = _parse(_DE_AWARD).awards[0]
    assert award.award_date == "2024-06-04"
    assert award.award_date_raw == "2024-06-04+02:00"


def test_award_date_raw_follows_the_contract_not_the_lot():
    """Hungarian EKR names losing bidders. The raw date, like the cleaned
    one, belongs only to the tender the SettledContract references —
    22 winners carry it, 40 losers carry None."""
    notice = _parse(_MANY_TENDERS)
    assert Counter((a.is_winner, a.award_date_raw) for a in notice.awards) == {
        (True, "2024-04-17+02:00"): 22,
        (False, None): 40,
    }


@pytest.mark.parametrize("fixture", [_PT_MODIFICATION, _CONSORTIUM, _FRAMEWORK])
def test_award_date_raw_is_none_when_the_contract_publishes_no_date(fixture):
    """These notices' SettledContracts carry `cbc:IssueDate` only. Absence
    must stay distinguishable from the placeholder: None, not "2000-01-01".
    The Portuguese one matters most — its root TenderResult carries the
    placeholder while its contract carries no award date at all."""
    notice = _parse(fixture)
    assert notice.awards
    assert all(a.award_date is None for a in notice.awards)
    assert all(a.award_date_raw is None for a in notice.awards)


# ── Tender reference ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fixture, reference",
    [
        (_DE_AWARD, "2024_44_B_03.217.01_O"),
        (_DE_MODIFICATION, "2024_44_B_03.217.01_O"),
        (_PT_MODIFICATION, "CO/2019/174"),
    ],
)
def test_tender_reference_is_the_lot_tenders_own_reference(fixture, reference):
    notice = _parse(fixture)
    assert {a.tender_reference for a in notice.awards} == {reference}


def test_tender_reference_is_per_tender():
    """62 LotTenders, 62 distinct EKR references — one per award, none lost
    across the fan-out."""
    notice = _parse(_MANY_TENDERS)
    refs = [a.tender_reference for a in notice.awards]
    assert len(refs) == 62
    assert len(set(refs)) == 62
    assert all(r.startswith("EKR001096352023/") for r in refs)


def test_tender_reference_on_the_italian_consortium_notice():
    notice = _parse(_CONSORTIUM)
    assert {a.tender_reference for a in notice.awards} == {
        "OFFERTA LOTTO 1", "OFFERTA LOTTO 2", "OFFERTA LOTTO 3", "OFFERTA LOTTO 4",
    }


# ── Amount text ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fixture, value, raw",
    [
        # decimals present
        (_PT_MODIFICATION, 189057635.12, "189057635.12"),
        (_DE_AWARD, 263774.0, "263774.00"),
        # no decimals — the same float would erase the difference
        (_CONSORTIUM, 1705713.0, "1705713"),
    ],
)
def test_award_value_raw_is_the_payable_amount_text(fixture, value, raw):
    award = _parse(fixture).awards[0]
    assert award.value == value
    assert award.value_raw == raw


def test_value_raw_records_decimal_presence_per_award():
    """The Romanian framework mixes both shapes in one notice: 240 tenders
    priced without decimals, 32 with. A per-notice flag could not say so."""
    notice = _parse(_FRAMEWORK)
    assert Counter("." in a.value_raw for a in notice.awards) == {False: 240, True: 32}
    assert all(a.value is not None for a in notice.awards)


@pytest.mark.parametrize(
    "fixture, value, raw",
    [
        (_PT_MODIFICATION, 235000000.0, "235000000"),
        (_DE_AWARD, 263774.0, "263774.00"),
        (_MANY_TENDERS, 97750000.0, "97750000.00"),
        (_FRAMEWORK, 14178065.13, "14178065.13"),
        (_CONSORTIUM, None, None),  # publishes no cbc:TotalAmount
    ],
)
def test_total_value_raw_is_the_total_amount_text(fixture, value, raw):
    notice = _parse(fixture)
    assert notice.total_value == value
    assert notice.total_value_raw == raw


@pytest.mark.parametrize(
    "fixture, lot_id, value, raw",
    [
        (_CONSORTIUM, "LOT-0001", 2599081.0, "2599081"),
        (_MANY_TENDERS, "LOT-0001", 4930000.0, "4930000.00"),
        (_FRAMEWORK, "LOT-0001", None, None),  # no per-lot estimate published
    ],
)
def test_lot_estimate_keeps_its_text(fixture, lot_id, value, raw):
    lot = next(l for l in _parse(fixture).lots if l.lot_id == lot_id)
    assert lot.estimated_value == value
    assert lot.estimated_value_raw == raw


@pytest.mark.parametrize(
    "text, expected",
    [
        ("24474133", (24474133.0, "EUR", "24474133")),
        ("24474133.00", (24474133.0, "EUR", "24474133.00")),
        (" 18653880.2 ", (18653880.2, "EUR", "18653880.2")),
        # unparseable: the number is None, the text survives
        ("N/A", (None, "EUR", "N/A")),
        ("   ", (None, None, None)),
    ],
)
def test_read_amount_keeps_the_text_next_to_the_number(text, expected):
    el = etree.fromstring(f'<a currencyID="EUR">{text}</a>')
    assert read_amount(el) == expected


def test_read_amount_absent_element():
    assert read_amount(None) == (None, None, None)


# ── The watermark shape itself (inline: no fixture carries it) ────────────

_NSMAP = " ".join(
    f'xmlns:{p}="{u}"' for p, u in {
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "efac": "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1",
        "efext": "http://data.europa.eu/p27/eforms-ubl-extensions/1",
        "efbc": "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1",
    }.items()
)

# Modelled on the Portuguese gateway's output since its eForms migration:
# placeholder award dates at both levels, a "0.0" tender reference, and an
# amount with no decimals that is ambiguous between /100 and /1000.
WATERMARKED_CAN = f"""<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2"
    {_NSMAP}>
  <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
    <efext:EformsExtension>
      <efac:NoticeResult>
        <cbc:TotalAmount currencyID="EUR">24474133</cbc:TotalAmount>
        <efac:LotResult>
          <cbc:ID schemeName="result">RES-0001</cbc:ID>
          <cbc:TenderResultCode listName="winner-selection-status">selec-w</cbc:TenderResultCode>
          <efac:LotTender><cbc:ID schemeName="tender">TEN-0001</cbc:ID></efac:LotTender>
          <efac:SettledContract><cbc:ID schemeName="contract">CON-0001</cbc:ID></efac:SettledContract>
          <efac:TenderLot><cbc:ID schemeName="Lot">LOT-0000</cbc:ID></efac:TenderLot>
        </efac:LotResult>
        <efac:LotTender>
          <cbc:ID schemeName="tender">TEN-0001</cbc:ID>
          <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="EUR">24474133</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
          <efac:TenderingParty><cbc:ID schemeName="tendering-party">TPA-0001</cbc:ID></efac:TenderingParty>
          <efac:TenderReference><cbc:ID>0.0</cbc:ID></efac:TenderReference>
        </efac:LotTender>
        <efac:SettledContract>
          <cbc:ID schemeName="contract">CON-0001</cbc:ID>
          <cbc:AwardDate>2000-01-01Z</cbc:AwardDate>
          <cbc:IssueDate>2026-03-02+00:00</cbc:IssueDate>
          <efac:LotTender><cbc:ID schemeName="tender">TEN-0001</cbc:ID></efac:LotTender>
        </efac:SettledContract>
        <efac:TenderingParty>
          <cbc:ID schemeName="tendering-party">TPA-0001</cbc:ID>
          <efac:Tenderer><cbc:ID schemeName="organization">ORG-0002</cbc:ID></efac:Tenderer>
        </efac:TenderingParty>
      </efac:NoticeResult>
    </efext:EformsExtension>
  </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
  <cbc:CustomizationID>eforms-sdk-1.14</cbc:CustomizationID>
  <cbc:ID schemeName="notice-id">2a0f5c3e-1111-4c2b-9d4e-646890202600</cbc:ID>
  <cbc:NoticeTypeCode listName="competition">can-standard</cbc:NoticeTypeCode>
  <cbc:NoticeLanguageCode listName="language">POR</cbc:NoticeLanguageCode>
  <cac:TenderResult><cbc:AwardDate>2000-01-01Z</cbc:AwardDate></cac:TenderResult>
</ContractAwardNotice>
""".encode()


def test_watermarked_notice_keeps_the_placeholder_award_date_raw():
    """The cleaned date is nulled exactly as before; the raw keeps the
    placeholder so the census can find the notice."""
    notice = parse(WATERMARKED_CAN)
    assert len(notice.awards) == 1
    award = notice.awards[0]
    assert award.award_date is None
    assert award.award_date_raw == "2000-01-01Z"
    assert award.conclusion_date == "2026-03-02"
    assert notice.tender_result_award_date_raw == "2000-01-01Z"


def test_watermarked_notice_keeps_the_zero_tender_reference():
    assert parse(WATERMARKED_CAN).awards[0].tender_reference == "0.0"


def test_watermarked_notice_keeps_the_undecimalled_amounts():
    notice = parse(WATERMARKED_CAN)
    assert notice.awards[0].value == 24474133.0
    assert notice.awards[0].value_raw == "24474133"
    assert notice.total_value == 24474133.0
    assert notice.total_value_raw == "24474133"
    assert notice.notice_language == "POR"
    assert notice.customization_id == "eforms-sdk-1.14"


def test_raw_fields_default_to_none_on_a_bare_notice():
    """A notice with none of these elements yields None everywhere —
    the fields are additive and never invent a value."""
    xml = b"""<?xml version="1.0"?>
    <ContractAwardNotice
        xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:ID>empty</cbc:ID>
    </ContractAwardNotice>"""
    notice = parse(xml)
    assert notice.notice_language is None
    assert notice.customization_id is None
    assert notice.tender_result_award_date_raw is None
    assert notice.total_value_raw is None


# ── Legacy <TED_EXPORT> path: what exists there, nothing invented ─────────


def test_legacy_f03_award_keeps_the_val_total_text():
    notice = _parse(_LEGACY_SOLE)
    award = notice.awards[0]
    assert award.value == 7361500000.0
    assert award.value_raw == "7361500000.00"
    assert notice.total_value_raw == "7361500000.00"
    # An F03 publishes the conclusion date (V.2.1) only — no award date.
    assert award.award_date_raw is None
    assert award.tender_reference is None
    # LG_ORIG is the two-letter legacy form; the rest has no legacy source.
    assert notice.notice_language == "HU"
    assert notice.customization_id is None
    assert notice.tender_result_award_date_raw is None


def test_legacy_consortium_withholds_the_raw_amount_with_the_value():
    """A joint award's VAL_TOTAL is not booked per winner; the text
    follows the same rule, or a consumer could re-derive the double-count."""
    notice = _parse(_LEGACY_CONSORTIUM)
    assert [a.value for a in notice.awards] == [None, None]
    assert [a.value_raw for a in notice.awards] == [None, None]
    assert notice.total_value_raw == "3850000000"


def test_legacy_oldgen_award_keeps_fmtval_and_the_award_decision_date():
    """R2.0.7: money is VALUE_COST/@FMTVAL (TED-normalised to two decimals,
    so decimal presence is not a signal there) and CONTRACT_AWARD_DATE is
    published as DAY/MONTH/YEAR parts, whose ISO composition is the only
    string form."""
    notice = _parse(_LEGACY_OLDGEN)
    award = notice.awards[0]
    assert award.value == 1860000.0
    assert award.value_raw == "1860000.00"
    assert award.award_date_raw == "2013-05-29"
    assert award.conclusion_date == "2013-05-29"
    assert notice.notice_language == "PL"

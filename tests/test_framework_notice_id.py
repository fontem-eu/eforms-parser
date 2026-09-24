"""The framework grouping key (data-backlog Part 5, C6).

``is_framework`` says a notice belongs to a framework procedure; it says
nothing about WHICH framework, so 152,758 prod contracts carry the flag
and no way to put two of them in the same group. OPT-100 is that missing
datum: the establishing notice and every call-off under it publish the
identical value, and TED indexes it as ``framework-notice-id``.

Every value asserted here was read out of an unmodified TED download.
Three fixtures were added for this feature — 761784-2024 and 3406-2025,
the two published notices of one Polish police car-supply procedure (the
second is a change notice of the first: same ContractFolderID,
``efac:Changes/efbc:ChangedNoticeIdentifier`` = 761784-2024), which
converge on framework ``536632-2024``; and 156-2025, a French award under
framework ``306032-2024``. The fixtures already in the repo cover the
rest: 324264-2024 is a framework notice with no OPT-100, which is the
BT-125 fallback, and 324192-2024 is a non-framework notice whose BT-125
names an unrelated 2023 notice, which is why the fallback is gated. Paths
no fixture carries — SettledContracts that disagree, a UUID-form OPT-100 —
are inline XML.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from eforms.extractors.framework import normalise_framework_notice_id
from eforms.namespaces import NS
from eforms.parser import parse

_FIXTURES = Path(__file__).parent / "fixtures"

# The two published notices of one Polish framework procedure (Komenda
# Wojewódzka Policji w Poznaniu, 4 lots `fa-w-rc`): OPT-100 536632-2024 on
# 7 SettledContracts each, BT-125 the same notice zero-padded.
_PL_AWARD = "eforms_can_framework_ref_pl_761784-2024.xml"
_PL_CHANGE = "eforms_can_framework_ref_pl_3406-2025.xml"
# French award, 2 lots `fa-wo-rc`: OPT-100 306032-2024 while its BT-125
# carries the other value form, a versioned notice UUID.
_FR_AWARD = "eforms_can_framework_ref_fr_156-2025.xml"
# Italian framework (`fa-mix`), no OPT-100, BT-125 790624-2023.
_IT_FRAMEWORK = "eforms_can_consortium_3_tenderers_324264-2024.xml"
# Hungarian award, framework-agreement = none, BT-125 413145-2023.
_HU_NON_FRAMEWORK = "eforms_can_many_tenders_few_named_324192-2024.xml"
# Romanian framework (`fa-wo-rc`) that publishes neither term.
_RO_FRAMEWORK = "eforms_can_framework_multi_supplier_324249-2024.xml"
_DE_AWARD = "eforms_can_standard_de_award_of_562407_201338-2026.xml"
_DE_MODIFICATION = "eforms_can_modif_de_562407-2026.xml"
_PT_MODIFICATION = "eforms_can_modif_pt_orphan_award_540529-2026.xml"
_LEGACY_SOLE = "ted_export_f03_award_sole_winner_217109-2022.xml"
_LEGACY_CONSORTIUM = "ted_export_f03_award_consortium_233491-2019.xml"
_LEGACY_OLDGEN = "ted_export_r207_award_oldgen_179996-2013.xml"

_PL_FRAMEWORK_KEY = "536632-2024"
_FR_FRAMEWORK_KEY = "306032-2024"
# BT-125 of 156-2025: the other value form both terms can take.
_UUID_WITH_VERSION = "45d7e260-cdfb-4ae3-a3d9-fdc8beea8b77-01"
_UUID = "45d7e260-cdfb-4ae3-a3d9-fdc8beea8b77"
_BT_125 = "cac:TenderingProcess/cac:NoticeDocumentReference/cbc:ID"

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


def _xml(name: str) -> etree._Element:
    return etree.fromstring((_FIXTURES / name).read_bytes())


def _notice(*parts: str) -> bytes:
    return f'<?xml version="1.0"?><Root {_NS_DECL}>{"".join(parts)}</Root>'.encode()


def _lot(lot_id: str, fa_code: str) -> str:
    return (
        f'<cac:ProcurementProjectLot><cbc:ID schemeName="Lot">{lot_id}</cbc:ID>'
        "<cac:TenderingProcess><cac:ContractingSystem>"
        '<cbc:ContractingSystemTypeCode listName="framework-agreement">'
        f"{fa_code}</cbc:ContractingSystemTypeCode>"
        "</cac:ContractingSystem></cac:TenderingProcess>"
        "</cac:ProcurementProjectLot>"
    )


def _previous_notice(ref: str) -> str:
    """BT-125 at procedure level."""
    return (
        "<cac:TenderingProcess><cac:NoticeDocumentReference>"
        f"<cbc:ID>{ref}</cbc:ID>"
        "</cac:NoticeDocumentReference></cac:TenderingProcess>"
    )


def _settled(ref: str | None, con_id: str = "CON-0001") -> str:
    """OPT-100 on one SettledContract; ``ref`` None for a contract that
    publishes no reference."""
    reference = (
        f"<cac:NoticeDocumentReference><cbc:ID>{ref}</cbc:ID>"
        "</cac:NoticeDocumentReference>"
    ) if ref is not None else ""
    return (
        f"<efac:SettledContract><cbc:ID>{con_id}</cbc:ID>{reference}"
        "</efac:SettledContract>"
    )


def _result(*settled_contracts: str) -> str:
    body = "".join(settled_contracts)
    return f"{_EXT_OPEN}<efac:NoticeResult>{body}</efac:NoticeResult>{_EXT_CLOSE}"


# ── Real notices: OPT-100 ─────────────────────────────────────────────────


@pytest.mark.parametrize("fixture", [_PL_AWARD, _PL_CHANGE])
def test_both_notices_of_one_framework_converge_on_the_same_key(fixture):
    """The convergence the whole feature rests on: two separately
    published notices, one grouping key."""
    notice = _parse(fixture)
    assert notice.framework_notice_id == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_raw == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_source == "opt-100"
    assert notice.framework_notice_id_conflict is False


def test_the_two_polish_notices_are_distinct_publications():
    """Guards the test above against proving nothing: the pair are two TED
    publications, not one file read twice."""
    award, change = _parse(_PL_AWARD), _parse(_PL_CHANGE)
    assert award.publication_number == "761784-2024"
    assert change.publication_number == "3406-2025"
    assert award.notice_id != change.notice_id
    assert award.is_framework is change.is_framework is True


def test_the_key_is_read_from_the_settled_contract_records_only():
    """761784-2024 holds 14 ``efac:SettledContract`` elements: 7 records
    under the NoticeResult and 7 one-line stubs under the LotResults that
    reference them by id. Only the records carry OPT-100, which is why the
    lookup hangs off the NoticeResult instead of sweeping with `.//`."""
    root = _xml(_PL_AWARD)
    assert len(root.findall(".//efac:SettledContract", NS)) == 14
    assert [
        el.text for el in root.findall(
            ".//efac:SettledContract/cac:NoticeDocumentReference/cbc:ID", NS)
    ] == [_PL_FRAMEWORK_KEY] * 7


def test_the_same_notice_writes_the_key_zero_padded_in_bt_125():
    """761784-2024 publishes one framework under two spellings — OPT-100
    ``536632-2024``, BT-125 ``00536632-2024``. TED's own
    ``framework-notice-id`` index returns both notices of the framework for
    the unpadded form and nothing at all for the padded one, so the padded
    one can never be the key."""
    assert _xml(_PL_AWARD).findtext(_BT_125, namespaces=NS) == "00536632-2024"
    assert normalise_framework_notice_id("00536632-2024") == _PL_FRAMEWORK_KEY
    assert _parse(_PL_AWARD).framework_notice_id == _PL_FRAMEWORK_KEY


def test_french_award_takes_opt_100_over_its_uuid_previous_notice():
    """156-2025 publishes both terms and they name different notices:
    OPT-100 wins and BT-125 is not consulted at all."""
    notice = _parse(_FR_AWARD)
    assert notice.framework_notice_id == _FR_FRAMEWORK_KEY
    assert notice.framework_notice_id_raw == _FR_FRAMEWORK_KEY
    assert notice.framework_notice_id_source == "opt-100"
    assert _xml(_FR_AWARD).findtext(_BT_125, namespaces=NS) == _UUID_WITH_VERSION


# ── Real notices: the gated BT-125 fallback ───────────────────────────────


def test_framework_notice_without_opt_100_falls_back_to_bt_125():
    """The Italian `fa-mix` framework publishes no OPT-100; its
    previous-notice reference is the only key on offer, and on a framework
    procedure that reference is about the framework."""
    notice = _parse(_IT_FRAMEWORK)
    assert notice.is_framework is True
    assert notice.framework_notice_id == "790624-2023"
    assert notice.framework_notice_id_raw == "790624-2023"
    assert notice.framework_notice_id_source == "bt-125"
    assert notice.framework_notice_id_conflict is False


def test_non_framework_notice_never_takes_its_previous_notice():
    """324192-2024 sets framework-agreement = none and still publishes a
    BT-125 (413145-2023, the prior notice of an ordinary procedure).
    Reading it would invent a framework that does not exist."""
    assert _xml(_HU_NON_FRAMEWORK).findtext(_BT_125, namespaces=NS) == "413145-2023"
    notice = _parse(_HU_NON_FRAMEWORK)
    assert notice.is_framework is False
    assert notice.framework_notice_id is None
    assert notice.framework_notice_id_raw is None
    assert notice.framework_notice_id_source is None


@pytest.mark.parametrize(
    "fixture", [_RO_FRAMEWORK, _DE_AWARD, _DE_MODIFICATION, _PT_MODIFICATION])
def test_notices_publishing_neither_term_carry_no_key(fixture):
    """Including a framework one (the Romanian `fa-wo-rc` notice): no key
    published means no key — not an empty string, and not "no framework"."""
    notice = _parse(fixture)
    assert notice.framework_notice_id is None
    assert notice.framework_notice_id_raw is None
    assert notice.framework_notice_id_source is None
    assert notice.framework_notice_id_conflict is False


@pytest.mark.parametrize(
    "fixture", [_LEGACY_SOLE, _LEGACY_CONSORTIUM, _LEGACY_OLDGEN])
def test_legacy_ted_export_notices_have_no_grouping_key(fixture):
    """The pre-eForms S-forms have no framework term of any kind, so every
    legacy notice is a None — absence of a key, not a statement that the
    contract stands outside a framework."""
    notice = _parse(fixture)
    assert notice.framework_notice_id is None
    assert notice.framework_notice_id_raw is None
    assert notice.framework_notice_id_source is None
    assert notice.framework_notice_id_conflict is False


# ── Normalisation ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 761784-2024's two spellings of one framework
        ("00536632-2024", "536632-2024"),
        ("536632-2024", "536632-2024"),
        ("  00536632-2024 ", "536632-2024"),
        # 156-2025's BT-125: the version suffix is not part of the key
        (_UUID_WITH_VERSION, _UUID),
        (f"{_UUID}-02", _UUID),
        (_UUID_WITH_VERSION.upper(), _UUID),
        # a bare UUID is not the documented form: verbatim, still a key
        (_UUID, _UUID),
        # neither form: verbatim beats a rewrite that groups with nothing
        ("FRAMEWORK/2024/017", "FRAMEWORK/2024/017"),
        # ... but an all-zero number groups everything that shares the
        # placeholder into one fabricated framework, so it is no key.
        ("00000000-2025", None),
        ("", None),
        (None, None),
    ],
)
def test_normalise_framework_notice_id(raw, expected):
    assert normalise_framework_notice_id(raw) == expected


def test_bt_125_is_normalised_onto_the_same_key_as_opt_100():
    """The padded BT-125 of 761784-2024, on a notice that publishes no
    OPT-100: the fallback has to land on the same key as the primary term
    or the two sides of a framework never meet."""
    notice = parse(_notice(
        _previous_notice("00536632-2024"), _lot("LOT-0001", "fa-w-rc")))
    assert notice.framework_notice_id == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_raw == "00536632-2024"
    assert notice.framework_notice_id_source == "bt-125"


def test_uuid_form_opt_100_loses_its_version_suffix():
    """A buyer may write the referenced notice's UUID instead of its
    publication number; ``-01`` and ``-02`` of one notice are one
    framework."""
    notice = parse(_notice(_result(_settled(_UUID_WITH_VERSION))))
    assert notice.framework_notice_id == _UUID
    assert notice.framework_notice_id_raw == _UUID_WITH_VERSION
    assert notice.framework_notice_id_source == "opt-100"


# ── Several SettledContracts ──────────────────────────────────────────────


def test_contracts_that_agree_are_not_a_conflict():
    notice = parse(_notice(_result(
        _settled(_PL_FRAMEWORK_KEY, "CON-0001"),
        _settled(_PL_FRAMEWORK_KEY, "CON-0002"),
    )))
    assert notice.framework_notice_id == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_conflict is False


def test_a_padding_difference_within_one_notice_is_not_a_conflict():
    """Counted on the normalised key, so a notice that spells its own
    framework both ways agrees with itself. The raw field keeps the first
    spelling published."""
    notice = parse(_notice(_result(
        _settled("00536632-2024", "CON-0001"),
        _settled(_PL_FRAMEWORK_KEY, "CON-0002"),
    )))
    assert notice.framework_notice_id == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_raw == "00536632-2024"
    assert notice.framework_notice_id_conflict is False


def test_disagreeing_contracts_take_the_most_common_key_and_say_so():
    notice = parse(_notice(_result(
        _settled(_FR_FRAMEWORK_KEY, "CON-0001"),
        _settled(_PL_FRAMEWORK_KEY, "CON-0002"),
        _settled(_PL_FRAMEWORK_KEY, "CON-0003"),
    )))
    assert notice.framework_notice_id == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_raw == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_conflict is True


def test_a_tie_between_contracts_keeps_the_first_published():
    """Deterministic on document order, so one notice never loads under two
    different keys."""
    notice = parse(_notice(_result(
        _settled(_FR_FRAMEWORK_KEY, "CON-0001"),
        _settled(_PL_FRAMEWORK_KEY, "CON-0002"),
    )))
    assert notice.framework_notice_id == _FR_FRAMEWORK_KEY
    assert notice.framework_notice_id_conflict is True


def test_a_contract_without_a_reference_is_not_a_disagreement():
    """Absence is not a competing value. Real notices mix the two: half of
    761784-2024's SettledContract elements carry no reference."""
    notice = parse(_notice(_result(
        _settled(None, "CON-0001"),
        _settled(_PL_FRAMEWORK_KEY, "CON-0002"),
    )))
    assert notice.framework_notice_id == _PL_FRAMEWORK_KEY
    assert notice.framework_notice_id_conflict is False

@pytest.mark.parametrize("raw", ["0-2026", "00000000-2026", "0", "000", "0-0000"])
def test_a_zero_placeholder_is_not_a_key(raw):
    """A key groups notices, so a degenerate one is worse than none:
    every notice publishing the same placeholder would be pulled into
    one fabricated framework agreement. Prod already held "0-2026" from
    an ESP notice (found 2026-09-24 by the normalisation assertion)."""
    assert normalise_framework_notice_id(raw) is None


def test_a_real_reference_survives_the_degenerate_check():
    assert normalise_framework_notice_id("00536632-2024") == "536632-2024"
    assert normalise_framework_notice_id("0000123-2024") == "123-2024"

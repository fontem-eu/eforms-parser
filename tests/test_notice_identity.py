"""Identity stamps read from the notice itself.

These four fields (publication number, procedure id, notice version and the
modification back-link in both of its forms) are what let one ingest path
key a contract the same way whether the notice arrived from a monthly
archive or from the search API. Before 2026-09 the archive path had none
of them, which is how an award and its later modification ended up as two
contracts in the graph.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eforms.extractors.notice_metadata import (
    normalise_publication_number,
    split_back_link,
)
from eforms.parser import parse

_FIXTURES = Path(__file__).parent / "fixtures"

_PT_MODIFICATION = _FIXTURES / "eforms_can_modif_pt_orphan_award_540529-2026.xml"
_DE_MODIFICATION = _FIXTURES / "eforms_can_modif_de_562407-2026.xml"
_DE_AWARD = _FIXTURES / "eforms_can_standard_de_award_of_562407_201338-2026.xml"
_LEGACY_AWARD = _FIXTURES / "ted_export_f03_award_sole_winner_217109-2022.xml"

_DE_PROCEDURE = "5339cf92-c005-4943-86eb-04ece600ed0a"
_DE_AWARD_NOTICE = "a64a67f4-a562-4014-ae25-232da2f4fa1c"


def _parse(path: Path):
    return parse(path.read_bytes())


def test_publication_number_is_stamped_in_ted_form():
    notice = _parse(_PT_MODIFICATION)
    # XML carries 00540529-2026; TED, the graph and every back-link use
    # the unpadded form.
    assert notice.publication_number == "540529-2026"


def test_procedure_id_and_version_are_stamped():
    notice = _parse(_PT_MODIFICATION)
    assert notice.procedure_id == "afc0e4f6-c140-435b-8f60-b1bf37e6860e"
    assert notice.notice_version == "01"
    assert notice.notice_id == "5f0530ee-2f91-494f-9aed-ea56ba4245de"


def test_modification_and_its_award_share_the_procedure_id():
    """The whole point: one contract identity across the chain."""
    modification = _parse(_DE_MODIFICATION)
    award = _parse(_DE_AWARD)
    assert modification.notice_type == "can-modif"
    assert award.notice_type == "can-standard"
    assert modification.procedure_id == award.procedure_id == _DE_PROCEDURE
    assert award.notice_id == _DE_AWARD_NOTICE


def test_back_link_as_publication_number():
    notice = _parse(_PT_MODIFICATION)
    assert notice.modifies_publication_number == "549184-2020"
    assert notice.modifies_notice_id is None


def test_back_link_as_versioned_notice_uuid():
    notice = _parse(_DE_MODIFICATION)
    # Buyer wrote "<uuid>-01": the graph indexes the bare uuid.
    assert notice.modifies_notice_id == _DE_AWARD_NOTICE
    assert notice.modifies_publication_number is None


def test_award_notice_carries_no_back_link():
    award = _parse(_DE_AWARD)
    assert award.modifies_publication_number is None
    assert award.modifies_notice_id is None


def test_legacy_award_keeps_reference_number_as_legacy_procedure_id():
    notice = _parse(_LEGACY_AWARD)
    assert notice.legacy_procedure_id == "EKR001152382021"
    # Legacy notices have no ContractFolderID; identity is the publication
    # number (decision 2026-09-12), so procedure_id stays unset.
    assert notice.procedure_id is None
    assert notice.publication_number == "217109-2022"


def test_eforms_notice_has_no_legacy_procedure_id():
    assert _parse(_DE_AWARD).legacy_procedure_id is None


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("00540529-2026", "540529-2026"),
        ("540529-2026", "540529-2026"),
        ("  00012345-2024 ", "12345-2024"),
        # buyer placeholder: keep it recognisable, never "0-2025"
        ("00000000-2025", "00000000-2025"),
        ("not-a-number", "not-a-number"),
        ("", None),
        (None, None),
    ],
)
def test_normalise_publication_number(raw, expected):
    assert normalise_publication_number(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("549184-2020", ("549184-2020", None)),
        ("00549184-2020", ("549184-2020", None)),
        (
            "A64A67F4-A562-4014-AE25-232DA2F4FA1C-01",
            (None, _DE_AWARD_NOTICE),
        ),
        (f"{_DE_AWARD_NOTICE}-02", (None, _DE_AWARD_NOTICE)),
        # bare uuid without a version is not the documented form: kept verbatim
        (_DE_AWARD_NOTICE, (_DE_AWARD_NOTICE, None)),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_split_back_link(raw, expected):
    assert split_back_link(raw) == expected

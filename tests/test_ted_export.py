"""Tests for the legacy TED (``<TED_EXPORT>``) parser path.

These notices predate eForms (roughly 2023 to mid-2024). The fixture is
a trimmed ``F20_2014`` contract-modification form, wrapped in the
R2.0.9 default namespace so the tests also prove the parser's
namespace-agnostic (``local-name()``) navigation.
"""
from pathlib import Path

from lxml import etree

from eforms.parser import parse
from eforms.ted_export import looks_like_ted_export, parse_ted_export

# Minimal legacy F20 (modification) notice. Namespaced like production
# TED exports so the local-name() lookups are exercised for real.
MODIFICATION_F20 = b"""<?xml version="1.0" encoding="UTF-8"?>
<TED_EXPORT xmlns="http://publications.europa.eu/resource/schema/ted/R2.0.9/publication">
  <CODED_DATA_SECTION>
    <NOTICE_DATA>
      <NO_DOC_OJS>2024/S 010-024047</NO_DOC_OJS>
      <ISO_COUNTRY VALUE="RO"/>
    </NOTICE_DATA>
    <CODIF_DATA>
      <TD_DOCUMENT_TYPE CODE="K">Modification of a contract/concession during its term</TD_DOCUMENT_TYPE>
      <DATE_PUB>20240115</DATE_PUB>
    </CODIF_DATA>
    <REF_NOTICE>
      <NO_DOC_OJS>2017/S 147-305158</NO_DOC_OJS>
    </REF_NOTICE>
  </CODED_DATA_SECTION>
  <FORM_SECTION>
    <F20_2014 LG="RO" CATEGORY="ORIGINAL">
      <CONTRACTING_BODY>
        <ADDRESS_CONTRACTING_BODY>
          <OFFICIALNAME>Municipiul Gheorgheni</OFFICIALNAME>
          <ADDRESS>Piata Libertatii 27</ADDRESS>
          <COUNTRY VALUE="RO"/>
        </ADDRESS_CONTRACTING_BODY>
      </CONTRACTING_BODY>
      <OBJECT_CONTRACT>
        <TITLE><P>Lucrari de modernizare strazi</P></TITLE>
        <CPV_MAIN><CPV_CODE CODE="45000000"/></CPV_MAIN>
      </OBJECT_CONTRACT>
      <AWARD_CONTRACT>
        <LOT_NO>1</LOT_NO>
        <AWARDED_CONTRACT>
          <DATE_CONCLUSION_CONTRACT>20190712</DATE_CONCLUSION_CONTRACT>
          <CONTRACTORS>
            <CONTRACTOR>
              <ADDRESS_CONTRACTOR>
                <OFFICIALNAME>S.C. Fortat-House S.R.L.</OFFICIALNAME>
                <COUNTRY VALUE="RO"/>
              </ADDRESS_CONTRACTOR>
            </CONTRACTOR>
          </CONTRACTORS>
        </AWARDED_CONTRACT>
        <INFO_MODIFICATIONS>
          <VALUES>
            <VAL_TOTAL_BEFORE CURRENCY="RON">2821075.49</VAL_TOTAL_BEFORE>
            <VAL_TOTAL_AFTER CURRENCY="RON">2925919.96</VAL_TOTAL_AFTER>
          </VALUES>
        </INFO_MODIFICATIONS>
      </AWARD_CONTRACT>
    </F20_2014>
  </FORM_SECTION>
</TED_EXPORT>
"""


def _root(xml):
    return etree.fromstring(xml)


def test_looks_like_ted_export_detects_root():
    assert looks_like_ted_export(_root(MODIFICATION_F20)) is True


def test_looks_like_ted_export_rejects_eforms():
    eforms_root = _root(
        b'<ContractAwardNotice '
        b'xmlns="urn:oasis:names:specification:ubl:schema:xsd:'
        b'ContractAwardNotice-2"/>'
    )
    assert looks_like_ted_export(eforms_root) is False


def test_parse_routes_legacy_ted_export():
    """The public entry point must dispatch <TED_EXPORT> to the legacy
    parser — an eForms extractor run would return an empty notice."""
    notice = parse(MODIFICATION_F20)
    assert notice.buyer() is not None
    assert notice.buyer().name == "Municipiul Gheorgheni"


def test_notice_type_from_document_code():
    """TD_DOCUMENT_TYPE CODE='K' -> can-modif."""
    assert parse_ted_export(_root(MODIFICATION_F20)).notice_type == "can-modif"


def test_extracts_notice_metadata():
    notice = parse_ted_export(_root(MODIFICATION_F20))
    assert notice.notice_id == "2024/S 010-024047"
    assert notice.issue_date == "2024-01-15"
    assert notice.cpv_main == "45000000"
    assert notice.title == "Lucrari de modernizare strazi"


def test_buyer_country_from_address_block():
    buyer = parse_ted_export(_root(MODIFICATION_F20)).buyer()
    assert buyer.country == "RO"
    assert buyer.address == "Piata Libertatii 27"


def test_contractor_becomes_award():
    notice = parse_ted_export(_root(MODIFICATION_F20))
    assert len(notice.awards) == 1
    contractors = notice.contractors()
    assert len(contractors) == 1
    assert contractors[0].name == "S.C. Fortat-House S.R.L."
    assert contractors[0].country == "RO"
    assert notice.awards[0].lot_id == "1"
    assert notice.awards[0].conclusion_date == "2019-07-12"


def test_modification_value_prefers_after():
    """VAL_TOTAL_AFTER is the post-modification total — the signal we
    want — and must win over VAL_TOTAL_BEFORE."""
    notice = parse_ted_export(_root(MODIFICATION_F20))
    assert notice.total_value == 2925919.96
    assert notice.modification_value_before == 2821075.49
    assert notice.currency == "RON"


def test_org_ids_are_internal_join_keys():
    """Legacy notices carry no party IDs, so the parser mints synthetic
    ones. buyer_org_id and each award.contractor_org_id must resolve
    within notice.organizations."""
    notice = parse_ted_export(_root(MODIFICATION_F20))
    assert notice.buyer_org_id in notice.organizations
    for award in notice.awards:
        assert award.contractor_org_id in notice.organizations


def test_missing_value_still_parses():
    """A modification with no published value yields total_value None
    but still extracts buyer + contractor (not an error)."""
    xml = MODIFICATION_F20.replace(
        b'<VAL_TOTAL_BEFORE CURRENCY="RON">2821075.49</VAL_TOTAL_BEFORE>', b""
    ).replace(
        b'<VAL_TOTAL_AFTER CURRENCY="RON">2925919.96</VAL_TOTAL_AFTER>', b""
    )
    notice = parse_ted_export(_root(xml))
    assert notice.total_value is None
    assert notice.buyer() is not None
    assert len(notice.awards) == 1


def test_multiple_contractors_yield_multiple_awards():
    xml = MODIFICATION_F20.replace(
        b"</CONTRACTORS>",
        b"""<CONTRACTOR>
              <ADDRESS_CONTRACTOR>
                <OFFICIALNAME>Second Winner SRL</OFFICIALNAME>
                <COUNTRY VALUE="RO"/>
              </ADDRESS_CONTRACTOR>
            </CONTRACTOR></CONTRACTORS>""",
    )
    notice = parse_ted_export(_root(xml))
    assert len(notice.awards) == 2
    names = {c.name for c in notice.contractors()}
    assert names == {"S.C. Fortat-House S.R.L.", "Second Winner SRL"}
    # Synthetic org IDs must stay distinct.
    assert len({a.contractor_org_id for a in notice.awards}) == 2


def test_modifies_publication_number_from_ref_notice():
    """The legacy REF_NOTICE/NO_DOC_OJS (original notice OJS reference) is
    converted to the machine publication-number form, matching the
    modifies_publication_number the eForms path gets from the search API."""
    notice = parse_ted_export(_root(MODIFICATION_F20))
    assert notice.modifies_publication_number == "305158-2017"


def test_modifies_publication_number_absent_when_no_ref():
    """No REF_NOTICE -> modifies_publication_number is None (not an error)."""
    xml = MODIFICATION_F20.replace(
        b"<REF_NOTICE>\n      <NO_DOC_OJS>2017/S 147-305158</NO_DOC_OJS>\n    </REF_NOTICE>\n",
        b"",
    )
    notice = parse_ted_export(_root(xml))
    assert notice.modifies_publication_number is None
    assert notice.buyer() is not None


def test_before_value_none_when_only_after_published():
    """A modification publishing only VAL_TOTAL (no before/after split)
    yields modification_value_before None but a populated total_value."""
    xml = MODIFICATION_F20.replace(
        b'<VAL_TOTAL_BEFORE CURRENCY="RON">2821075.49</VAL_TOTAL_BEFORE>', b""
    ).replace(
        b'<VAL_TOTAL_AFTER CURRENCY="RON">2925919.96</VAL_TOTAL_AFTER>',
        b'<VAL_TOTAL CURRENCY="RON">3000000.00</VAL_TOTAL>',
    )
    notice = parse_ted_export(_root(xml))
    assert notice.modification_value_before is None
    assert notice.total_value == 3000000.00


# ── Real TED award notices (fixtures downloaded from ted.europa.eu) ────────
# The legacy path was written for modifications ("K"); awards were parsed but
# their bidder count and per-award value were never read. Every pre-eForms
# award therefore looked like "competition not disclosed" — a statement about
# this parser, not about the buyer. These fixtures are unmodified TED
# documents, so the tests fail if TED's real shape stops being handled.
_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> bytes:
    return (_FIXTURES / name).read_bytes()


SOLE_WINNER = "ted_export_f03_award_sole_winner_217109-2022.xml"
CONSORTIUM = "ted_export_f03_award_consortium_233491-2019.xml"


def test_real_f03_award_yields_bidder_count_and_value():
    """A real F03 award with one winner: TED publishes
    NB_TENDERS_RECEIVED=2 and VAL_TOTAL=7 361 500 000 HUF."""
    notice = parse(_fixture(SOLE_WINNER))
    assert len(notice.awards) == 1
    award = notice.awards[0]
    assert award.tenders_received == 2, "legacy bidder count must be parsed"
    assert award.value == 7361500000.00
    assert award.currency == "HUF"


def test_real_f03_award_is_not_single_bidder():
    """The regression that matters: this contract was competed (2 tenders).
    Reading None here is what made the platform report it as undisclosed."""
    award = parse(_fixture(SOLE_WINNER)).awards[0]
    assert award.tenders_received is not None
    assert award.tenders_received > 1


def test_real_consortium_award_shares_bidder_count_across_winners():
    """Two contractors jointly win ONE contract (4 tenders received). The
    bidder count is a property of the lot, so every award carries it."""
    notice = parse(_fixture(CONSORTIUM))
    assert len(notice.awards) == 2
    assert [a.tenders_received for a in notice.awards] == [4, 4]


def test_real_consortium_award_does_not_multiply_the_money():
    """The joint award is HUF 3.85bn total. Emitting one Award per winner and
    attaching the full VAL_TOTAL to each would book 7.7bn of public money that
    was never spent — so a non-sole winner carries no value."""
    notice = parse(_fixture(CONSORTIUM))
    assert [a.value for a in notice.awards] == [None, None]
    assert [a.currency for a in notice.awards] == [None, None]


def test_real_award_notice_type_maps_to_eforms_slug():
    """F03 (TD_DOCUMENT_TYPE=7) must map to can-standard, or awards_only()
    drops every legacy award on the floor."""
    assert parse(_fixture(SOLE_WINNER)).notice_type == "can-standard"


# ── The older XML generation (R2.0.7/R2.0.8, roughly 2011-2016) ────────────
# A different dialect entirely: AWARD_OF_CONTRACT / OFFERS_RECEIVED_NUMBER /
# ECONOMIC_OPERATOR_NAME_ADDRESS / VALUE_COST@FMTVAL. The dialects coexist for
# years, so this must parse alongside the F03_2014 shape, not instead of it.
OLDGEN = "ted_export_r207_award_oldgen_179996-2013.xml"


def test_real_oldgen_award_yields_bidder_count():
    """A real 2013 R2.0.7 award: TED publishes OFFERS_RECEIVED_NUMBER=2.
    Without this dialect every 2011-2016 award reads as 'not disclosed'."""
    notice = parse(_fixture(OLDGEN))
    assert notice.awards, "old-generation awards must parse"
    assert notice.awards[0].tenders_received == 2


def test_real_oldgen_award_uses_awarded_value_not_the_estimate():
    """This award carries both INITIAL_ESTIMATED_TOTAL_VALUE_CONTRACT
    (PLN 2 967 317.07) and the awarded COSTS_RANGE_AND_CURRENCY
    (EUR 1 860 000). Booking the estimate would misstate the spend."""
    award = parse(_fixture(OLDGEN)).awards[0]
    assert award.value == 1860000.00
    assert award.currency == "EUR"


def test_real_oldgen_award_names_the_winner():
    notice = parse(_fixture(OLDGEN))
    org = notice.organizations[notice.awards[0].contractor_org_id]
    assert "DECSOFT" in org.name


def test_f03_dialect_still_wins_when_present():
    """Additive, not a cutover: the newer F03 shape must be unaffected."""
    assert parse(_fixture(SOLE_WINNER)).awards[0].tenders_received == 2


def test_real_oldgen_award_has_a_buyer():
    """The loader drops any notice without one — `buyer = notice.buyer();
    if not buyer: return`. The R2.0.7 authority lives in
    CA_CE_CONCESSIONAIRE_PROFILE, not F03's ADDRESS_CONTRACTING_BODY, so
    without it a whole month of award notices emits zero events (12,258 of
    them did exactly that)."""
    notice = parse(_fixture(OLDGEN))
    buyer = notice.buyer()
    assert buyer is not None, "old-generation notices must resolve a buyer"
    assert buyer.name


def test_f03_buyer_still_resolves():
    """The old-gen buyer lookup is a fallback, never a replacement."""
    assert parse(_fixture(SOLE_WINNER)).buyer() is not None

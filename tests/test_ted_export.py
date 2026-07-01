"""Tests for the legacy TED (``<TED_EXPORT>``) parser path.

These notices predate eForms (roughly 2023 to mid-2024). The fixture is
a trimmed ``F20_2014`` contract-modification form, wrapped in the
R2.0.9 default namespace so the tests also prove the parser's
namespace-agnostic (``local-name()``) navigation.
"""
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

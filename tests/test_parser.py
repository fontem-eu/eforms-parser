"""Tests for the main parser entry point using minimal XML fixtures."""
from lxml import etree

from eforms.extractors.organizations import extract_organizations
from eforms.models import Award
from eforms.namespaces import NS
from eforms.parser import parse

# Minimal Contract Award Notice XML — exercises all extractors
MINIMAL_CAN = b"""<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
    xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1"
    xmlns:efbc="http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1">

  <cbc:ID>notice-uuid-001</cbc:ID>
  <cbc:IssueDate>2024-06-15</cbc:IssueDate>
  <cbc:NoticeTypeCode>can-standard</cbc:NoticeTypeCode>

  <cac:ContractingParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>ORG-BUYER</cbc:ID></cac:PartyIdentification>
    </cac:Party>
  </cac:ContractingParty>

  <cac:ProcurementProject>
    <cbc:Name>IT Infrastructure Modernisation</cbc:Name>
    <cbc:Description>Upgrade servers and network</cbc:Description>
    <cac:MainCommodityClassification>
      <cbc:ItemClassificationCode listName="cpv">72000000</cbc:ItemClassificationCode>
    </cac:MainCommodityClassification>
  </cac:ProcurementProject>

  <cac:TenderingProcess>
    <cbc:ProcedureCode listName="procurement-procedure-type">open</cbc:ProcedureCode>
  </cac:TenderingProcess>

  <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
    <efext:EformsExtension>
      <efac:Organizations>
        <efac:Organization>
          <efac:Company>
            <cac:PartyIdentification><cbc:ID>ORG-BUYER</cbc:ID></cac:PartyIdentification>
            <cac:PartyName><cbc:Name>Bundesministerium des Innern</cbc:Name></cac:PartyName>
            <cac:PostalAddress>
              <cbc:CityName>Berlin</cbc:CityName>
              <cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country>
            </cac:PostalAddress>
          </efac:Company>
        </efac:Organization>
        <efac:Organization>
          <efac:Company>
            <cac:PartyIdentification><cbc:ID>ORG-WINNER</cbc:ID></cac:PartyIdentification>
            <cac:PartyName><cbc:Name>SAP SE</cbc:Name></cac:PartyName>
            <cac:PartyLegalEntity><cbc:CompanyID schemeName="VAT">DE143293625</cbc:CompanyID></cac:PartyLegalEntity>
            <cac:PostalAddress>
              <cbc:CityName>Walldorf</cbc:CityName>
              <cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country>
            </cac:PostalAddress>
          </efac:Company>
        </efac:Organization>
      </efac:Organizations>
      <efac:NoticeResult>
        <cbc:TotalAmount currencyID="EUR">12500000</cbc:TotalAmount>
        <efac:LotResult>
          <efac:TenderLot><cbc:ID>LOT-0001</cbc:ID></efac:TenderLot>
          <efac:LotTender><cbc:ID>TEN-0001</cbc:ID></efac:LotTender>
          <efac:SettledContract><cbc:ID>CON-0001</cbc:ID></efac:SettledContract>
        </efac:LotResult>
        <efac:LotTender>
          <cbc:ID>TEN-0001</cbc:ID>
          <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="EUR">12500000</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
          <efac:TenderingParty><cbc:ID>TPA-0001</cbc:ID></efac:TenderingParty>
        </efac:LotTender>
        <efac:SettledContract>
          <cbc:ID>CON-0001</cbc:ID>
          <cbc:AwardDate>2024-06-01</cbc:AwardDate>
        </efac:SettledContract>
        <efac:TenderingParty>
          <cbc:ID>TPA-0001</cbc:ID>
          <efac:Tenderer>
            <cbc:ID schemeName="organization">ORG-WINNER</cbc:ID>
          </efac:Tenderer>
        </efac:TenderingParty>
      </efac:NoticeResult>
    </efext:EformsExtension>
  </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
</ContractAwardNotice>
"""


def test_parse_minimal_can():
    """Parse a minimal Contract Award Notice and verify all fields."""
    notice = parse(MINIMAL_CAN)
    assert notice.notice_id == "notice-uuid-001"
    assert notice.notice_type == "can-standard"
    assert notice.title == "IT Infrastructure Modernisation"
    assert notice.description == "Upgrade servers and network"
    assert notice.cpv_main == "72000000"
    assert notice.procedure_type == "open"
    assert notice.issue_date == "2024-06-15"
    assert notice.total_value == 12500000.0
    assert notice.currency == "EUR"


def test_parse_organizations():
    """Organizations block is parsed and keyed by org ID."""
    notice = parse(MINIMAL_CAN)
    assert len(notice.organizations) == 2
    assert notice.organizations["ORG-BUYER"].name == "Bundesministerium des Innern"
    lid = notice.organizations["ORG-WINNER"].legal_id
    assert lid is not None
    assert lid.value == "DE143293625"
    # schemeName preserved from the XML attribute
    assert lid.scheme_name == "VAT"
    assert notice.organizations["ORG-WINNER"].country == "DE"


def test_parse_legal_id_without_scheme_name():
    """When `cbc:CompanyID` has no @schemeName attribute, scheme_name is None
    but value is still extracted faithfully."""
    ns_decl = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
    xml = f"""<?xml version="1.0"?>
    <Root {ns_decl}>
      <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
        <efext:EformsExtension>
          <efac:Organizations>
            <efac:Organization>
              <efac:Company>
                <cac:PartyIdentification><cbc:ID>ORG-X</cbc:ID></cac:PartyIdentification>
                <cac:PartyName><cbc:Name>Bare ID Co</cbc:Name></cac:PartyName>
                <cac:PartyLegalEntity><cbc:CompanyID>12345</cbc:CompanyID></cac:PartyLegalEntity>
              </efac:Company>
            </efac:Organization>
          </efac:Organizations>
        </efext:EformsExtension>
      </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
    </Root>"""
    orgs = extract_organizations(etree.fromstring(xml.encode()))
    lid = orgs["ORG-X"].legal_id
    assert lid is not None
    assert lid.value == "12345"
    assert lid.scheme_name is None


def test_parse_buyer():
    """buyer() resolves to the contracting authority."""
    notice = parse(MINIMAL_CAN)
    buyer = notice.buyer()
    assert buyer is not None
    assert buyer.name == "Bundesministerium des Innern"


def test_parse_contractors():
    """contractors() resolves to the winning organization."""
    notice = parse(MINIMAL_CAN)
    contractors = notice.contractors()
    assert len(contractors) == 1
    assert contractors[0].name == "SAP SE"
    assert contractors[0].legal_id is not None
    assert contractors[0].legal_id.value == "DE143293625"


def test_parse_awards():
    """Awards link lots to contractors with value and date."""
    notice = parse(MINIMAL_CAN)
    assert len(notice.awards) == 1
    award = notice.awards[0]
    assert award.lot_id == "LOT-0001"
    assert award.contractor_org_id == "ORG-WINNER"
    assert award.value == 12500000.0
    assert award.currency == "EUR"
    assert award.award_date == "2024-06-01"


def test_parse_awards_single_winner_unchanged_by_fan_out():
    """Regression: the single-winner path (one LotResult → one LotTender →
    one Tenderer) must still yield exactly the same one Award after the
    extractor was taught to fan out across multi-tender / consortium
    results. This sample omits cbc:TenderResultCode and cbc:RankCode —
    an unranked, implicitly-selected winner."""
    award = parse(MINIMAL_CAN).awards[0]
    assert award == Award(
        lot_id="LOT-0001",
        contractor_org_id="ORG-WINNER",
        value=12500000.0,
        currency="EUR",
        award_date="2024-06-01",
        conclusion_date=None,
        tenders_received=None,
        rank=None,
        is_winner=True,
        tendering_party_id="TPA-0001",
        is_consortium_member=False,
    )


def test_parse_empty_xml():
    """Minimal XML with no content produces a Notice with empty fields."""
    xml = b"""<?xml version="1.0"?>
    <ContractAwardNotice
        xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
      <cbc:ID>empty</cbc:ID>
    </ContractAwardNotice>"""
    notice = parse(xml)
    assert notice.notice_id == "empty"
    assert notice.title is None
    assert not notice.organizations
    assert not notice.awards


# Standalone fixture — regional-award XML with NUTS on both the notice's
# place-of-performance and on the buyer authority's postal address.
MINIMAL_CAN_WITH_NUTS = b"""<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice
    xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2"
    xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
    xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
    xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
    xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
    xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1">
  <cbc:ID>notice-uuid-nuts</cbc:ID>
  <cac:ProcurementProject>
    <cbc:Name>Regional road works</cbc:Name>
    <cac:RealizedLocation>
      <cac:Address>
        <cbc:CountrySubentityCode listName="nuts">PT170</cbc:CountrySubentityCode>
      </cac:Address>
    </cac:RealizedLocation>
  </cac:ProcurementProject>
  <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
    <efext:EformsExtension>
      <efac:Organizations>
        <efac:Organization>
          <efac:Company>
            <cac:PartyIdentification><cbc:ID>ORG-CM</cbc:ID></cac:PartyIdentification>
            <cac:PartyName><cbc:Name>Camara Municipal de Lisboa</cbc:Name></cac:PartyName>
            <cac:PostalAddress>
              <cbc:CityName>Lisboa</cbc:CityName>
              <cbc:CountrySubentityCode listName="nuts">PT170</cbc:CountrySubentityCode>
              <cac:Country><cbc:IdentificationCode>PT</cbc:IdentificationCode></cac:Country>
            </cac:PostalAddress>
          </efac:Company>
        </efac:Organization>
      </efac:Organizations>
    </efext:EformsExtension>
  </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
</ContractAwardNotice>
"""


def test_parse_extracts_place_of_performance_nuts():
    """NUTS on the ProcurementProject's RealizedLocation lands on Notice.nuts."""
    notice = parse(MINIMAL_CAN_WITH_NUTS)
    assert notice.nuts == "PT170"


def test_parse_extracts_authority_nuts_from_postal_address():
    """NUTS on the contracting authority's PostalAddress lands on Organization.nuts."""
    notice = parse(MINIMAL_CAN_WITH_NUTS)
    org = notice.organizations.get("ORG-CM")
    assert org is not None
    assert org.nuts == "PT170"


def test_parse_returns_none_nuts_when_absent():
    """MINIMAL_CAN has no CountrySubentityCode anywhere — both fields stay None."""
    notice = parse(MINIMAL_CAN)
    assert notice.nuts is None
    for org in notice.organizations.values():
        assert org.nuts is None
def test_parse_integrity_fields():
    """Award criteria, submission deadline, framework flag and EU funding
    are extracted from the standard eForms locations."""
    ns_decl = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
    xml = f"""<?xml version="1.0"?>
    <Root {ns_decl}>
      <cac:TenderingTerms>
        <cac:AwardingTerms><cac:AwardingCriterion>
          <cac:SubordinateAwardingCriterion>
            <cbc:AwardingCriterionTypeCode listName="award-criterion-type">price</cbc:AwardingCriterionTypeCode>
          </cac:SubordinateAwardingCriterion>
          <cac:SubordinateAwardingCriterion>
            <cbc:AwardingCriterionTypeCode listName="award-criterion-type">quality</cbc:AwardingCriterionTypeCode>
          </cac:SubordinateAwardingCriterion>
        </cac:AwardingCriterion></cac:AwardingTerms>
      </cac:TenderingTerms>
      <cac:TenderingProcess>
        <cac:ContractingSystem>
          <cbc:ContractingSystemTypeCode listName="framework-agreement">fa-wo-rc</cbc:ContractingSystemTypeCode>
        </cac:ContractingSystem>
        <cac:TenderSubmissionDeadlinePeriod><cbc:EndDate>2024-05-01+02:00</cbc:EndDate></cac:TenderSubmissionDeadlinePeriod>
      </cac:TenderingProcess>
      <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent><efext:EformsExtension>
        <efac:Funding><cbc:FundingProgramCode>EUFUNDS_RRF</cbc:FundingProgramCode></efac:Funding>
      </efext:EformsExtension></ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
    </Root>""".encode()
    notice = parse(xml)
    assert notice.award_criterion_type == "meat"   # price + quality → MEAT
    assert notice.submission_deadline == "2024-05-01"
    assert notice.is_framework is True
    assert notice.eu_funded is True
    assert notice.funding_programme == "EUFUNDS_RRF"


def test_award_criterion_price_only():
    ns_decl = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
    xml = f"""<?xml version="1.0"?>
    <Root {ns_decl}><cac:TenderingTerms><cac:AwardingTerms><cac:AwardingCriterion>
      <cac:SubordinateAwardingCriterion>
        <cbc:AwardingCriterionTypeCode listName="award-criterion-type">price</cbc:AwardingCriterionTypeCode>
      </cac:SubordinateAwardingCriterion>
    </cac:AwardingCriterion></cac:AwardingTerms></cac:TenderingTerms></Root>""".encode()
    assert parse(xml).award_criterion_type == "price"


def test_extract_lot_tender_counts():
    from eforms.extractors.awards import extract_lot_tender_counts  # pylint: disable=import-outside-toplevel
    ns_decl = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
    xml = f"""<?xml version="1.0"?>
    <Root {ns_decl}>
      <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent><efext:EformsExtension>
        <efac:NoticeResult>
          <efac:LotResult>
            <efac:TenderLot><cbc:ID>LOT-0001</cbc:ID></efac:TenderLot>
            <efac:ReceivedSubmissionsStatistics>
              <efbc:StatisticsCode listName="received-submission-type">tenders</efbc:StatisticsCode>
              <efbc:StatisticsNumeric>1</efbc:StatisticsNumeric>
            </efac:ReceivedSubmissionsStatistics>
          </efac:LotResult>
        </efac:NoticeResult>
      </efext:EformsExtension></ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
    </Root>""".encode()
    counts = extract_lot_tender_counts(etree.fromstring(xml))
    assert counts == {"LOT-0001": 1}   # single bidder


def test_zero_tenders_treated_as_unrecorded():
    from eforms.extractors.awards import extract_lot_tender_counts  # pylint: disable=import-outside-toplevel
    ns_decl = " ".join(f'xmlns:{p}="{u}"' for p, u in NS.items())
    body = (
        "<ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>"
        "<efext:EformsExtension><efac:NoticeResult><efac:LotResult>"
        "<efac:TenderLot><cbc:ID>LOT-0001</cbc:ID></efac:TenderLot>"
        "<efac:ReceivedSubmissionsStatistics>"
        "<efbc:StatisticsCode listName=\"received-submission-type\">tenders</efbc:StatisticsCode>"
        "<efbc:StatisticsNumeric>0</efbc:StatisticsNumeric>"
        "</efac:ReceivedSubmissionsStatistics>"
        "</efac:LotResult></efac:NoticeResult></efext:EformsExtension>"
        "</ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>"
    )
    xml = f'<?xml version="1.0"?><Root {ns_decl}>{body}</Root>'.encode()
    # 0 received tenders on an awarded lot is contradictory -> not recorded.
    assert not extract_lot_tender_counts(etree.fromstring(xml))


NSMAP_MIN = (
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonBasicComponents-2" '
    'xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:'
    'CommonExtensionComponents-2" '
    'xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1" '
    'xmlns:efbc="http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1" '
    'xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1"'
)


def _stats_notice(stats_xml: str) -> bytes:
    """Minimal ContractAwardNotice wrapping one LotResult's statistics."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ContractAwardNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:ContractAwardNotice-2" {NSMAP_MIN}>
  <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
    <efext:EformsExtension><efac:NoticeResult>
      <efac:LotResult>
        <efac:TenderLot><cbc:ID schemeName="Lot">LOT-0001</cbc:ID></efac:TenderLot>
        {stats_xml}
      </efac:LotResult>
    </efac:NoticeResult></efext:EformsExtension>
  </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
</ContractAwardNotice>'''.encode()


def test_tender_counts_accepts_t_esubm_fallback():
    # Real-world shape (audit 2026-07-26, e.g. TED 449053-2026): only the
    # electronic-submissions total is published. It must be used.
    from eforms.extractors.awards import extract_lot_tender_counts  # pylint: disable=import-outside-toplevel
    xml = _stats_notice(
        '<efac:ReceivedSubmissionsStatistics>'
        '<efbc:StatisticsCode listName="received-submission-type">t-esubm'
        '</efbc:StatisticsCode>'
        '<efbc:StatisticsNumeric>4</efbc:StatisticsNumeric>'
        '</efac:ReceivedSubmissionsStatistics>')
    counts = extract_lot_tender_counts(etree.fromstring(xml))
    assert counts == {"LOT-0001": 4}


def test_tender_counts_plain_total_beats_electronic():
    from eforms.extractors.awards import extract_lot_tender_counts  # pylint: disable=import-outside-toplevel
    xml = _stats_notice(
        '<efac:ReceivedSubmissionsStatistics>'
        '<efbc:StatisticsCode listName="received-submission-type">t-esubm'
        '</efbc:StatisticsCode>'
        '<efbc:StatisticsNumeric>3</efbc:StatisticsNumeric>'
        '</efac:ReceivedSubmissionsStatistics>'
        '<efac:ReceivedSubmissionsStatistics>'
        '<efbc:StatisticsCode listName="received-submission-type">tenders'
        '</efbc:StatisticsCode>'
        '<efbc:StatisticsNumeric>5</efbc:StatisticsNumeric>'
        '</efac:ReceivedSubmissionsStatistics>')
    counts = extract_lot_tender_counts(etree.fromstring(xml))
    assert counts == {"LOT-0001": 5}


def test_tender_counts_subgroup_codes_never_count():
    # t-sme is a subgroup, not a total — a notice publishing only
    # subgroups still has no usable count.
    from eforms.extractors.awards import extract_lot_tender_counts  # pylint: disable=import-outside-toplevel
    xml = _stats_notice(
        '<efac:ReceivedSubmissionsStatistics>'
        '<efbc:StatisticsCode listName="received-submission-type">t-sme'
        '</efbc:StatisticsCode>'
        '<efbc:StatisticsNumeric>2</efbc:StatisticsNumeric>'
        '</efac:ReceivedSubmissionsStatistics>')
    counts = extract_lot_tender_counts(etree.fromstring(xml))
    assert counts == {}


def test_tender_counts_zero_still_skipped():
    from eforms.extractors.awards import extract_lot_tender_counts  # pylint: disable=import-outside-toplevel
    xml = _stats_notice(
        '<efac:ReceivedSubmissionsStatistics>'
        '<efbc:StatisticsCode listName="received-submission-type">t-esubm'
        '</efbc:StatisticsCode>'
        '<efbc:StatisticsNumeric>0</efbc:StatisticsNumeric>'
        '</efac:ReceivedSubmissionsStatistics>')
    counts = extract_lot_tender_counts(etree.fromstring(xml))
    assert counts == {}

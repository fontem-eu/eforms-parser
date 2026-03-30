"""Tests for the main parser entry point using minimal XML fixtures."""
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
            <cac:PartyLegalEntity><cbc:CompanyID>DE143293625</cbc:CompanyID></cac:PartyLegalEntity>
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
    assert notice.organizations["ORG-WINNER"].legal_id == "DE143293625"
    assert notice.organizations["ORG-WINNER"].country == "DE"


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
    assert contractors[0].legal_id == "DE143293625"


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
    assert notice.organizations == {}
    assert notice.awards == []

"""Extract award results — lot→tender→contractor mapping + values."""
from __future__ import annotations

from lxml import etree

from ..models import Award
from ..namespaces import NS
from .notice_metadata import _clean_date

_CBC_ID = "cbc:ID"

_RESULT_PATH = (
    ".//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension/efac:NoticeResult"
)


def extract_total_value(root: etree._Element) -> tuple[float | None, str | None]:
    """Extract the notice-level total award value and currency."""
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return None, None
    amount_el = result_el.find("cbc:TotalAmount", NS)
    if amount_el is None or not amount_el.text:
        return None, None
    try:
        value = float(amount_el.text.strip())
    except ValueError:
        return None, None
    currency = amount_el.get("currencyID")
    return value, currency


def extract_lot_tender_counts(root: etree._Element) -> dict[str, int]:
    """lot_id -> number of tenders received, from each LotResult's
    ReceivedSubmissionsStatistics (the 'tenders' total). Drives the
    single-bidder indicator."""
    counts: dict[str, int] = {}
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return counts
    for lot_result in result_el.findall("efac:LotResult", NS):
        lot_id_el = lot_result.find("efac:TenderLot/cbc:ID", NS)
        if lot_id_el is None or not lot_id_el.text:
            continue
        lot_id = lot_id_el.text.strip()
        for stat in lot_result.findall("efac:ReceivedSubmissionsStatistics", NS):
            code = (stat.findtext(
                "efbc:StatisticsCode", default="", namespaces=NS) or "").strip().lower()
            num = (stat.findtext(
                "efbc:StatisticsNumeric", default="", namespaces=NS) or "").strip()
            if code == "tenders" and num.isdigit():
                counts[lot_id] = int(num)
                break
    return counts


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
# The eForms award extraction walks a 4-step indirection chain
# (TenderingParty → LotTender → SettledContract → LotResult) and the
# locals/branches needed to bridge those XPath joins are intrinsic to
# the schema. Splitting it produces helpers that take 6+ context
# args and obscure the single linear extraction pass.
def extract_awards(root: etree._Element) -> list[Award]:
    """Extract per-lot award results.

    Real eForms structure (indirection chain):
      TenderingParty (TPA-0001) → Tenderer → org ID (ORG-0002)
      LotTender (TEN-0001) → TenderingParty ref (TPA-0001), has value
      SettledContract (CON-0001) → has AwardDate
      LotResult → refs LotTender, TenderLot, SettledContract
    """
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return []

    # Step 1: Build TenderingParty ID → org ID mapping
    tpa_to_org: dict[str, str] = {}
    for tpa in result_el.findall("efac:TenderingParty", NS):
        tpa_id_el = tpa.find(_CBC_ID, NS)
        if tpa_id_el is None or not tpa_id_el.text:
            continue
        tpa_id = tpa_id_el.text.strip()
        tenderer = tpa.find("efac:Tenderer/cbc:ID", NS)
        if tenderer is not None and tenderer.text:
            tpa_to_org[tpa_id] = tenderer.text.strip()

    # Step 2: Build LotTender ID → (TenderingParty ref, value, currency)
    tender_info: dict[str, dict] = {}
    for lt in result_el.findall("efac:LotTender", NS):
        lt_id_el = lt.find(_CBC_ID, NS)
        if lt_id_el is None or not lt_id_el.text:
            continue
        lt_id = lt_id_el.text.strip()

        tpa_ref_el = lt.find("efac:TenderingParty/cbc:ID", NS)
        tpa_ref = (
            tpa_ref_el.text.strip()
            if tpa_ref_el is not None and tpa_ref_el.text
            else None
        )

        value = None
        currency = None
        val_el = lt.find("cac:LegalMonetaryTotal/cbc:PayableAmount", NS)
        if val_el is not None and val_el.text:
            try:
                value = float(val_el.text.strip())
            except ValueError:
                pass
            currency = val_el.get("currencyID")

        tender_info[lt_id] = {
            "tpa_ref": tpa_ref,
            "value": value,
            "currency": currency,
        }

    # Step 3: Build SettledContract ID → (award date, conclusion date)
    contract_dates: dict[str, str] = {}
    contract_conclusion: dict[str, str] = {}
    for sc in result_el.findall("efac:SettledContract", NS):
        sc_id_el = sc.find(_CBC_ID, NS)
        if sc_id_el is None or not sc_id_el.text:
            continue
        sc_id = sc_id_el.text.strip()
        date_el = sc.find("cbc:AwardDate", NS)
        if date_el is not None and date_el.text:
            cleaned = _clean_date(date_el.text.strip())
            if cleaned:
                contract_dates[sc_id] = cleaned
        # Contract conclusion/signing date (IssueDate on SettledContract)
        issue_el = sc.find("cbc:IssueDate", NS)
        if issue_el is not None and issue_el.text:
            cleaned = _clean_date(issue_el.text.strip())
            if cleaned:
                contract_conclusion[sc_id] = cleaned

    # Step 4: Assemble awards from LotResult
    awards: list[Award] = []
    for lr in result_el.findall("efac:LotResult", NS):
        lot_id_el = lr.find("efac:TenderLot/cbc:ID", NS)
        tender_ref_el = lr.find("efac:LotTender/cbc:ID", NS)
        contract_ref_el = lr.find("efac:SettledContract/cbc:ID", NS)

        if lot_id_el is None or tender_ref_el is None:
            continue

        lot_id = lot_id_el.text.strip() if lot_id_el.text else ""
        tender_id = tender_ref_el.text.strip() if tender_ref_el.text else ""

        # Resolve: LotTender → TenderingParty → Org
        info = tender_info.get(tender_id, {})
        tpa_ref = info.get("tpa_ref", "")
        org_id = tpa_to_org.get(tpa_ref, "")

        # Value from LotTender
        value = info.get("value")
        currency = info.get("currency")

        # Award date + conclusion date from SettledContract
        award_date = None
        conclusion_date = None
        if contract_ref_el is not None and contract_ref_el.text:
            sc_ref = contract_ref_el.text.strip()
            award_date = contract_dates.get(sc_ref)
            conclusion_date = contract_conclusion.get(sc_ref)

        if org_id:
            awards.append(Award(
                lot_id=lot_id,
                contractor_org_id=org_id,
                value=value,
                currency=currency,
                award_date=award_date,
                conclusion_date=conclusion_date,
            ))

    return awards

"""Extract award results — lot→tender→contractor mapping + values."""
from __future__ import annotations

from lxml import etree

from ..models import Award
from ..namespaces import NS

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


def extract_awards(root: etree._Element) -> list[Award]:
    """Extract per-lot award results."""
    result_el = root.find(_RESULT_PATH, NS)
    if result_el is None:
        return []

    # Build tender_id → contractor org_id mapping
    tender_to_contractor: dict[str, str] = {}
    for tender in result_el.findall("efac:LotTender", NS):
        tender_id_el = tender.find("cbc:ID", NS)
        if tender_id_el is None or not tender_id_el.text:
            continue
        tid = tender_id_el.text.strip()
        for tp in tender.findall("efac:TenderingParty", NS):
            for tenderer in tp.findall("efac:Tenderer", NS):
                org_el = tenderer.find(
                    "cbc:ID[@schemeName='organization']", NS
                )
                if org_el is not None and org_el.text:
                    tender_to_contractor[tid] = org_el.text.strip()

    # Build lot results
    awards: list[Award] = []
    for lot_result in result_el.findall("efac:LotResult", NS):
        lot_id_el = lot_result.find(
            "efac:TenderLot/cbc:ID", NS
        )
        tender_id_el = lot_result.find(
            "efac:LotTender/cbc:ID", NS
        )
        if lot_id_el is None or tender_id_el is None:
            continue

        lot_id = lot_id_el.text.strip() if lot_id_el.text else ""
        tender_id = tender_id_el.text.strip() if tender_id_el.text else ""
        contractor_org_id = tender_to_contractor.get(tender_id, "")

        # Award value
        value = None
        currency = None
        settled = lot_result.find("efac:SettledContract", NS)
        if settled is not None:
            val_el = settled.find(
                "cac:LegalMonetaryTotal/cbc:PayableAmount", NS
            )
            if val_el is not None and val_el.text:
                try:
                    value = float(val_el.text.strip())
                except ValueError:
                    pass
                currency = val_el.get("currencyID")

        # Award date
        award_date = None
        date_el = lot_result.find("cbc:AwardDate", NS)
        if date_el is not None and date_el.text:
            award_date = date_el.text.strip()

        if contractor_org_id:
            awards.append(Award(
                lot_id=lot_id,
                contractor_org_id=contractor_org_id,
                value=value,
                currency=currency,
                award_date=award_date,
            ))

    return awards

"""Extract lot-level metadata."""
from __future__ import annotations

from lxml import etree

from ..models import Lot
from ..namespaces import NS


def extract_lots(root: etree._Element) -> list[Lot]:
    """Extract all lots from the procurement project."""
    lots: list[Lot] = []
    for lot_el in root.findall(".//cac:ProcurementProjectLot", NS):
        lot_id_el = lot_el.find("cbc:ID", NS)
        if lot_id_el is None or not lot_id_el.text:
            continue
        lot_id = lot_id_el.text.strip()

        proj = lot_el.find("cac:ProcurementProject", NS)
        title = None
        cpv = None
        value = None
        currency = None

        if proj is not None:
            title_el = proj.find("cbc:Name", NS)
            title = (
                title_el.text.strip()
                if title_el is not None and title_el.text
                else None
            )
            cpv_el = proj.find(
                "cac:MainCommodityClassification/"
                "cbc:ItemClassificationCode[@listName='cpv']",
                NS,
            )
            cpv = (
                cpv_el.text.strip()
                if cpv_el is not None and cpv_el.text
                else None
            )
            val_el = proj.find(
                "cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount",
                NS,
            )
            if val_el is not None and val_el.text:
                try:
                    value = float(val_el.text.strip())
                except ValueError:
                    pass
                currency = val_el.get("currencyID")

        lots.append(Lot(
            lot_id=lot_id,
            title=title,
            cpv=cpv,
            estimated_value=value,
            currency=currency,
        ))
    return lots

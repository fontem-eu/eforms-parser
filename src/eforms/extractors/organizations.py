"""Extract organizations block → dict[org_id, Organization]."""
from __future__ import annotations

from lxml import etree

from ..models import Organization
from ..namespaces import NS

_ORG_PATH = (
    ".//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension/efac:Organizations/efac:Organization"
)


def extract_organizations(
    root: etree._Element,
) -> dict[str, Organization]:
    """Parse all organizations and return a dict keyed by org ID."""
    result: dict[str, Organization] = {}
    for org_el in root.findall(_ORG_PATH, NS):
        company = org_el.find("efac:Company", NS)
        if company is None:
            continue

        org_id_el = company.find("cac:PartyIdentification/cbc:ID", NS)
        if org_id_el is None or not org_id_el.text:
            continue
        org_id = org_id_el.text.strip()

        name_el = company.find("cac:PartyName/cbc:Name", NS)
        name = name_el.text.strip() if name_el is not None and name_el.text else ""

        country_el = company.find(
            "cac:PostalAddress/cac:Country/cbc:IdentificationCode", NS
        )
        country = (
            country_el.text.strip()
            if country_el is not None and country_el.text
            else None
        )

        legal_id_el = company.find(
            "cac:PartyLegalEntity/cbc:CompanyID", NS
        )
        legal_id = (
            legal_id_el.text.strip()
            if legal_id_el is not None and legal_id_el.text
            else None
        )

        address_parts = []
        for tag in ("cbc:StreetName", "cbc:CityName", "cbc:PostalZone"):
            el = company.find(f"cac:PostalAddress/{tag}", NS)
            if el is not None and el.text:
                address_parts.append(el.text.strip())
        address = ", ".join(address_parts) if address_parts else None

        result[org_id] = Organization(
            org_id=org_id,
            name=name,
            country=country,
            legal_id=legal_id,
            address=address,
        )
    return result

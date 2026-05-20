"""Extract organizations block → dict[org_id, Organization]."""
from __future__ import annotations

from lxml import etree

from ..models import LegalIdentifier, Organization
from ..namespaces import NS

_ORG_PATH = (
    ".//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension/efac:Organizations/efac:Organization"
)


def extract_organizations(
    root: etree._Element,
) -> dict[str, Organization]:
    """Parse all organizations and return a dict keyed by org ID."""
    # pylint: disable=too-many-locals
    # Organization extraction reads ~15 optional UBL/EFAC subfields
    # (id, name, address parts, legal id + scheme, contact); the
    # locals correspond 1-to-1 to schema fields, splitting them off
    # buys no clarity.
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

        # Preserve both the text content and the `@schemeName` attribute
        # (which may label the value as "VAT", "national", "EORI", etc.).
        # Consumers route on scheme_name; we don't interpret it here.
        legal_id_el = company.find(
            "cac:PartyLegalEntity/cbc:CompanyID", NS
        )
        if legal_id_el is not None and legal_id_el.text:
            legal_id: LegalIdentifier | None = LegalIdentifier(
                value=legal_id_el.text.strip(),
                scheme_name=legal_id_el.get("schemeName"),
            )
        else:
            legal_id = None

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

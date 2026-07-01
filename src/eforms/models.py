"""Dataclasses representing parsed eForms notice structures."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LegalIdentifier:
    """Verbatim content of an eForms `cbc:CompanyID` element.

    The XML may carry a `@schemeName` attribute that labels what the value
    IS (e.g. "VAT", "national", "EORI", or a publisher-defined string).
    We preserve both fields exactly as they appear in the source. No
    validation, no interpretation — consumers decide what to do with it.
    """

    value: str
    scheme_name: str | None = None


@dataclass
class Organization:
    """A party (buyer, contractor, etc.) referenced within a notice."""

    org_id: str
    name: str
    country: str | None = None
    legal_id: LegalIdentifier | None = None
    address: str | None = None


@dataclass
class Lot:
    """A single lot within a procurement procedure."""

    lot_id: str
    title: str | None = None
    cpv: str | None = None
    estimated_value: float | None = None
    currency: str | None = None


@dataclass
class Award:
    """A lot-level award result linking a lot to a winning contractor."""

    lot_id: str
    contractor_org_id: str
    value: float | None = None
    currency: str | None = None
    award_date: str | None = None
    conclusion_date: str | None = None  # contract signing/conclusion date
    tenders_received: int | None = None  # bidder count for the award's lot


@dataclass
class Notice:  # pylint: disable=too-many-instance-attributes
    """A fully parsed eForms notice with resolved org references.

    The 15 fields mirror the eForms top-level notice schema 1:1 —
    every field is a distinct semantic UBL element, not a candidate
    for grouping. Splitting would force callers to learn an artificial
    intermediate object hierarchy.
    """

    notice_id: str
    publication_number: str | None = None
    notice_type: str | None = None
    title: str | None = None
    description: str | None = None
    cpv_main: str | None = None
    procedure_type: str | None = None
    issue_date: str | None = None
    dispatch_date: str | None = None  # when notice was sent to TED
    buyer_org_id: str | None = None
    total_value: float | None = None
    currency: str | None = None
    # Tender-integrity fields (inputs to the EC Single Market Scoreboard /
    # DIGIWHIST CRI red flags). All Optional — older notices omit them.
    award_criterion_type: str | None = None   # price | cost | quality
    submission_deadline: str | None = None    # tender submission cut-off
    is_framework: bool | None = None          # framework agreement?
    eu_funded: bool | None = None             # any EU co-financing declared
    funding_programme: str | None = None      # e.g. cohesion / RRF programme code
    # Contract-modification specifics. Legacy TED F20 modification
    # notices self-contain the pre-modification total; the modified
    # (after) total lands in ``total_value``. ``modifies_publication_number``
    # is the publication-number of the notice this one modifies.
    modification_value_before: float | None = None
    modifies_publication_number: str | None = None
    organizations: dict[str, Organization] = field(default_factory=dict)
    lots: list[Lot] = field(default_factory=list)
    awards: list[Award] = field(default_factory=list)

    def buyer(self) -> Organization | None:
        """Return the buying authority, or None if not resolvable."""
        if self.buyer_org_id and self.buyer_org_id in self.organizations:
            return self.organizations[self.buyer_org_id]
        return None

    def contractors(self) -> list[Organization]:
        """Return all winning contractors across all awards."""
        return [
            self.organizations[a.contractor_org_id]
            for a in self.awards
            if a.contractor_org_id in self.organizations
        ]

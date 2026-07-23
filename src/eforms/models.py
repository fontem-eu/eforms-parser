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
    nuts: str | None = None


@dataclass
class Lot:
    """A single lot within a procurement procedure."""

    lot_id: str
    title: str | None = None
    cpv: str | None = None
    estimated_value: float | None = None
    currency: str | None = None


@dataclass
class Award:  # pylint: disable=too-many-instance-attributes
    """A lot-level award result linking a lot to one named contractor.

    One Award is emitted per (LotResult × referenced LotTender × named
    Tenderer). A single lot therefore yields several Awards when the
    LotResult references several LotTenders (multi-supplier framework
    agreements / ranked cascades) or when the winning TenderingParty is
    a consortium of joint bidders.

    The 11 fields are a flat record of one eForms award row — each is a
    distinct published datum (identity, money, dates, rank, provenance
    flags), not a candidate for grouping. Nesting them would force every
    consumer through an artificial object hierarchy for no gain.
    """

    lot_id: str
    contractor_org_id: str
    value: float | None = None
    currency: str | None = None
    award_date: str | None = None
    conclusion_date: str | None = None  # contract signing/conclusion date
    tenders_received: int | None = None  # bidder count for the award's lot
    # Position in a ranked cascade (eForms `cbc:RankCode` on the
    # LotTender). None when the notice does not rank its tenders.
    rank: int | None = None
    # Whether this tender actually won. When the notice emits any
    # SettledContract→LotTender reference, winners are exactly the
    # referenced tenders (Hungarian EKR / Swedish eSenders attach ALL
    # received tenders — including named losers — to the `selec-w`
    # LotResult, so the result code alone is not trustworthy). Notices
    # without such references fall back to the LotResult's
    # `cbc:TenderResultCode` == "selec-w" rule; notices that omit the
    # code predate the field and only ever record winners (default True).
    #
    # For non-winner awards, `value` is the losing BID amount — NOT an
    # award value. Consumers must exclude non-winners when summing
    # contract totals, and `award_date`/`conclusion_date` are None for
    # them (a loser is not party to the settled contract).
    is_winner: bool = True
    tendering_party_id: str | None = None
    # True when this contractor bid as part of a multi-member
    # TenderingParty (consortium). Every member of the consortium carries
    # the SAME `value` — the full tender price, which is not divisible
    # across members by any published figure. Consumers aggregating money
    # MUST deduplicate by (tendering_party_id, lot_id) rather than summing
    # Awards, or consortium tenders inflate totals N-fold.
    is_consortium_member: bool = False


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
    # Place-of-performance NUTS (from ProcurementProject/RealizedLocation).
    nuts: str | None = None
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

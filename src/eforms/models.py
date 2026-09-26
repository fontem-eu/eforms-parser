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
    # Verbatim text ``estimated_value`` was parsed from
    # (``cbc:EstimatedOverallContractAmount``): "4250000.00" and
    # "4250000" are one float and two different statements about scale.
    estimated_value_raw: str | None = None


@dataclass
class Award:  # pylint: disable=too-many-instance-attributes
    """A lot-level award result linking a lot to one named contractor.

    One Award is emitted per (LotResult × referenced LotTender × named
    Tenderer). A single lot therefore yields several Awards when the
    LotResult references several LotTenders (multi-supplier framework
    agreements / ranked cascades) or when the winning TenderingParty is
    a consortium of joint bidders.

    The fields are a flat record of one eForms award row — each is a
    distinct published datum (identity, money, dates, rank, provenance
    flags, and since 0.12 the verbatim text behind the cleaned money
    and dates), not a candidate for grouping. Nesting them would force
    every consumer through an artificial object hierarchy for no gain.
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
    # ── Raw signals (0.12) ───────────────────────────────────────────
    # The published text behind the cleaned fields above. The cleaned
    # fields are unchanged; these exist so a downstream cleaning stage
    # can see what the buyer actually wrote — placeholders, decimal
    # presence — instead of only what we made of it (data-backlog Part
    # 5, C4/C5: "never silently rewrite: keep the raw value").
    #
    # `cbc:AwardDate` of the SettledContract, verbatim: keeps the
    # "2000-01-01" placeholder that `award_date` nulls (some eSender
    # software writes it instead of a real date; which senders, and in
    # which countries, is what a census over this field will show) and
    # the timezone suffix TED appends. None for the same awards
    # `award_date` is None for on structural grounds (losers).
    award_date_raw: str | None = None
    # `efac:TenderReference/cbc:ID` of the LotTender — the bidder's own
    # reference for its tender, free text. "0.0" is a placeholder one
    # gateway family writes here; it travels with the award-date one.
    tender_reference: str | None = None
    # `cbc:PayableAmount` text `value` was parsed from ("24474133" vs
    # "24474133.00"). Kept even when it fails to parse (value None);
    # None wherever `value` is withheld on purpose (legacy consortia).
    value_raw: str | None = None
    # ── Framework-agreement values of the award's LotResult ─────────
    # BT-709 `efac:FrameworkAgreementValues/cbc:MaximumValueAmount`
    # (this lot's framework ceiling) and BT-660
    # `efbc:ReestimatedValueAmount` (its re-estimate at award time).
    # Like `tenders_received` these are facts about the LOT, repeated on
    # every award of it: never sum them across awards, and never into
    # spend — a ceiling is capacity, not money paid.
    framework_max_value: float | None = None
    framework_max_value_currency: str | None = None
    framework_reestimated_value: float | None = None
    framework_reestimated_value_currency: str | None = None


@dataclass
class Notice:  # pylint: disable=too-many-instance-attributes
    """A fully parsed eForms notice with resolved org references.

    The fields mirror the eForms top-level notice schema 1:1 — every
    field is a distinct semantic UBL element, not a candidate for
    grouping. Splitting would force callers to learn an artificial
    intermediate object hierarchy.
    """

    notice_id: str
    publication_number: str | None = None
    notice_type: str | None = None
    title: str | None = None
    # ISO 639-1 language of `title` ("it"), from the title element's own
    # languageID on eForms and the original-language form's LG on legacy
    # TED, falling back to the notice language. None when neither is
    # recognisable: never guessed from the buyer's country.
    title_lang: str | None = None
    description: str | None = None
    cpv_main: str | None = None
    procedure_type: str | None = None
    issue_date: str | None = None
    dispatch_date: str | None = None  # when notice was sent to TED
    publication_date: str | None = None  # when TED published it
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
    # Identity stamps, read from the notice itself (2026-09, single ingest
    # path). procedure_id is BT-04, the ContractFolderID every notice of one
    # procedure shares — contract identity. notice_version is BT-757, so a
    # loader can skip "already at this version" rather than "already seen".
    # modifies_notice_id is the back-link in its other form: when a buyer
    # wrote the previous notice's versioned UUID instead of a publication
    # number, this holds the bare UUID the graph indexes on.
    procedure_id: str | None = None
    notice_version: str | None = None
    modifies_notice_id: str | None = None
    # Pre-eForms only: the reference number the authority gave the procedure
    # (S-form II.1.1). Kept, indexed and queryable — never the key.
    legacy_procedure_id: str | None = None
    # Place-of-performance NUTS (from ProcurementProject/RealizedLocation).
    nuts: str | None = None
    # ── Raw signals + envelope (0.12) ────────────────────────────────
    # Root `cac:TenderResult/cbc:AwardDate` verbatim, never cleaned.
    # Every eForms award notice seen so far carries the "2000-01-01"
    # placeholder here; the raw text is what lets a census tell the
    # placeholder from a real date and from absence.
    tender_result_award_date_raw: str | None = None
    # `cbc:NoticeLanguageCode` verbatim: eForms three-letter ("POR"),
    # legacy TED two-letter `LG_ORIG` ("PL"). Two code systems, one
    # field — the value says which era wrote it.
    notice_language: str | None = None
    # `cbc:CustomizationID` — the eForms SDK version the notice was
    # authored against ("eforms-sdk-1.14"); the only version marker a
    # scale census can group gateways by. None on legacy TED.
    customization_id: str | None = None
    # Verbatim text `total_value` was parsed from (eForms
    # `cbc:TotalAmount`; legacy `VAL_TOTAL_AFTER` / `VAL_TOTAL`).
    total_value_raw: str | None = None
    # ── Framework-agreement terms, procedure level (C6) ─────────────
    # The ceiling: BT-271 `efbc:FrameworkMaximumAmount` on the
    # procedure, else BT-118 `efbc:OverallMaximumFrameworkContractsAmount`
    # on the NoticeResult, else the one LotResult's BT-709 when the
    # notice has exactly one LotResult. Capacity, not spend — never into
    # totals.
    framework_max_value: float | None = None
    framework_max_value_currency: str | None = None
    framework_max_value_raw: str | None = None
    # BT-1118 `efbc:OverallApproximateFrameworkContractsAmount` on the
    # NoticeResult, else the one LotResult's BT-660 when the notice has
    # exactly one. Multi-lot notices keep the per-lot figures on their
    # awards and leave this None rather than summing.
    framework_reestimated_value: float | None = None
    framework_reestimated_value_currency: str | None = None
    # BT-36 `cac:PlannedPeriod/cbc:DurationMeasure` of the first lot that
    # sets up a framework agreement (eForms has no separate framework
    # duration; the lot's is the framework's). `_months` only when the
    # unit converts exactly (MONTH, YEAR); `_raw` whenever published, as
    # "<n> <unitCode>" — so "6 WEEK" is kept and not rounded.
    framework_duration_months: int | None = None
    framework_duration_raw: str | None = None
    # BT-113 `cac:FrameworkAgreement/cbc:MaximumOperatorQuantity`.
    framework_max_operators: int | None = None
    # ── Framework grouping key (0.13) ───────────────────────────────
    # OPT-100 `efac:SettledContract/cac:NoticeDocumentReference/cbc:ID`,
    # the "Framework Notice Identifier", normalised: the notice that
    # established a framework agreement and every call-off under it carry
    # the identical value, so it groups the notices of one framework.
    # That is all it is. About 80% of the time it names a call for
    # competition, a notice type this platform does not ingest, so it
    # resolves to a :Contract we hold in roughly 13.6% of cases — a
    # grouping key, never a pointer. Nothing here says which side of the
    # framework a notice is on: `is_framework` is true of the
    # establishing notice and of 344/351 confirmed call-offs alike.
    # None means "not published", NOT "no framework": pre-2024 notices
    # carry no such term at all (coverage across framework-flagged award
    # notices is 28.8% for 2024, 89.4% for 2025, 98.3% for 2026).
    framework_notice_id: str | None = None
    # The published text, before normalisation ("00536632-2024"): the
    # padding and the UUID version suffix are what a census of sender
    # behaviour keys on, and they are gone from the field above.
    framework_notice_id_raw: str | None = None
    # Which term it came from: "opt-100", or "bt-125" for the weaker
    # previous-notice fallback, which is read only on a framework
    # procedure. None when neither is published.
    framework_notice_id_source: str | None = None
    # True when this notice's SettledContracts named more than one
    # framework and the most common one won — a padding difference is not
    # a disagreement, the count is on the normalised key. Rare; a loader
    # grouping on the key wants to know the notice was not unanimous.
    framework_notice_id_conflict: bool = False
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

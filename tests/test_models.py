"""Tests for the Notice dataclass methods."""
from eforms.models import Award, Notice, Organization


def test_buyer_resolves_org():
    """buyer() returns the Organization matching buyer_org_id."""
    org = Organization(org_id="ORG-0001", name="Ministry X")
    notice = Notice(
        notice_id="abc",
        buyer_org_id="ORG-0001",
        organizations={"ORG-0001": org},
    )
    assert notice.buyer() is org


def test_buyer_returns_none_when_missing():
    """buyer() returns None when buyer_org_id is not in organizations."""
    notice = Notice(notice_id="abc", buyer_org_id="ORG-9999")
    assert notice.buyer() is None


def test_contractors_returns_winning_orgs():
    """contractors() returns all organizations referenced by awards."""
    org_a = Organization(org_id="ORG-A", name="Winner A")
    org_b = Organization(org_id="ORG-B", name="Winner B")
    notice = Notice(
        notice_id="abc",
        organizations={"ORG-A": org_a, "ORG-B": org_b},
        awards=[
            Award(lot_id="LOT-1", contractor_org_id="ORG-A"),
            Award(lot_id="LOT-2", contractor_org_id="ORG-B"),
        ],
    )
    contractors = notice.contractors()
    assert len(contractors) == 2
    assert contractors[0].name == "Winner A"


def test_contractors_skips_unresolvable_orgs():
    """contractors() skips awards whose org_id is not in organizations."""
    notice = Notice(
        notice_id="abc",
        organizations={},
        awards=[Award(lot_id="LOT-1", contractor_org_id="ORG-GONE")],
    )
    assert notice.contractors() == []

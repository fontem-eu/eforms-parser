"""Tests for notice type filters."""
from eforms.filters import awards_and_modifications, awards_only, modifications_only
from eforms.models import Notice


def _notice(notice_type: str) -> Notice:
    return Notice(notice_id="x", notice_type=notice_type)


def test_awards_only_filters_correctly():
    """Only can-standard and can-social pass through."""
    notices = [
        _notice("can-standard"),
        _notice("cn-standard"),
        _notice("can-modif"),
        _notice("can-social"),
    ]
    result = list(awards_only(notices))
    assert len(result) == 2
    assert result[0].notice_type == "can-standard"
    assert result[1].notice_type == "can-social"


def test_modifications_only():
    """Only can-modif passes through."""
    notices = [_notice("can-standard"), _notice("can-modif")]
    result = list(modifications_only(notices))
    assert len(result) == 1
    assert result[0].notice_type == "can-modif"


def test_awards_and_modifications():
    """Both awards and modifications pass through."""
    notices = [
        _notice("can-standard"),
        _notice("cn-standard"),
        _notice("can-modif"),
    ]
    result = list(awards_and_modifications(notices))
    assert len(result) == 2

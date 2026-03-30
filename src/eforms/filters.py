"""Filter iterables of Notice objects by type."""
from __future__ import annotations

from collections.abc import Iterable, Iterator

from .models import Notice

_AWARD_TYPES = frozenset({
    "can-standard", "can-social", "can-desg", "can-tran",
})
_MODIFICATION_TYPES = frozenset({"can-modif"})


def awards_only(notices: Iterable[Notice]) -> Iterator[Notice]:
    """Yield only Contract Award Notices."""
    for n in notices:
        if n.notice_type in _AWARD_TYPES:
            yield n


def modifications_only(notices: Iterable[Notice]) -> Iterator[Notice]:
    """Yield only Contract Modification Notices."""
    for n in notices:
        if n.notice_type in _MODIFICATION_TYPES:
            yield n


def awards_and_modifications(notices: Iterable[Notice]) -> Iterator[Notice]:
    """Yield awards and modifications (the two types we load)."""
    target = _AWARD_TYPES | _MODIFICATION_TYPES
    for n in notices:
        if n.notice_type in target:
            yield n

"""Language codes as TED writes them, brought to the ISO 639-1 the graph uses.

eForms writes the Publications Office language table's three-letter codes
("ITA", "DEU"); legacy TED writes two-letter ones ("HU"). Translations are
keyed ``title_<iso639-1>`` downstream, so both eras are brought to that.
"""
from __future__ import annotations

# The Publications Office "language" authority table codes for the 24 EU
# official languages, plus the EEA languages TED notices also arrive in.
_THREE_TO_TWO: dict[str, str] = {
    "BUL": "bg", "CES": "cs", "DAN": "da", "DEU": "de", "ELL": "el",
    "ENG": "en", "SPA": "es", "EST": "et", "FIN": "fi", "FRA": "fr",
    "GLE": "ga", "HRV": "hr", "HUN": "hu", "ITA": "it", "LIT": "lt",
    "LAV": "lv", "MLT": "mt", "NLD": "nl", "POL": "pl", "POR": "pt",
    "RON": "ro", "SLK": "sk", "SLV": "sl", "SWE": "sv",
    "NOR": "no", "ISL": "is",
}


def to_iso639_1(code: str | None) -> str | None:
    """``"ITA"`` -> ``"it"``, ``"HU"`` -> ``"hu"``; None for anything else.

    An unrecognised code comes back as None rather than a guess: a wrong
    language is worse than a missing one, since a translator told the wrong
    source translates from it.
    """
    if not code or not code.strip():
        return None
    code = code.strip().upper()
    if len(code) == 2 and code.isalpha():
        return code.lower()
    return _THREE_TO_TWO.get(code)

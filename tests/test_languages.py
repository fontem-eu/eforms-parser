"""TED language codes from both eras, brought to the ISO 639-1 the graph keys on."""
import pytest

from eforms.languages import to_iso639_1


@pytest.mark.parametrize("code, expected", [
    ("ITA", "it"), ("DEU", "de"), ("ELL", "el"), ("GLE", "ga"), ("NOR", "no"),
    ("HU", "hu"), ("EN", "en"), ("ita", "it"), (" POR ", "pt"),
])
def test_both_eras_come_out_as_iso_639_1(code, expected):
    assert to_iso639_1(code) == expected


@pytest.mark.parametrize("code", [None, "", "   ", "XYZ", "MUL", "E1"])
def test_an_unrecognised_code_is_none_not_a_guess(code):
    assert to_iso639_1(code) is None

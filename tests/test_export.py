"""Tests for CSV export escaping."""

from lab_manager.api.routes.export import _escape_cell


def test_escape_cell_formula_equals():
    assert _escape_cell("=SUM(A1:A10)") == "'=SUM(A1:A10)"


def test_escape_cell_formula_plus():
    assert _escape_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"


def test_escape_cell_formula_minus():
    # -cmd is dangerous (letter after minus), -1+1 is safe (digit after minus)
    assert _escape_cell("-cmd|' /C calc'!A0") == "'-cmd|' /C calc'!A0"
    assert _escape_cell("-1+1") == "-1+1"
    assert _escape_cell("-20C") == "-20C"


def test_escape_cell_formula_at():
    assert _escape_cell("@SUM(A1)") == "'@SUM(A1)"


def test_escape_cell_formula_tab():
    assert _escape_cell("\tcmd") == "'\tcmd"


def test_escape_cell_normal_string():
    assert _escape_cell("Normal text") == "Normal text"


def test_escape_cell_empty_string():
    assert _escape_cell("") == ""


def test_escape_cell_none():
    assert _escape_cell(None) == ""


def test_escape_cell_integer():
    assert _escape_cell(42) == 42


def test_escape_cell_float():
    assert _escape_cell(3.14) == 3.14


def test_escape_cell_formula_cr():
    assert _escape_cell("\r=cmd") == "'\r=cmd"


def test_escape_cell_formula_newline():
    assert _escape_cell("\n=cmd") == "'\n=cmd"

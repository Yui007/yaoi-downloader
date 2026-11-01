from __future__ import annotations

import pytest

from yaoi.errors import SelectionError
from yaoi.selection import parse_selection


def test_integer_and_all():
    assert parse_selection("5", 10) == [4]
    assert parse_selection("all", 4) == [0, 1, 2, 3]
    assert parse_selection("*", 3) == [0, 1, 2]


def test_ranges_are_inclusive_and_normalized():
    assert parse_selection("1-3", 10) == [0, 1, 2]
    assert parse_selection("20-10", 25) == list(range(9, 20))
    assert parse_selection("5.5-8.5", 10) == [5, 6, 7]


def test_union_sorted_unique():
    assert parse_selection("1,5,10-12,5", 20) == [0, 4, 9, 10, 11]


def test_decimal_label():
    labels = ["Ch.1", "Ch.2", "Ch.2.5", "Ch.3"]
    assert parse_selection("2.5", 4, labels) == [2]
    with pytest.raises(SelectionError):
        parse_selection("9.5", 4, labels)
    with pytest.raises(SelectionError):
        parse_selection("2.5", 4)


def test_errors_name_the_problem():
    for text in ["", "0", "11", "1,,2", "all,1", "abc", "1-0"]:
        with pytest.raises(SelectionError):
            parse_selection(text, 10)

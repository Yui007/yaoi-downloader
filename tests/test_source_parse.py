from __future__ import annotations

import json

from yaoi.errors import SourceError
from yaoi.sources.yaoi import balanced_slice, extract_groups, rsc_payload


def test_rsc_payload_joins_escaped_rows():
    payload = '<div>{"groups":[{"label":"1","variants":[{"id":2}]}]}</div>'
    rows = json.dumps(payload)[1:-1]
    html = f'self.__next_f.push([1,"{rows}"])'
    joined = rsc_payload(html)
    assert '"groups"' in joined


def test_extract_groups_and_balanced_slice():
    group_data = [{"label": "1", "variants": [{"id": 2, "s": 3}]}]
    payload = 'prefix "groups":' + json.dumps(group_data) + ' suffix'
    rows = json.dumps(payload)[1:-1]
    html = f'self.__next_f.push([1,"{rows}"])'
    assert extract_groups(html) == group_data
    assert balanced_slice('xx[1,{"a":"]"}]yy', 2) == '[1,{"a":"]"}]'


def test_missing_groups_is_typed():
    try:
        extract_groups("<html></html>")
    except SourceError:
        pass
    else:
        raise AssertionError("expected SourceError")

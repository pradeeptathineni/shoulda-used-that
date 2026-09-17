from __future__ import annotations

import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shoulda_used_that.canonical import canonical_bytes, digest, short_id
from shoulda_used_that.errors import ShouldaError


def test_rfc8785_object_order_and_utf8_vector() -> None:
    value = {"string": '€$\u000f\nA\'B"\\"/', "literals": [None, True, False]}
    encoded = canonical_bytes(value)

    assert encoded == (
        b'{"literals":[null,true,false],"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"\\\\\\"/"}'
    )
    assert json.loads(encoded) == value


@given(
    st.dictionaries(
        st.text(min_size=1),
        st.integers(min_value=-(2**53) + 1, max_value=2**53 - 1),
        max_size=20,
    )
)
def test_canonical_identity_is_insertion_order_independent(value: dict[str, int]) -> None:
    reversed_value = dict(reversed(list(value.items())))

    assert canonical_bytes(value) == canonical_bytes(reversed_value)
    assert digest(value, prefix="test") == digest(reversed_value, prefix="test")


def test_short_id_is_namespaced_and_rejects_unsafe_length() -> None:
    assert short_id({"a": 1}, prefix="chk").startswith("chk_")
    assert len(short_id({"a": 1}, prefix="chk")) == 28
    with pytest.raises(ValueError, match="at least 16"):
        short_id({}, prefix="x", length=15)


def test_non_json_value_fails_with_typed_error() -> None:
    with pytest.raises(ShouldaError) as raised:
        canonical_bytes({"not-json": object()})

    assert raised.value.code == "canonicalization_failed"

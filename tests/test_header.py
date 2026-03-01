"""Tests for the request.Header class."""

import pytest

from poorwsgi.request import Headers

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use


class TestSetValues:
    """Tests adding headers and setting header values."""

    def test_constructor_empty(self):
        """Tests the Headers constructor with empty inputs."""
        Headers()
        Headers([])  # list
        Headers(tuple())
        Headers({})  # dict
        Headers(set())

    def test_constructor_tuples(self):
        """Tests the Headers constructor with tuple inputs."""
        headers = Headers([("X-Test", "Ok"), ("Key", "Value")])
        assert headers["X-Test"] == "Ok"

        headers = Headers((("X-Test", "Ok"), ("X-Test", "Value")))
        assert headers["X-Test"] == "Ok"
        assert headers.get_all("X-Test") == ("Ok", "Value")

    def test_constructor_dict(self):
        """Tests the Headers constructor with dictionary inputs."""
        headers = Headers({"X-Test": "Ok", "Key": "Value"})
        assert headers["X-Test"] == "Ok"

        xheaders = Headers(headers.items())
        assert xheaders["X-Test"] == "Ok"

    def test_constructor_error(self):
        """Tests the Headers constructor with invalid inputs, expecting
        errors."""
        with pytest.raises(TypeError):
            Headers("Value")
        with pytest.raises(ValueError):  # noqa: PT011
            Headers(["a", "b"])
        with pytest.raises(TypeError):
            Headers({"None": None})

    def test_set(self):
        """Tests setting a header value using dictionary-like assignment."""
        headers = Headers()
        headers["X-Test"] = "Ok"
        assert headers.items() == (("X-Test", "Ok"),)

    def test_add_header(self):
        """Tests adding headers with various parameters using add_header."""
        headers = Headers()
        headers.add_header(
            "Content-Disposition", "attachment", filename="image.png"
        )
        assert (
            headers["Content-Disposition"]
            == 'attachment; filename="image.png"'
        )

        headers.add_header(
            "Accept-Encoding", (("gzip", 1.0), ("identity", 0.5), ("*", 0))
        )
        assert (
            headers["Accept-Encoding"] == "gzip;q=1.0, identity;q=0.5, *;q=0"
        )

        headers.add_header("X-Test", key="value")
        assert headers["X-Test"] == 'key="value"'

    def test_add_header_error(self):
        """Tests adding a header with invalid values, expecting a
        ValueError."""
        headers = Headers()
        with pytest.raises(ValueError):  # noqa: PT011
            headers.add_header("X-None")

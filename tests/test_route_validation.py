"""Unit tests for route filter validation."""

import pytest

from poorwsgi.state import METHOD_GET
from poorwsgi.wsgi import Application


def test_valid_route_no_filter():
    """Tests that routes without filters work correctly."""
    app = Application("test_valid_no_filter")

    @app.route("/api/users")
    def handler(_req):
        return "ok"

    assert "/api/users" in app.routes


def test_valid_route_with_int_filter():
    """Tests that routes with :int filters work correctly."""
    app = Application("test_valid_int")

    @app.route("/api/users/<id:int>")
    def handler(_req, _id):
        return "ok"

    # Route with filter should be in regular_routes
    assert len(app.regular_routes) > 0


def test_valid_route_with_word_filter():
    """Tests that routes with :word filters work correctly."""
    app = Application("test_valid_word")

    @app.route("/api/users/<name:word>")
    def handler(_req, _name):
        return "ok"

    assert len(app.regular_routes) > 0


def test_valid_route_with_float_filter():
    """Tests that routes with :float filters work correctly."""
    app = Application("test_valid_float")

    @app.route("/api/values/<value:float>")
    def handler(_req, _value):
        return "ok"

    assert len(app.regular_routes) > 0


def test_valid_route_with_uuid_filter():
    """Tests that routes with :uuid filters work correctly."""
    app = Application("test_valid_uuid")

    @app.route("/api/objects/<id:uuid>")
    def handler(_req, _id):
        return "ok"

    assert len(app.regular_routes) > 0


def test_valid_route_with_hex_filter():
    """Tests that routes with :hex filters work correctly."""
    app = Application("test_valid_hex")

    @app.route("/api/codes/<code:hex>")
    def handler(_req, _code):
        return "ok"

    assert len(app.regular_routes) > 0


def test_valid_route_with_multiple_filters():
    """Tests that routes with multiple filters work correctly."""
    app = Application("test_valid_multiple")

    @app.route("/api/<entity:word>/<id:int>")
    def handler(_req, _entity, _id):
        return "ok"

    assert len(app.regular_routes) > 0


def test_invalid_route_space_after_open_bracket():
    """Tests that a space after < is rejected."""
    app = Application("test_invalid_space_after_open")

    with pytest.raises(
        ValueError, match=r"Invalid route definition.*must not contain spaces"
    ):

        @app.route("/api/< id:int>")
        def handler(_req, _id):
            return "ok"


def test_invalid_route_space_before_close_bracket():
    """Tests that a space before > is rejected."""
    app = Application("test_invalid_space_before_close")

    with pytest.raises(ValueError, match="Invalid route definition"):

        @app.route("/api/<id:int >")
        def handler(_req, _id):
            return "ok"


def test_invalid_route_space_after_name():
    """Tests that a space after the parameter name is rejected."""
    app = Application("test_invalid_space_after_name")

    with pytest.raises(ValueError, match="Invalid route definition"):

        @app.route("/api/<id :int>")
        def handler(_req, _id):
            return "ok"


def test_invalid_route_space_after_colon():
    """Tests that a space after : is rejected."""
    app = Application("test_invalid_space_after_colon")

    with pytest.raises(ValueError, match="Invalid route definition"):

        @app.route("/api/<id: int>")
        def handler(_req, _id):
            return "ok"


def test_invalid_route_multiple_spaces():
    """Tests that multiple spaces are rejected."""
    app = Application("test_invalid_multiple_spaces")

    with pytest.raises(ValueError, match="Invalid route definition"):

        @app.route("/api/< id : int >")
        def handler(_req, _id):
            return "ok"


def test_error_message_provides_examples():
    """Tests that the error message includes helpful examples."""
    app = Application("test_error_message")

    with pytest.raises(
        ValueError, match="Invalid route definition"
    ) as exc_info:

        @app.route("/api/<id :int>")
        def handler(_req, _id):
            return "ok"

    error_message = str(exc_info.value)
    assert "<id:int>" in error_message
    assert "<name:word>" in error_message
    assert "<value:float>" in error_message


def test_set_route_with_space_rejection():
    """Tests that the set_route method also rejects spaces."""
    app = Application("test_set_route_space")

    def handler(_req, _id):
        return "ok"

    with pytest.raises(ValueError, match="Invalid route definition"):
        app.set_route("/api/< id:int>", handler, METHOD_GET)


def test_route_with_no_filter_and_angle_brackets():
    """Tests that routes without filters but with <> in the path work."""
    app = Application("test_no_filter")

    @app.route("/api/<id>")
    def handler(_req, _id):
        return "ok"

    # Route with <name> but no filter should work
    assert len(app.regular_routes) > 0


def test_custom_filter_no_spaces():
    """Tests that custom filters work without spaces."""
    app = Application("test_custom_filter")
    app.set_filter("custom", r"[a-z]+")

    @app.route("/api/<value:custom>")
    def handler(_req, _value):
        return "ok"

    assert len(app.regular_routes) > 0


def test_custom_filter_with_space_rejection():
    """Tests that custom filters reject spaces."""
    app = Application("test_custom_filter_space")
    app.set_filter("custom", r"[a-z]+")

    with pytest.raises(ValueError, match="Invalid route definition"):

        @app.route("/api/<value: custom>")
        def handler(_req, _value):
            return "ok"


def test_re_filter_no_spaces():
    """Tests that the :re: filter works without spaces."""
    app = Application("test_re_filter")

    @app.route("/api/<value:re:[a-z]+>")
    def handler(_req, _value):
        return "ok"

    assert len(app.regular_routes) > 0


def test_re_filter_with_space_rejection():
    """Tests that the :re: filter rejects spaces before >."""
    app = Application("test_re_filter_space")

    with pytest.raises(ValueError, match="Invalid route definition"):

        @app.route("/api/<value:re:[a-z]+ >")
        def handler(_req, _value):
            return "ok"

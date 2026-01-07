"""Unit tests for route filter validation."""
import pytest

from poorwsgi.wsgi import Application
from poorwsgi.state import METHOD_GET


def test_valid_route_no_filter():
    """Test that routes without filters work correctly."""
    app = Application('test_valid_no_filter')
    
    @app.route('/api/users')
    def handler(req):
        return 'ok'
    
    assert '/api/users' in app.routes


def test_valid_route_with_int_filter():
    """Test that routes with :int filter work correctly."""
    app = Application('test_valid_int')
    
    @app.route('/api/users/<id:int>')
    def handler(req, id):
        return 'ok'
    
    # Route with filter should be in regular_routes
    assert len(app.regular_routes) > 0


def test_valid_route_with_word_filter():
    """Test that routes with :word filter work correctly."""
    app = Application('test_valid_word')
    
    @app.route('/api/users/<name:word>')
    def handler(req, name):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_valid_route_with_float_filter():
    """Test that routes with :float filter work correctly."""
    app = Application('test_valid_float')
    
    @app.route('/api/values/<value:float>')
    def handler(req, value):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_valid_route_with_uuid_filter():
    """Test that routes with :uuid filter work correctly."""
    app = Application('test_valid_uuid')
    
    @app.route('/api/objects/<id:uuid>')
    def handler(req, id):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_valid_route_with_hex_filter():
    """Test that routes with :hex filter work correctly."""
    app = Application('test_valid_hex')
    
    @app.route('/api/codes/<code:hex>')
    def handler(req, code):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_valid_route_with_multiple_filters():
    """Test that routes with multiple filters work correctly."""
    app = Application('test_valid_multiple')
    
    @app.route('/api/<entity:word>/<id:int>')
    def handler(req, entity, id):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_invalid_route_space_after_open_bracket():
    """Test that space after < is rejected."""
    app = Application('test_invalid_space_after_open')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/< id:int>')
        def handler(req, id):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)
    assert 'must not contain spaces' in str(exc_info.value)
    assert '/api/< id:int>' in str(exc_info.value)


def test_invalid_route_space_before_close_bracket():
    """Test that space before > is rejected."""
    app = Application('test_invalid_space_before_close')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/<id:int >')
        def handler(req, id):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)
    assert 'must not contain spaces' in str(exc_info.value)


def test_invalid_route_space_after_name():
    """Test that space after parameter name is rejected."""
    app = Application('test_invalid_space_after_name')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/<id :int>')
        def handler(req, id):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)
    assert 'must not contain spaces' in str(exc_info.value)


def test_invalid_route_space_after_colon():
    """Test that space after : is rejected."""
    app = Application('test_invalid_space_after_colon')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/<id: int>')
        def handler(req, id):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)
    assert 'must not contain spaces' in str(exc_info.value)


def test_invalid_route_multiple_spaces():
    """Test that multiple spaces are rejected."""
    app = Application('test_invalid_multiple_spaces')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/< id : int >')
        def handler(req, id):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)
    assert 'must not contain spaces' in str(exc_info.value)


def test_error_message_provides_examples():
    """Test that error message includes helpful examples."""
    app = Application('test_error_message')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/<id :int>')
        def handler(req, id):
            return 'ok'
    
    error_message = str(exc_info.value)
    assert '<id:int>' in error_message
    assert '<name:word>' in error_message
    assert '<value:float>' in error_message


def test_set_route_with_space_rejection():
    """Test that set_route method also rejects spaces."""
    app = Application('test_set_route_space')
    
    def handler(req, id):
        return 'ok'
    
    with pytest.raises(ValueError) as exc_info:
        app.set_route('/api/< id:int>', handler, METHOD_GET)
    
    assert 'Invalid route definition' in str(exc_info.value)
    assert 'must not contain spaces' in str(exc_info.value)


def test_route_with_no_filter_and_angle_brackets():
    """Test that routes without filters but with <> in path work."""
    app = Application('test_no_filter')
    
    @app.route('/api/<id>')
    def handler(req, id):
        return 'ok'
    
    # Route with <name> but no filter should work
    assert len(app.regular_routes) > 0


def test_custom_filter_no_spaces():
    """Test that custom filters work without spaces."""
    app = Application('test_custom_filter')
    app.set_filter('custom', r'[a-z]+')
    
    @app.route('/api/<value:custom>')
    def handler(req, value):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_custom_filter_with_space_rejection():
    """Test that custom filters reject spaces."""
    app = Application('test_custom_filter_space')
    app.set_filter('custom', r'[a-z]+')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/<value: custom>')
        def handler(req, value):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)


def test_re_filter_no_spaces():
    """Test that :re: filter works without spaces."""
    app = Application('test_re_filter')
    
    @app.route('/api/<value:re:[a-z]+>')
    def handler(req, value):
        return 'ok'
    
    assert len(app.regular_routes) > 0


def test_re_filter_with_space_rejection():
    """Test that :re: filter rejects spaces before >."""
    app = Application('test_re_filter_space')
    
    with pytest.raises(ValueError) as exc_info:
        @app.route('/api/<value:re:[a-z]+ >')
        def handler(req, value):
            return 'ok'
    
    assert 'Invalid route definition' in str(exc_info.value)

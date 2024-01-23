"""Tests for request.Header class."""

from unittest import TestCase

from poorwsgi.request import Headers

# pylint: disable=missing-function-docstring
# pylint: disable=no-self-use


class TestSetValues(TestCase):
    """Adding headers and or setting header values."""

    def test_constructor_empty(self):
        Headers()
        Headers([])  # list
        Headers(tuple())
        Headers({})  # dict
        Headers(set())

    def test_constructor_tuples(self):
        headers = Headers([('X-Test', 'Ok'), ('Key', 'Value')])
        assert headers['X-Test'] == 'Ok'

        headers = Headers((('X-Test', 'Ok'), ('X-Test', 'Value')))
        assert headers['X-Test'] == 'Ok'
        assert headers.get_all('X-Test') == ('Ok', 'Value')

    def test_constructor_dict(self):
        headers = Headers({'X-Test': 'Ok', 'Key': 'Value'})
        assert headers['X-Test'] == 'Ok'

        xheaders = Headers(headers.items())
        assert xheaders['X-Test'] == 'Ok'

    def test_constructor_error(self):
        with self.assertRaises(TypeError):
            Headers('Value')
        with self.assertRaises(ValueError):
            Headers(['a', 'b'])
        with self.assertRaises(TypeError):
            Headers({'None': None})

    def test_set(self):
        headers = Headers()
        headers['X-Test'] = "Ok"
        assert headers.items() == (('X-Test', 'Ok'),)

    def test_add_header(self):
        headers = Headers()
        headers.add_header('Content-Disposition', 'attachment',
                           filename='image.png')
        assert headers['Content-Disposition'] == \
            'attachment; filename="image.png"'

        headers.add_header('Accept-Encoding',
                           (('gzip', 1.0), ('identity', 0.5), ('*', 0)))
        assert headers['Accept-Encoding'] == \
            'gzip;q=1.0, identity;q=0.5, *;q=0'

        headers.add_header('X-Test', key="value")
        assert headers['X-Test'] == 'key="value"'

    def test_add_header_error(self):
        headers = Headers()
        with self.assertRaises(ValueError):
            headers.add_header('X-None')

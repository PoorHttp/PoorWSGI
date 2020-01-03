from unittest import TestCase

from poorwsgi.request import Headers


class Test(TestCase):
    def test_set(self):
        headers = Headers()
        headers['X-Test'] = "Ok"
        assert headers.items() == (('X-Test', 'Ok'),)

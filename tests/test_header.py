from poorwsgi.request import Headers


class Test:
    def test_set(self):
        headers = Headers()
        headers['X-Test'] = "Ok"
        assert headers.items() == (('X-Test', 'Ok'),)

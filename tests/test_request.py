from io import BytesIO

from poorwsgi.request import JsonDict, JsonList, parse_json_request


class TestJSON:
    def test_json_dict(self):
        json = JsonDict(age=23, items=[1, 2], size="25")
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age") == 23
        assert json.getfirst("age") == "23"
        assert json.getfirst("items") == "1"
        assert tuple(json.getlist("items", fce=str)) == ("1", "2")

    def test_json_list_empty(self):
        json = JsonList()
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age", 23) == 23
        assert json.getfirst("age", 23) == "23"
        assert json.getfirst("name", "2", int) == 2

    def test_json_list(self):
        json = JsonList([1, 2])
        assert json.getvalue("age") == 1
        assert json.getfirst("age") == "1"
        assert tuple(json.getlist("items", fce=str)) == ("1", "2")


class TestParseJson:
    def test_str(self):
        assert isinstance(parse_json_request(BytesIO(b"{}")), JsonDict)

    def test_list(self):
        assert isinstance(parse_json_request(BytesIO(b"[]")), JsonList)

    def test_text(self):
        assert isinstance(parse_json_request(BytesIO(b'"text"')), str)

    def test_int(self):
        assert isinstance(parse_json_request(BytesIO(b"23")), int)

    def test_float(self):
        assert isinstance(parse_json_request(BytesIO(b"3.14")), float)

    def test_bool(self):
        assert isinstance(parse_json_request(BytesIO(b"true")), bool)

    def test_null(self):
        assert parse_json_request(BytesIO(b"null")) is None

    def test_error(self):
        assert parse_json_request(BytesIO(b"abraka")) is None

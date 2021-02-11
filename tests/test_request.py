from io import BytesIO
from typing import Dict, Any

from poorwsgi.request import JsonDict, JsonList, parse_json_request, \
    EmptyForm, Args, FieldStorage


class TestEmpty:
    def test_emptry_form(self):
        form = EmptyForm()
        assert form.getvalue("name") is None
        assert form.getvalue("name", "PooWSGI") == "PooWSGI"
        assert form.getfirst("name") is None
        assert form.getfirst("age", "23", int) == 23
        assert tuple(form.getlist("values", ("3", "4"), int)) == (3, 4)
        assert tuple(form.getlist("values")) == ()


class TestJSON:
    def test_json_dict(self):
        json = JsonDict(age=23, items=[1, 2], size="25")
        assert json.getvalue("no") is None
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age") == 23
        assert json.getfirst("no") is None
        assert json.getfirst("age") == "23"
        assert json.getfirst("items") == "1"
        assert tuple(json.getlist("items", fce=str)) == ("1", "2")
        assert tuple(json.getlist("values", ("3", "4"), int)) == (3, 4)
        assert tuple(json.getlist("values")) == ()

    def test_json_list_empty(self):
        json = JsonList()
        assert json.getvalue("no") is None
        assert json.getvalue("name", "PooWSGI") == "PooWSGI"
        assert json.getvalue("age", 23) == 23
        assert json.getfirst("no") is None
        assert json.getfirst("age", 23) == "23"
        assert json.getfirst("name", "2", int) == 2
        assert tuple(json.getlist("ages", ["1", "2"], int)) == (1, 2)
        assert tuple(json.getlist("ages")) == ()

    def test_json_list(self):
        json = JsonList([1, 2])
        assert json.getvalue("age") == 1
        assert json.getfirst("age") == "1"
        assert tuple(json.getlist("items", fce=str)) == ("1", "2")


class TestArgs:
    class Req:
        app = None
        query = ''
        environ: Dict[str, Any] = {}

    def test_empty(self):
        args = Args(self.Req())
        assert args.getvalue("no") is None
        assert args.getvalue("name", "PooWSGI") == "PooWSGI"
        assert args.getfirst("no") is None
        assert args.getfirst("age", "23", int) == 23
        assert tuple(args.getlist("values", ("3", "4"), int)) == (3, 4)
        assert tuple(args.getlist("values")) == ()


class TestForm:
    class Req:
        environ: Dict[str, Any] = {}

    def test_empty(self):
        form = FieldStorage(self.Req())
        assert form.getvalue("no") is None
        assert form.getvalue("name", "PooWSGI") == "PooWSGI"
        assert form.getfirst("no") is None
        assert form.getfirst("age", "23", int) == 23
        assert tuple(form.getlist("values", ("3", "4"), int)) == (3, 4)
        assert tuple(form.getlist("values")) == ()


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

    def test_unicode(self):
        rv = parse_json_request(BytesIO(b'"\\u010de\\u0161tina"'))
        assert rv == "čeština"

    def test_utf8(self):
        rv = parse_json_request(BytesIO(b'"\xc4\x8de\xc5\xa1tina"'))
        assert rv == "čeština"

    def test_unicode_struct(self):
        rv = parse_json_request(BytesIO(b'{"lang":"\\u010de\\u0161tina"}'))
        assert rv == {"lang": "čeština"}

    def test_utf_struct(self):
        rv = parse_json_request(BytesIO(b'{"lang":"\xc4\x8de\xc5\xa1tina"}'))
        assert rv == {"lang": "čeština"}

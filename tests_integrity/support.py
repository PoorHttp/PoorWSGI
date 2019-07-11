from requests import Request, Session
from requests.exceptions import RequestException


def check_url(url, method="GET", status_code=200, allow_redirects=True,
              **kwargs):
    """Do HTTP request and check status_code."""
    session = kwargs.pop("session", None)
    if not session:     # nechceme vytvářet session nadarmo
        session = Session()
    try:
        request = Request(method, url, cookies=session.cookies, **kwargs)
        response = session.send(request.prepare(),
                                allow_redirects=allow_redirects)
        if isinstance(status_code, int):
            status_code = [status_code]
        assert response.status_code in status_code
        return response
    except RequestException:
        pass
    raise ConnectionError("Not response")

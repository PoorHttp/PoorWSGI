"""OpenAPI checker based on jsonschema.

This module have another implementation of OpenAPI request and responds checks.
As was written, this module requires ``jsonschema`` which is not standard
PoorWSGI dependency.

:Classes:   OpenApi
"""
from enum import Enum
from secrets import randbelow


class Policy(Enum):
    """Checking policy when DEFAULT means by explicit settings."""
    NEVER = 0
    DEFAULT = 1
    ALLWAYS = 2


def check_handler_after(req, res):
    """."""
    check = getattr(req, "check_response", False)
    if check:
        pass    # call response check
    return res


class OpenAPI():
    """Module contains functionality for OpenAPI request and response check."""

    def __init__(self):
        self.__request_policy = Policy.DEFAULT
        self.__response_policy = Policy.DEFAULT

    @property
    def request_policy(self):
        """Return checking policy (Policy enumerate) for requests."""
        return self.__request_policy

    @request_policy.setter
    def request_policy(self, value):
        """Set checking policy for requests, Policy.DEFAULT is default."""
        assert isinstance(value, Policy)
        self.__request_policy = value

    @property
    def response_policy(self):
        """Return checking policy (Policy enumerate) for requests."""
        return self.__response_policy

    @response_policy.setter
    def response_policy(self, value):
        """Set checking policy for requests, Policy.DEFAULT is default."""
        assert isinstance(value, Policy)
        self.__response_policy = value

    def check(self, path, request=1, response=0):
        """Wrap the function to check if request or response are valid.

        path: string
            path defined in openapi schema
        requests: int (1)
            number of 1:N how frequently will request check be called
        response: int (0)
            number of 1:N how frequently will response check be called

        Values `request` and `response` could be rewrite by request_policy
        resp. response_policy property. When Policy.DEFAULT is used, that
        be used this number as random match. So when value is 5, that means,
        there is chance 1:5 that check will be called.
        """
        def decorator(fun):
            def wrapper(req, *args, **kwargs):
                req.check_path = path

                check = (self.request_policy == Policy.ALLWAYS or
                         (self.request_policy == Policy.DEFAULT and
                          request and randbelow(request+1)))
                # req.check_request

                check = (self.response_policy == Policy.ALLWAYS or
                         (self.response_policy == Policy.DEFAULT and
                          response and randbelow(response+1)))
                req.check_response = check

                if req.check_request:
                    # pylint: disable=fixme
                    pass    # TODO: call check request

                return fun(req, *args, **kwargs)
            return wrapper
        return decorator

"""pytest configuration"""


def pytest_addoption(parser):
    """Append new options for py.test command tool."""
    parser.addoption(
        "--with-uwsgi", action="store_true",
        help="Run http server on uwsgi instead of internal server.")

"""Pytest configuration."""


def pytest_addoption(parser):
    """Appends new options for the pytest command-line tool."""
    parser.addoption(
        "--with-uwsgi", action="store_true",
        help="Run http server on uwsgi instead of internal server.")

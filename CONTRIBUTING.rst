Contributing to the Project
===========================

Thank you for your interest in contributing to the PoorWSGI project! Every contribution is welcome. This document will guide you through the process of reporting a bug, suggesting an enhancement, or directly contributing code.

Reporting Bugs
--------------
If you encounter a bug, please ensure that you:

1.  Search the existing `issues <https://github.com/PoorHttp/PoorWSGI/issues>`_ to ensure the bug has not already been reported.
2.  If you cannot find the bug, create a new issue.
3.  In the description, provide as much information as possible:

    *   The version of PoorWSGI you are using.
    *   The Python version and operating system.
    *   A short but descriptive summary of the bug.
    *   Steps to reproduce the bug.
    *   What you expected to happen and what actually happened.

Suggesting Enhancements
-----------------------
Do you have an idea for a new feature or improvement?

1.  Create a new issue and describe your suggestion.
2.  Explain why this feature would be useful and how it should work.

Development and Code Contribution
---------------------------------
If you want to contribute code, please follow these steps. The project is developed using a **Test-Driven Development (TDD)** approach. This means that for every new feature or bug fix, a failing test should be written first, followed by the code that makes the test pass.

1. Setting Up the Development Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First, prepare your local development environment.

.. code-block:: bash

    # 1. Fork the repository and clone it
    git clone https://github.com/YOUR-USERNAME/PoorWSGI.git
    cd PoorWSGI

    # 2. Create and activate a virtual environment
    python3 -m venv .venv
    source .venv/bin/activate

    # 3. Install the project in editable mode and the development dependencies
    python -m pip install --upgrade pip
    pip install -e .
    pip install -U pre-commit flake8 setuptools pytest pytest-doctestplus pytest-pylint pytest-mypy ruff isort
    pip install -U openapi-core uwsgi simplejson WSocket requests websocket-client
    pip install -U types-simplejson types-requests types-PyYAML

    # 4. Activate pre-commit hooks for automatic code checking
    pre-commit install

2. Code Style and Automatic Checks (pre-commit)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To maintain a consistent style and code quality, the project **requires the use of `pre-commit`**. This tool automatically runs a set of checks (called "hooks") before each commit. These checks include formatting, linting, and other code analyses. The configuration is defined in the `.pre-commit-config.yaml` file.

Thanks to `pre-commit`, you don't have to run all the tools manually. If a commit fails due to a check, `pre-commit` will often fix the code for you automatically. In that case, you just need to add the modified files again (`git add`) and repeat the commit.

If you still wish to run the checks manually during development (outside of a commit), you can use the following commands:

.. code-block:: bash

    # Manually run all pre-commit hooks on all files
    pre-commit run --all-files

    # Alternatively, individual tools:
    ruff format .      # Formatting
    ruff check .       # Linting
    pylint poorwsgi/   # In-depth analysis
    isort .            # Sorting imports

3. Running Tests
~~~~~~~~~~~~~~~~

As mentioned, TDD is a key part of development. All tests must pass before you submit a Pull Request.

*   `tests/`: Contains unit tests.
*   `tests_integrity/`: Contains integration tests, which may run real servers from the `examples/` directory.

You can run the tests using `pytest`:

.. code-block:: bash

    # Run all tests (unit and integration)
    pytest -v

    # Run only unit tests
    pytest -v tests/

    # Run integration tests
    pytest -v tests_integrity/

4. Submitting Changes (Pull Request)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1.  Create a new branch for your changes: `git checkout -b feature/my-new-feature`.
2.  Make your code changes and write tests for them.
3.  Ensure that all local tests pass (`pytest -v`).
4.  Create a commit. At this point, `pre-commit` will automatically check and possibly fix your code. If it fails, make the necessary adjustments and repeat the commit.

    .. code-block:: bash

        git add .
        git commit -m "A brief description of the changes"

5.  Push the changes to your fork: `git push origin feature/my-new-feature`.
6.  Open a `Pull Request <https://github.com/PoorHttp/PoorWSGI/pulls>`_ to the `main` branch of the main repository.

Your Pull Request will be reviewed by automated tests (CI) and one of the project maintainers. Thank you for your help!

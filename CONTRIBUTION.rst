Contribution
============


Tests
-----
``test`` command in ``setup.py`` run unit tests automatically. There is used
``pytest`` toolkit, so pytest tool is needed.

You can run tests with next commands:

.. code:: sh

		# setup.py unit tests
		~$ python3 setup.py test

    # all test (with integrity tests)
    ~$ pytest -v

**pytest** package have many additional plugins so you can use that.
Next command check all .rst files, source code with pep8 and doctest checkers.

.. code:: sh

    # check pep8 and doctest (pytest-pep8 and pytest-doctestplus plugins)
    ~$ pytest -v --pep8 --doctest-plus --doctest-rst


Directories
-----------
* ``poorwsgi`` - poorwsgi library
* ``tests`` - unit tests that only use code from poorwsgi
* ``tests_integrity`` - integrity tests, that needs running servers. If no
  server url is set, that each test run it's server from ``examples`` directory.
* ``doc`` - documentation source for html documentation
* ``examples`` - example servers which is used by integrity tests

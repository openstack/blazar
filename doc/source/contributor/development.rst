======================
Development guidelines
======================

Coding Guidelines
-----------------

`PEP8 <http://legacy.python.org/dev/peps/pep-0008/>`_ checks should pass for
all Blazar code. You may check it using the following command:

.. sourcecode:: console

    tox -e pep8

..

Also you should keep your code clear using more code style checks via
`pylint <http://www.pylint.org>`_:

.. sourcecode:: console

   tox -e pylint

..

If you see any pep8/pylint errors in your code, it is mandatory to fix them
before sending your change for review.

Testing Guidelines
------------------

Blazar repositories have unit tests that are run on all submitted code, and it
is recommended for developers to execute them themselves to catch regressions
early. Developers are also expected to keep the test suite up-to-date with any
submitted code changes.

Unit tests might be run in `TOX <https://testrun.org/tox/latest/>`_ environments
via the commands:

.. sourcecode:: console

   tox -e py36
   tox -e py37

..

for Python 3.6 and Python 3.7 accordingly.

Note that the Blazar code base is not yet compatible with Python 3, so tests
will be failing.

Note that some tests might use databases, the script
``tools/test-setup.sh`` sets up databases for the unit tests.

Documentation Guidelines
------------------------

Currently Blazar docs are partially written on `OpenStack wiki
<https://wiki.openstack.org/wiki/Blazar>`_ pages, and partially using
Sphinx / RST located in the main repo in *doc* directory.

To build Sphinx / RST docs locally run the following command:

.. sourcecode:: console

   tox -e docs

..

Then you can access generated docs in the *doc/build/* directory, for example,
the main page would be *doc/build/html/index.html*.

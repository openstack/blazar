Development guidelines
======================

Coding Guidelines
-----------------

`PEP8 <http://legacy.python.org/dev/peps/pep-0008/>`_ checking should pass for
all Blazar code. You may check it using the following command:

.. sourcecode:: console

    tox -e pep8

..

Also you should keep your code clear using more code style checkings via
`pylint <http://www.pylint.org>`_:

.. sourcecode:: console

   tox -e pylint

..

If you see any pep8/pylint errors in your code, it's mandatory to fix them
before sending your change on review.

Testing Guidelines
------------------

Blazar repositories have unit tests that are run on all submitted code, and it
is recommended for developers to execute them themselves to catch regressions
early. Developers are also expected to keep the test suite up-to-date with any
submitted code changes.

Unit tests might be run in `TOX <https://testrun.org/tox/latest/>`_ environments
via the commands:

.. sourcecode:: console

   tox -e py27
   tox -e py34
   tox -e py35

..

for Python 2.7, Python 3.4, and Python 3.5 accordingly.

Note that the Blazar code base is not yet compatible with Python 3, so tests
will be failing.

Documentation Guidelines
------------------------

Currently Blazar docs are partially written on `OpenStack wiki
<https://wiki.openstack.org/wiki/Blazar>`_ pages, and partially using
Sphinx / RST located in the main repo in *doc* directory.

To build Sphinx / RST docs locally run the following command:

.. sourcecode:: console

   tox -e docs

..

After it you can access generated docs in *doc/build/* directory, for example,
main page - *doc/build/html/index.html*.


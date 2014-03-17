Development guidelines
======================

Coding Guidelines
-----------------

`PEP8 <http://legacy.python.org/dev/peps/pep-0008/>`_ checking should pass for
all Climate code. You may check it using the following command:

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

Climate repositories have unit tests that are run on all submitted code, and it
is recommended for developers to execute them themselves to catch regressions
early. Developers are also expected to keep the test suite up-to-date with any
submitted code changes.

Unit tests might be ran in `TOX <https://testrun.org/tox/latest/>`_ environment
via commands:

.. sourcecode:: console

   tox -e py27
   tox -e py26

..

for Python 2.7 and Python 2.6 accordingly.

Documentation Guidelines
------------------------

Currently Climate docs are partially written on `OpenStack wiki
<https://wiki.openstack.org/wiki/Climate>`_ pages, and partially using
Sphinx / RST located in the main repo in *doc* directory. In future all of them
will be moved to Sphinx / RST (now these docs cannot be published on
readthedocs.org, because there is already existing *climate* project created on
it. Now Climate ATCs are voting to choose new name for Climate project and then
all docs will be moved to new readthedocs project).

To build Sphinx / RST docs locally run the following command:

.. sourcecode:: console

   tox -e docs

..

After it you can access generated docs in *doc/build/* directory, for example,
main page - *doc/build/html/index.html*.


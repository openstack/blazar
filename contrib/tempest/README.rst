This directory contains the files necessary for tempest to cover Blazar project.

To install:

$ TEMPEST_DIR=/path/to/tempest
$ BLAZAR_DIR=/path/to/blazar
$ cp -R ${BLAZAR_DIR}/contrib/tempest/tempest/* ${TEMPEST_DIR}/tempest/

For example:
$ cp -R /opt/stack/blazar/contrib/tempest/tempest/* /opt/stack/tempest/tempest/

To run all the blazar tests, add the following to the tox.ini file located at TEMPEST_DIR:

[testenv:blazar]
sitepackages = True
commands =
   bash tools/pretty_tox.sh '(^tempest\.(api|scenario|thirdparty|cli)\.test_resource_reservation) {posargs}'

Then, inside the TEMPEST_DIR, run:
$ tox -eblazar

To debug tests with pdb or ipdb debuggers, run the following:
$ python -m testtools.run tempest."modules_to_your_test_file"."test_file_name"."your_test_suite_name"
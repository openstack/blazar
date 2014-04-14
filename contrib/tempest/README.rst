This directory contains the files necessary for tempest to cover Climate project.

To install:

$ TEMPEST_DIR=/path/to/tempest
$ CLIMATE_DIR=/path/to/climate
$ cp -R ${CLIMATE_DIR}/contrib/tempest/tempest/* ${TEMPEST_DIR}/tempest/

For example:
$ cp -R /opt/stack/climate/contrib/tempest/tempest/* /opt/stack/tempest/tempest/

To run all the climate tests, add the following to the tox.ini file located at TEMPEST_DIR:

[testenv:climate]
sitepackages = True
commands =
   bash tools/pretty_tox.sh '(^tempest\.(api|scenario|thirdparty|cli)\.test_resource_reservation) {posargs}'

Then, inside the TEMPEST_DIR, run:
$ tox -eclimate

To debug tests with pdb or ipdb debuggers, run the following:
$ python -m testtools.run tempest."modules_to_your_test_file"."test_file_name"."your_test_suite_name"
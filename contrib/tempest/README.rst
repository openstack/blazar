This directory contains the files necessary for tempest to cover Climate project.

To install:

$ TEMPEST_DIR=/path/to/tempest
$ CLIMATE_DIR=/path/to/climate
$ cp -R ${CLIMATE_DIR}/contrib/tempest/tempest/* ${TEMPEST_DIR}/tempest/

For example:
$ cp -R /opt/stack/climate/contrib/tempest/tempest/* /opt/stack/tempest/tempest/

To run cli tests:
./run_tests.sh -- tempest.cli.simple_read_only.test_climate
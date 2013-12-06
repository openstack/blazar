====================
Devstack Integration
====================

This directory contains the files necessary to integrate Climate with devstack.

To install:

    $ DEVSTACK_DIR=.../path/to/devstack
    $ cp lib/climate ${DEVSTACK_DIR}/lib
    $ cp extras.d/70-climate.sh ${DEVSTACK_DIR}/extras.d

To configure devstack to run climate:

    $ cd ${DEVSTACK_DIR}
    $ echo "enable_service climate" >> localrc
    $ echo "enable_service climate-a" >> localrc
    $ echo "enable_service climate-m" >> localrc

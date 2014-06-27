====================
Devstack Integration
====================

This directory contains the files necessary to integrate Blazar with devstack.

To install:

    $ DEVSTACK_DIR=.../path/to/devstack
    $ cp lib/blazar ${DEVSTACK_DIR}/lib
    $ cp extras.d/70-blazar.sh ${DEVSTACK_DIR}/extras.d

To configure devstack to run blazar:

    $ cd ${DEVSTACK_DIR}
    $ echo "enable_service blazar" >> localrc
    $ echo "enable_service blazar-a" >> localrc
    $ echo "enable_service blazar-m" >> localrc

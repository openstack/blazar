===========================
Installation using DevStack
===========================

This section includes instructions for Blazar installation using DevStack.
DevStack configures both the host reservation and the instance reservation.

1. Download DevStack:

.. sourcecode:: console

    git clone https://opendev.org/openstack/devstack.git

..

2. Create a local.conf file in the devstack directory. You can use the
   following sample local.conf:

.. sourcecode:: console

    [[local|localrc]]
    ADMIN_PASSWORD=password
    DATABASE_PASSWORD=$ADMIN_PASSWORD
    RABBIT_PASSWORD=$ADMIN_PASSWORD
    SERVICE_PASSWORD=$ADMIN_PASSWORD
    DEST=/opt/stack/
    LOGFILE=$DEST/logs/stack.sh.log
    HOST_IP=127.0.0.1
    GIT_BASE=https://opendev.org/
    RECLONE=yes
    enable_plugin blazar https://opendev.org/openstack/blazar

..

3. Run DevStack as the stack user:

.. sourcecode:: console

    ./stack.sh

..

4. Source the admin credentials:

.. sourcecode:: console

    . openrc admin admin

..

5. Now you can add hosts to Blazar:

.. sourcecode:: console

    blazar host-create hostname

..

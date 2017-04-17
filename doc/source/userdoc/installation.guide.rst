Installation using DevStack
===========================

This section includes instructions for Blazar installation using DevStack.

1. Download DevStack:

.. sourcecode:: console

    git clone https://git.openstack.org/openstack-dev/devstack.git

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
    GIT_BASE=https://git.openstack.org/
    RECLONE=yes
    enable_plugin blazar https://git.openstack.org/openstack/blazar

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

Installation without DevStack
=============================

This section includes instructions for Blazar installation.

Download all Blazar related repos:

.. sourcecode:: console

   git clone https://git.openstack.org/openstack/blazar
   git clone https://git.openstack.org/openstack/blazar-nova
   git clone https://git.openstack.org/openstack/python-blazarclient

..

Install all these projects to your working environment via:

.. sourcecode:: console

    python setup.py install

..

or

.. sourcecode:: console

    python setup.py develop

..

Next you need to create a Blazar policy file:

.. sourcecode:: console

    cp /path/to/blazar/etc/policy.json /etc/blazar/

..

Next you need to configure Blazar and Nova. First, generate a blazar.conf sample:

.. sourcecode:: console

    cd /path/to/blazar
    tox -e genconfig
    mv etc/blazar/blazar.conf.sample /etc/blazar/blazar.conf

..

Then edit */etc/blazar/blazar.conf* using the following example:

.. sourcecode:: console

    [DEFAULT]
    host=<blazar_host>
    port=<blazar_port>
    os_auth_host=<auth_host>
    os_auth_port=<auth_port>
    os_auth_protocol=<http, for example>
    os_auth_version=v3
    os_admin_username=<username>
    os_admin_password=<password>
    os_admin_project_name=<project_name>
    identity_service=identityv3

    [manager]
    plugins=physical.host.plugin

    [keystone_authtoken]
    auth_uri=<auth_uri>

    [physical:host]
    aggregate_freepool_name=freepool
    project_id_key=blazar:project
    blazar_owner=blazar:owner
    blazar_az_prefix=blazar:

..

Here *os_admin_** flags refer to the Blazar service user. *blazar_** ones - to
an admin user created specially to work with physical reservations. If you do
not have these users, create them:

.. sourcecode:: console

    openstack user create --password <password> --project <project_name> --email <email-address> <username>
    openstack role add --project <project_name> --user <username> <admin_role>

..

And the same procedure for special admin user to work with physical
reservations.

Next you need to configure Nova. If you want to use physical reservations,
please add the following lines to nova.conf file:

.. sourcecode:: console

    scheduler_available_filters = nova.scheduler.filters.all_filters
    scheduler_available_filters = blazarnova.scheduler.filters.blazar_filter.BlazarFilter
    scheduler_default_filters=RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,BlazarFilter

..

Restart nova-scheduler to use the new configuration file.

Next you need to create a Nova aggregate to use as a free pool for host
reservation:

.. sourcecode:: console

    openstack aggregate create freepool

..

Blazar uses Keystone trusts to commit actions on behalf of user-created leases.
That's why we need to create identityv3 service with appropriate endpoints:

.. sourcecode:: console

    openstack service create --name keystonev3 --description "Keystone Identity Service v3" identityv3
    openstack endpoint create --region <region> keystonev3 public "<auth_protocol>://<auth_host>:<auth_port>/v3"
    openstack endpoint create --region <region> keystonev3 admin "<auth_protocol>://<auth_host>:<auth_port>/v3"
    openstack endpoint create --region <region> keystonev3 internal "<auth_protocol>://<auth_host>:<auth_port>/v3"

..

And we need to create the reservation service in Keystone with its endpoints:

.. sourcecode:: console

    openstack service create --name blazar --description “OpenStack Reservation Service” reservation
    openstack endpoint create --region <region> blazar public "<auth_protocol>://<blazar_host>:<blazar_port>/v1"
    openstack endpoint create --region <region> blazar public "<auth_protocol>://<blazar_host>:<blazar_port>/v1"
    openstack endpoint create --region <region> blazar public "<auth_protocol>://<blazar_host>:<blazar_port>/v1"

..

And, finally, we need to create a database for Blazar:

.. sourcecode:: console

    mysql -u<user> -p<password> -h<host> -e "DROP DATABASE IF EXISTS blazar;"
    mysql -u<user> -p<password> -h<host> -e "CREATE DATABASE blazar CHARACTER SET utf8;"

..

Then edit the database section of */etc/blazar/blazar.conf*:

.. sourcecode:: console

    [database]
    connection=mysql+pymysql://<user>:<password>@<host>/blazar?charset=utf8

..

To start Blazar services use:

.. sourcecode:: console

    blazar-api --config-file /etc/blazar/blazar.conf
    blazar-manager --config-file /etc/blazar/blazar.conf

..

Now you can use python-blazarclient to communicate with Blazar.


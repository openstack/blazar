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

    climate host-create hostname

..

Installation without DevStack
=============================

This section includes instructions for Blazar installation.

Download all Blazar related repos:

.. sourcecode:: console

   git clone https://github.com/stackforge/blazar.git
   git clone https://github.com/stackforge/blazar-nova.git
   git clone https://github.com/stackforge/python-blazarclient.git

..

Install all these projects to your working environment via:

.. sourcecode:: console

    python setup.py install

..

or

.. sourcecode:: console

    python setup.py develop

..

Next you need to configure Blazar and Nova. Define */etc/climate/climate.conf*
file using the following example:

.. sourcecode:: console

    [DEFAULT]
    host=<climate_host>

    os_auth_host=<auth_host>
    os_auth_port=<auth_port>
    os_auth_protocol=<http, for example>
    os_admin_username=<username>
    os_admin_password=<password>
    os_admin_project_name=<project_name>

    [manager]
    plugins=basic.vm.plugin,physical.host.plugin

    [virtual:instance]
    on_start=on_start
    on_end=create_image, delete

    [physical:host]
    on_start=on_start
    on_end=on_end
    climate_username=<username>
    climate_password=<password>
    climate_project_name=<project_name>

..

Here *os_admin_** flags refer to Blazar service user. *climate_** ones - to
admin user created specially to work with physical reservations. If you have no
these users, create them via Keystone:

.. sourcecode:: console

    keystone user-create --name=climate --pass=<service_password> --tenant_id=<service_tenant_id> --email=climate@example.com
    keystone user-role-add --tenant-id <service_tenant_id> --user-id <climate_user> --role-id <admin_role>

..

And the same procedure for special admin user to work with physical
reservations.

Next you need to configure Nova. If you want to use physical reservations,
please add the following lines to nova.conf file:

.. sourcecode:: console

    scheduler_available_filters = nova.scheduler.filters.all_filters
    scheduler_available_filters = climatenova.scheduler.filters.climate_filter.ClimateFilter
    scheduler_default_filters=RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,ClimateFilter

..

Restart nova-api and nova-scheduler to use new configuration file.

Blazar uses Keystone trusts to commit actions on behalf of user created lease.
That’s why we need to create identityv3 service with appropriate endpoints:

.. sourcecode:: console

    keystone service-create --name keystonev3 --type identityv3 --description "Keystone Identity Service v3"
    keystone endpoint-create --region <region> --service keystonev3 --publicurl "<auth_protocol>://<auth_host>:5000/v3" --adminurl "<auth_protocol>://<auth_host>:35357/v3" --internalurl "<auth_protocol>://<auth_host>:5000/v3"

..

And, finally, we need to create reservation service in Keystone with its
endpoints:

.. sourcecode:: console

    keystone service-create --name climate --type reservation --description “OpenStack reservation service.”
    keystone endpoint-create --region <region> --service climate --publicurl "<auth_protocol>://<climate_host>:1234/v1" --adminurl "<auth_protocol>://<climate_host>:1234/v1"

..

To start Blazar services use:

.. sourcecode:: console

    climate-api
    climate-manager

..

Now you can use python-blazarclient to communicate with Blazar.


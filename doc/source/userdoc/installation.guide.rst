Installation using Devstack
===========================

This section includes instructions for Climate installation using Devstack.

1. Download Devstack:

.. sourcecode:: console

    git clone https://github.com/openstack-dev/devstack.git

..

2. Download Climate:

.. sourcecode:: console

    git clone https://github.com/stackforge/climate.git

..

3. Add climate files to Devstack:

.. sourcecode:: console

    cd climate/contrib/devstack
    DEVSTACK_DIR=../../../devstack
    cp lib/climate ${DEVSTACK_DIR}/lib
    cp extras.d/70-climate.sh ${DEVSTACK_DIR}/extras.d

..

4. Configure devstack to run climate by adding climate, climate api and climate
   manager to the localrc file:

.. sourcecode:: console

    cd ${DEVSTACK_DIR}
    echo "enable_service climate" >> localrc
    echo "enable_service climate-a" >> localrc
    echo "enable_service climate-m" >> localrc

..

5. Run Devstack:

.. sourcecode:: console

    ./stack.sh

..

Installation without Devstack
=============================

This section includes instructions for Climate installation.

Download all Climate related repos:

.. sourcecode:: console

   git clone https://github.com/stackforge/climate.git
   git clone https://github.com/stackforge/climate-nova.git
   git clone https://github.com/stackforge/python-climateclient.git

..

Install all these projects to your working environment via:

.. sourcecode:: console

    python setup.py install

..

or

.. sourcecode:: console

    python setup.py develop

..

Next you need to configure Climate and Nova. Define */etc/climate/climate.conf*
file using the following example:

.. sourcecode:: console

    [DEFAULT]
    host=<climate_host>

    os_auth_host=<auth_host>
    os_auth_port=<auth_port>
    os_auth_protocol=<http, for example>
    os_admin_username=<username>
    os_admin_password=<password>
    os_admin_tenant_name=<tenant_name>

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
    climate_tenant_name=<tenant_name>

..

Here *os_admin_** flags refer to Climate service user. *climate_** ones - to
admin user created specially to work with physical reservations. If you have no
these users, create them via Keystone:

.. sourcecode:: console

    keystone user-create --name=climate --pass=<service_password> --tenant_id=<service_tenant_id> --email=climate@example.com
    keystone user-role-add --tenant-id <service_tenant_id> --user-id <climate_user> --role-id <admin_role>

..

And the same procedure for special admin user to work with physical
reservations.

Next you need to configure Nova. If you want to use virtual reservations,
please add the following lines to nova.conf file:

.. sourcecode:: console

    osapi_compute_extension = nova.api.openstack.compute.contrib.standard_extensions
    osapi_compute_extension = climatenova.api.extensions.default_reservation.Default_reservation
    osapi_compute_extension = climatenova.api.extensions.reservation.Reservation

..

If you want to use physical reservations add these ones:

.. sourcecode:: console

    scheduler_available_filters = nova.scheduler.filters.all_filters
    scheduler_available_filters = climatenova.scheduler.filters.climate_filter.ClimateFilter
    scheduler_default_filters=RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,ClimateFilter

..

Restart nova-api and nova-scheduler to use new configuration file.

Climate uses Keystone trusts to commit actions on behalf of user created lease.
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

To start Climate services use:

.. sourcecode:: console

    climate-api
    climate-manager

..

Now you can use python-climateclient to communicate with Climate.


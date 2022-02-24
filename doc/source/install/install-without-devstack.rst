=============================
Installation without DevStack
=============================

This section includes instructions for Blazar installation.
You can use the host reservation and the instance reservation once
you finish the install guide.

Download all Blazar related repos:

.. sourcecode:: console

   git clone https://opendev.org/openstack/blazar
   git clone https://opendev.org/openstack/blazar-nova
   git clone https://opendev.org/openstack/python-blazarclient

..

Install all these projects to your working environment via:

.. sourcecode:: console

    python setup.py install

..

or

.. sourcecode:: console

    python setup.py develop

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
    identity_service=<identity_service_name>
    os_region_name=<region_name>

    [manager]
    plugins=physical.host.plugin,virtual.instance.plugin

    [keystone_authtoken]
    auth_type=<password, for example>
    project_domain_name=<project_domain_name>
    project_name=<project_name>
    user_domain_name=<user_domain_name>
    username=<username>
    password=<password>
    auth_url=<identity_service_url>

..

*os_admin_** flags refer to the Blazar service user. If you do not have this
user, create it:

.. sourcecode:: console

    openstack user create --password <password> --project <project_name> --email <email-address> <username>
    openstack role add --project <project_name> --user <username> <admin_role>

..

Next you need to configure Nova. Please add the following lines to nova.conf file:

.. sourcecode:: console

    [filter_scheduler]
    available_filters = nova.scheduler.filters.all_filters
    available_filters = blazarnova.scheduler.filters.blazar_filter.BlazarFilter
    enabled_filters = AvailabilityZoneFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,ServerGroupAntiAffinityFilter,ServerGroupAffinityFilter,SameHostFilter,DifferentHostFilter,BlazarFilter

..

Restart nova-scheduler to use the new configuration file.

Next you need to create a Nova aggregate to use as a free pool for host
reservation:

.. sourcecode:: console

    openstack aggregate create freepool

..

And we need to create the reservation service in Keystone with its endpoints:

.. sourcecode:: console

    openstack service create --name blazar --description "OpenStack Reservation Service" reservation
    openstack endpoint create --region <region> blazar admin "<auth_protocol>://<blazar_host>:<blazar_port>/v1"
    openstack endpoint create --region <region> blazar internal "<auth_protocol>://<blazar_host>:<blazar_port>/v1"
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

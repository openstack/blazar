=======================
Floating IP Reservation
=======================

Prerequisites
-------------

The following packages should be installed:

* blazar
* neutron
* python-blazarclient

The floating IP plugin should be enabled in ``blazar.conf``:

.. sourcecode:: console

 [manager]
 plugins = virtual.floatingip.plugin

..

1. Create reservable floating IPs
---------------------------------

1. The operator should create floating IPs as reservable resources using the
   floatingip-create command. They must select floating IPs that are not part
   of an allocation pool in Neutron. For example, to create a reservable
   floating IP with address ``172.24.4.101`` from the Neutron network with ID
   ``81fabec7-00ae-497a-b485-72f4bf187d3e``, run:

.. sourcecode:: console

 blazar floatingip-create 81fabec7-00ae-497a-b485-72f4bf187d3e 172.24.4.101

..

2. Check reservable floating IPs:

.. sourcecode:: console

 blazar floatingip-list

..

Result:

.. sourcecode:: console

 +--------------------------------------+---------------------+--------------------------------------+
 | id                                   | floating_ip_address | floating_network_id                  |
 +--------------------------------------+---------------------+--------------------------------------+
 | 67720c36-4d53-41e6-acec-7d3fb9436fd5 | 172.24.4.101        | 81fabec7-00ae-497a-b485-72f4bf187d3e |
 +--------------------------------------+---------------------+--------------------------------------+

..

2. Create a lease
-----------------

1. Create a lease (floating IP reservation) using the lease-create command.
   Note that ``python-blazarclient`` version 2.2.0 or greater is required to
   use this feature.

.. sourcecode:: console

 blazar lease-create --reservation resource_type=virtual:floatingip,network_id=81fabec7-00ae-497a-b485-72f4bf187d3e,amount=1 fip-lease

..

Result:

.. sourcecode:: console

 Created a new lease:
 +--------------+-------------------------------------------------------------+
 | Field        | Value                                                       |
 +--------------+-------------------------------------------------------------+
 | created_at   | 2019-08-27 10:49:22                                         |
 | degraded     | False                                                       |
 | end_date     | 2019-08-28T10:49:00.000000                                  |
 | events       | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "8410ba04-7c5a-46c8-ae1d-92036cf05dc6",     |
 |              |     "event_type": "start_lease",                            |
 |              |     "created_at": "2019-08-27 10:49:22",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-08-27T10:49:00.000000",                   |
 |              |     "id": "56f2561c-f321-4415-8ddf-ab92a435f879"            |
 |              | }                                                           |
 |              | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "8410ba04-7c5a-46c8-ae1d-92036cf05dc6",     |
 |              |     "event_type": "before_end_lease",                       |
 |              |     "created_at": "2019-08-27 10:49:22",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-08-28T09:49:00.000000",                   |
 |              |     "id": "8958c2e3-fbaf-4275-9b79-9742bd23286c"            |
 |              | }                                                           |
 |              | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "8410ba04-7c5a-46c8-ae1d-92036cf05dc6",     |
 |              |     "event_type": "end_lease",                              |
 |              |     "created_at": "2019-08-27 10:49:22",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-08-28T10:49:00.000000",                   |
 |              |     "id": "b69017c4-7943-40aa-921f-62aeef04feac"            |
 |              | }                                                           |
 | id           | 8410ba04-7c5a-46c8-ae1d-92036cf05dc6                        |
 | name         | fip-lease                                                   |
 | project_id   | e3326e5bb5734e46be37a6c868776537                            |
 | reservations | {                                                           |
 |              |     "status": "pending",                                    |
 |              |     "lease_id": "8410ba04-7c5a-46c8-ae1d-92036cf05dc6",     |
 |              |     "resource_id": "81b94874-254b-41ec-9fcc-752b8e112df4",  |
 |              |     "network_id": "81fabec7-00ae-497a-b485-72f4bf187d3e",   |
 |              |     "created_at": "2019-08-27 10:49:22",                    |
 |              |     "updated_at": "2019-08-27 10:49:22",                    |
 |              |     "required_floatingips": [],                             |
 |              |     "missing_resources": false,                             |
 |              |     "amount": 1,                                            |
 |              |     "id": "2fef4ef9-fc29-40f8-bfc4-5c9952b83743",           |
 |              |     "resource_type": "virtual:floatingip",                  |
 |              |     "resources_changed": false                              |
 |              | }                                                           |
 | start_date   | 2019-08-27T10:49:00.000000                                  |
 | status       | PENDING                                                     |
 | trust_id     | 8cefb806bb0c40ceb1407d192fb27014                            |
 | updated_at   | 2019-08-27 10:49:22                                         |
 | user_id      | 9a74fa556c654f8fb0050f240201363f                            |
 +--------------+-------------------------------------------------------------+

..

2. Check leases:

.. sourcecode:: console

 blazar lease-list

..

Result:

.. sourcecode:: console

 +--------------------------------------+-----------+----------------------------+----------------------------+
 | id                                   | name      | start_date                 | end_date                   |
 +--------------------------------------+-----------+----------------------------+----------------------------+
 | 8410ba04-7c5a-46c8-ae1d-92036cf05dc6 | fip-lease | 2019-08-27T10:49:00.000000 | 2019-08-28T10:49:00.000000 |
 +--------------------------------------+-----------+----------------------------+----------------------------+

..

3. Use the leased resources
---------------------------

1. Once the lease becomes active, the allocated floating IPs are tagged with
   the reservation ID, in this case ``2fef4ef9-fc29-40f8-bfc4-5c9952b83743``,
   and can be displayed with the following command:

.. sourcecode:: console

 openstack floating ip list --tags reservation:2fef4ef9-fc29-40f8-bfc4-5c9952b83743

..

Result:

.. sourcecode:: console

 +--------------------------------------+---------------------+------------------+------+--------------------------------------+----------------------------------+
 | ID                                   | Floating IP Address | Fixed IP Address | Port | Floating Network                     | Project                          |
 +--------------------------------------+---------------------+------------------+------+--------------------------------------+----------------------------------+
 | 5a5b026b-18a0-4ec7-b76d-642a0e8dc582 | 172.24.4.101        | None             | None | 81fabec7-00ae-497a-b485-72f4bf187d3e | e3326e5bb5734e46be37a6c868776537 |
 +--------------------------------------+---------------------+------------------+------+--------------------------------------+----------------------------------+

..

2. Use the reserved floating IP like a regular one, for example by attaching it
   to an instance with ``openstack server add floating ip``.

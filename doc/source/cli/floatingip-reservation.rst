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
   floating IP with address ``172.24.4.2`` from the Neutron network with ID
   ``81fabec7-00ae-497a-b485-72f4bf187d3e``, run:

.. sourcecode:: console

 # Using the blazar CLI
 blazar floatingip-create 81fabec7-00ae-497a-b485-72f4bf187d3e 172.24.4.2

 # Using the openstack CLI
 openstack reservation floatingip create 81fabec7-00ae-497a-b485-72f4bf187d3e 172.24.4.2

..

2. Check reservable floating IPs:

.. sourcecode:: console

 # Using the blazar CLI
 blazar floatingip-list

 # Using the openstack CLI
 openstack reservation floatingip list

..

Result:

.. sourcecode:: console

 +--------------------------------------+---------------------+--------------------------------------+
 | id                                   | floating_ip_address | floating_network_id                  |
 +--------------------------------------+---------------------+--------------------------------------+
 | 67720c36-4d53-41e6-acec-7d3fb9436fd5 | 172.24.4.2          | 81fabec7-00ae-497a-b485-72f4bf187d3e |
 +--------------------------------------+---------------------+--------------------------------------+

..

2. Create a lease
-----------------

1. Create a lease (floating IP reservation) using the lease-create command.
   Note that ``python-blazarclient`` version 2.2.1 or greater is required to
   use this feature. When you use ``resource_type=virtual:floatingip``, the
   following parameters are supported:

   * ``network_id``: UUID of the external network to reserve from (required)
   * ``amount``: number of floating IPs to reserve (optional, defaults to 1)
   * ``required_floatingips``: list of specific floating IPs to allocate (optional, must be formatted as a JSON array)

.. sourcecode:: console

 # Using the blazar CLI
 blazar lease-create --reservation 'resource_type=virtual:floatingip,network_id=81fabec7-00ae-497a-b485-72f4bf187d3e,amount=2,required_floatingips=["172.24.4.2","172.24.4.3"]' fip-lease

 # Using the openstack CLI
 openstack reservation lease create --reservation 'resource_type=virtual:floatingip,network_id=81fabec7-00ae-497a-b485-72f4bf187d3e,amount=2,required_floatingips=["172.24.4.2","172.24.4.3"]' fip-lease

..

Result:

.. sourcecode:: console

 Created a new lease:
 +--------------+-------------------------------------------------------------+
 | Field        | Value                                                       |
 +--------------+-------------------------------------------------------------+
 | created_at   | 2019-09-23 08:33:22                                         |
 | degraded     | False                                                       |
 | end_date     | 2019-09-24T08:33:00.000000                                  |
 | events       | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "d67f3bcf-cb82-4c7d-aa4d-49cc48586d89",     |
 |              |     "event_type": "before_end_lease",                       |
 |              |     "created_at": "2019-09-23 08:33:22",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-09-24T07:33:00.000000",                   |
 |              |     "id": "628e6eec-d157-4e6a-9238-47c008f357be"            |
 |              | }                                                           |
 |              | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "d67f3bcf-cb82-4c7d-aa4d-49cc48586d89",     |
 |              |     "event_type": "end_lease",                              |
 |              |     "created_at": "2019-09-23 08:33:22",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-09-24T08:33:00.000000",                   |
 |              |     "id": "d8a56235-3171-4097-8dd6-425788f4dd73"            |
 |              | }                                                           |
 |              | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "d67f3bcf-cb82-4c7d-aa4d-49cc48586d89",     |
 |              |     "event_type": "start_lease",                            |
 |              |     "created_at": "2019-09-23 08:33:22",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-09-23T08:33:00.000000",                   |
 |              |     "id": "f7322caf-9470-4281-b980-dcd76b3e476c"            |
 |              | }                                                           |
 | id           | d67f3bcf-cb82-4c7d-aa4d-49cc48586d89                        |
 | name         | fip-lease                                                   |
 | project_id   | 10b4b88b67e141aeb093fec48c93232c                            |
 | reservations | {                                                           |
 |              |     "status": "pending",                                    |
 |              |     "lease_id": "d67f3bcf-cb82-4c7d-aa4d-49cc48586d89",     |
 |              |     "resource_id": "ae205735-970e-4f91-a2fc-c99fc7cc45fc",  |
 |              |     "network_id": "81fabec7-00ae-497a-b485-72f4bf187d3e",   |
 |              |     "created_at": "2019-09-23 08:33:22",                    |
 |              |     "updated_at": "2019-09-23 08:33:22",                    |
 |              |     "required_floatingips": [                               |
 |              |         "172.24.4.2",                                       |
 |              |         "172.24.4.3"                                        |
 |              |     ],                                                      |
 |              |     "missing_resources": false,                             |
 |              |     "amount": 2,                                            |
 |              |     "id": "30f72423-db81-4f13-bc78-b931c4a96b48",           |
 |              |     "resource_type": "virtual:floatingip",                  |
 |              |     "resources_changed": false                              |
 |              | }                                                           |
 | start_date   | 2019-09-23T08:33:00.000000                                  |
 | status       | PENDING                                                     |
 | trust_id     | 0617c18ba83d4ec29832b0ec19c5ae5e                            |
 | updated_at   | 2019-09-23 08:33:23                                         |
 | user_id      | 9e43ffa598d14bac91fc889c2e15cd13                            |
 +--------------+-------------------------------------------------------------+

..

2. Check leases:

.. sourcecode:: console

 # Using the blazar CLI
 blazar lease-list

 # Using the openstack CLI
 openstack reservation lease list
..

Result:

.. sourcecode:: console

 +--------------------------------------+-----------+----------------------------+----------------------------+
 | id                                   | name      | start_date                 | end_date                   |
 +--------------------------------------+-----------+----------------------------+----------------------------+
 | d67f3bcf-cb82-4c7d-aa4d-49cc48586d89 | fip-lease | 2019-09-23T08:33:00.000000 | 2019-09-24T08:33:00.000000 |
 +--------------------------------------+-----------+----------------------------+----------------------------+

..

3. Update a lease
-----------------

1. Update a lease (floating IP reservation) using the lease-update command.
   Note that ``python-blazarclient`` version 2.2.1 or greater is required to
   use this feature. After passing the existing reservation ID to the ``--reservation`` option, you can modify start or end dates as well as some reservation parameters:

   * ``amount``: you can modify the number of floating IPs to reserve. Reducing
     ``amount`` is supported only for pending reservations.
   * ``required_floatingips``: you can only reset the list of specific floating
     IPs to allocate to an empty list

.. sourcecode:: console

 # Using the blazar CLI
 blazar lease-update --reservation 'id=e80033e6-5279-461d-9573-dec137233434,amount=3,required_floatingips=[]' fip-lease

 # Using the openstack CLI
 openstack reservation lease update --reservation 'id=e80033e6-5279-461d-9573-dec137233434,amount=3,required_floatingips=[]' fip-lease

..

Result:

.. sourcecode:: console

 Updated lease: fip-lease

..

2. Check updated lease:

.. sourcecode:: console

 # Using the openstack CLI
 blazar lease-show fip-lease

 # Using the openstack CLI
 openstack reservation lease show fip-lease

..

Result:

.. sourcecode:: console

 +--------------+-------------------------------------------------------------+
 | Field        | Value                                                       |
 +--------------+-------------------------------------------------------------+
 | created_at   | 2019-09-23 08:09:51                                         |
 | degraded     | False                                                       |
 | end_date     | 2019-09-24T08:09:00.000000                                  |
 | events       | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "5d528d8d-c023-4792-ae77-cb6d4dc2c162",     |
 |              |     "event_type": "before_end_lease",                       |
 |              |     "created_at": "2019-09-23 08:09:51",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-09-24T07:09:00.000000",                   |
 |              |     "id": "352521cc-bfe9-4881-9a3e-2ac770671144"            |
 |              | }                                                           |
 |              | {                                                           |
 |              |     "status": "DONE",                                       |
 |              |     "lease_id": "5d528d8d-c023-4792-ae77-cb6d4dc2c162",     |
 |              |     "event_type": "start_lease",                            |
 |              |     "created_at": "2019-09-23 08:09:51",                    |
 |              |     "updated_at": "2019-09-23 08:10:10",                    |
 |              |     "time": "2019-09-23T08:09:00.000000",                   |
 |              |     "id": "59e1e170-660e-4a2d-a9e7-167fd5741ff5"            |
 |              | }                                                           |
 |              | {                                                           |
 |              |     "status": "UNDONE",                                     |
 |              |     "lease_id": "5d528d8d-c023-4792-ae77-cb6d4dc2c162",     |
 |              |     "event_type": "end_lease",                              |
 |              |     "created_at": "2019-09-23 08:09:51",                    |
 |              |     "updated_at": null,                                     |
 |              |     "time": "2019-09-24T08:09:00.000000",                   |
 |              |     "id": "fda0d28d-afe5-4ebb-bea0-50ab1f8d7182"            |
 |              | }                                                           |
 | id           | 5d528d8d-c023-4792-ae77-cb6d4dc2c162                        |
 | name         | fip-lease                                                   |
 | project_id   | 10b4b88b67e141aeb093fec48c93232c                            |
 | reservations | {                                                           |
 |              |     "status": "active",                                     |
 |              |     "lease_id": "5d528d8d-c023-4792-ae77-cb6d4dc2c162",     |
 |              |     "resource_id": "543a350b-c703-48c9-a97e-2e787c26e385",  |
 |              |     "network_id": "81fabec7-00ae-497a-b485-72f4bf187d3e",   |
 |              |     "created_at": "2019-09-23 08:09:51",                    |
 |              |     "updated_at": "2019-09-23 08:10:10",                    |
 |              |     "required_floatingips": [],                             |
 |              |     "missing_resources": false,                             |
 |              |     "amount": 3,                                            |
 |              |     "id": "e80033e6-5279-461d-9573-dec137233434",           |
 |              |     "resource_type": "virtual:floatingip",                  |
 |              |     "resources_changed": false                              |
 |              | }                                                           |
 | start_date   | 2019-09-23T08:09:00.000000                                  |
 | status       | ACTIVE                                                      |
 | trust_id     | 707391571cd14bd9bfc8eaf986163b37                            |
 | updated_at   | 2019-09-23 08:15:51                                         |
 | user_id      | 9e43ffa598d14bac91fc889c2e15cd13                            |
 +--------------+-------------------------------------------------------------+

..

4. Use the leased resources
---------------------------

1. Once the lease becomes active, the allocated floating IPs are tagged with
   the reservation ID, in this case ``e80033e6-5279-461d-9573-dec137233434``,
   and can be displayed with the following command:

.. sourcecode:: console

 openstack floating ip list --tags reservation:e80033e6-5279-461d-9573-dec137233434

..

Result:

.. sourcecode:: console

 +--------------------------------------+---------------------+------------------+------+--------------------------------------+----------------------------------+
 | ID                                   | Floating IP Address | Fixed IP Address | Port | Floating Network                     | Project                          |
 +--------------------------------------+---------------------+------------------+------+--------------------------------------+----------------------------------+
 | 3954b799-4957-4e9f-96b7-46f72604c973 | 172.24.4.4          | None             | None | 81fabec7-00ae-497a-b485-72f4bf187d3e | 10b4b88b67e141aeb093fec48c93232c |
 | ae26069c-f7e9-4b8d-8ca0-6770c025dfae | 172.24.4.3          | None             | None | 81fabec7-00ae-497a-b485-72f4bf187d3e | 10b4b88b67e141aeb093fec48c93232c |
 | b427c171-30fe-45c4-a00b-3d5ca9b00306 | 172.24.4.2          | None             | None | 81fabec7-00ae-497a-b485-72f4bf187d3e | 10b4b88b67e141aeb093fec48c93232c |
 +--------------------------------------+---------------------+------------------+------+--------------------------------------+----------------------------------+

..

2. Use the reserved floating IP like a regular one, for example by attaching it
   to an instance with ``openstack server add floating ip``.

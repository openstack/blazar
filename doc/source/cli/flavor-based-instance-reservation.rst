=================================
Flavor-based Instance Reservation
=================================

Prerequisites
-------------

The following packages should be installed:

* blazar
* blazar-nova
* python-blazarclient

1. Add hosts into the freepool
------------------------------

1. Add hosts into the Blazar freepool using the host-create command:

.. sourcecode:: console

 # Using the blazar CLI
 blazar host-create compute-1

 # Using the openstack CLI
 openstack reservation host create compute-1

..

2. Check hosts in the freepool:

.. sourcecode:: console

 # Using the blazar CLI
 blazar host-list

 # Using the openstack CLI
 openstack reservation host list

..

Result:

.. sourcecode:: console

    +----+---------------------+-------+-----------+----------+
    | id | hypervisor_hostname | vcpus | memory_mb | local_gb |
    +----+---------------------+-------+-----------+----------+
    | 1  | compute-1           |     2 |      3951 |       38 |
    +----+---------------------+-------+-----------+----------+

..

2. Create a lease
-----------------

1. Create a lease (instance reservation) using lease-create command:

.. sourcecode:: console

 # Using the blazar CLI
 blazar lease-create --reservation resource_type=flavor:instance,flavor_id=3,amount=1 --start-date "2024-08-23 12:00" --end-date "2024-09-08 13:00" lease-1

 # Using the openstack CLI
 openstack reservation lease create --reservation resource_type=flavor:instance,flavor_id=3,amount=1 --start-date "2024-08-23 14:00" --end-date "2024-09-08 15:00" lease-1

..

Result:

.. sourcecode:: console

    +--------------+-------------------------------------------------------------------------------------------------------------------------------------+
    | Field        | Value                                                                                                                               |
    +--------------+-------------------------------------------------------------------------------------------------------------------------------------+
    | created_at   | 2024-08-23 12:40:53                                                                                                                 |
    | degraded     | False                                                                                                                               |
    | end_date     | 2024-09-08T15:00:00.000000                                                                                                          |
    | events       | {                                                                                                                                   |
    |              |     "id": "29e939d9-a158-4376-86d7-5093c3a379cb",                                                                                   |
    |              |     "lease_id": "d7779e56-2b78-4465-8f19-9cc916d97b11",                                                                             |
    |              |     "event_type": "end_lease",                                                                                                      |
    |              |     "time": "2024-09-08T15:00:00.000000",                                                                                           |
    |              |     "status": "UNDONE",                                                                                                             |
    |              |     "created_at": "2024-08-23 12:40:53",                                                                                            |
    |              |     "updated_at": null                                                                                                              |
    |              | }                                                                                                                                   |
    |              | {                                                                                                                                   |
    |              |     "id": "6c985a6e-416a-496a-9714-ae7b2dea0753",                                                                                   |
    |              |     "lease_id": "d7779e56-2b78-4465-8f19-9cc916d97b11",                                                                             |
    |              |     "event_type": "before_end_lease",                                                                                               |
    |              |     "time": "2024-09-08T14:00:00.000000",                                                                                           |
    |              |     "status": "UNDONE",                                                                                                             |
    |              |     "created_at": "2024-08-23 12:40:53",                                                                                            |
    |              |     "updated_at": null                                                                                                              |
    |              | }                                                                                                                                   |
    |              | {                                                                                                                                   |
    |              |     "id": "e3308415-78b1-441d-8881-74e9569e0635",                                                                                   |
    |              |     "lease_id": "d7779e56-2b78-4465-8f19-9cc916d97b11",                                                                             |
    |              |     "event_type": "start_lease",                                                                                                    |
    |              |     "time": "2024-08-23T14:00:00.000000",                                                                                           |
    |              |     "status": "UNDONE",                                                                                                             |
    |              |     "created_at": "2024-08-23 12:40:53",                                                                                            |
    |              |     "updated_at": null                                                                                                              |
    |              | }                                                                                                                                   |
    | id           | d7779e56-2b78-4465-8f19-9cc916d97b11                                                                                                |
    | name         | lease-1                                                                                                                             |
    | project_id   | 09dd299a860b4933a2ebc271377e77a6                                                                                                    |
    | reservations | {                                                                                                                                   |
    |              |     "id": "c1fb5090-e046-42a5-8287-2aa380a8d31a",                                                                                   |
    |              |     "lease_id": "d7779e56-2b78-4465-8f19-9cc916d97b11",                                                                             |
    |              |     "resource_id": "41448036-4bd0-4b03-bd72-829ad636024b",                                                                          |
    |              |     "resource_type": "flavor:instance",                                                                                             |
    |              |     "status": "pending",                                                                                                            |
    |              |     "missing_resources": false,                                                                                                     |
    |              |     "resources_changed": false,                                                                                                     |
    |              |     "created_at": "2024-08-23 12:40:53",                                                                                            |
    |              |     "updated_at": "2024-08-23 12:40:53",                                                                                            |
    |              |     "vcpus": 2,                                                                                                                     |
    |              |     "memory_mb": 4096,                                                                                                              |
    |              |     "disk_gb": 40,                                                                                                                  |
    |              |     "amount": 1,                                                                                                                    |
    |              |     "affinity": null,                                                                                                               |
    |              |     "resource_properties": "{\"id\": \"3\", \"name\": \"m1.medium\", \"ram\": 4096, \"disk\": 40, \"swap\": \"\", \"OS-FLV-EXT-     |
    |              | DATA:ephemeral\": 0, \"OS-FLV-DISABLED:disabled\": false, \"vcpus\": 2, \"os-flavor-access:is_public\": true, \"rxtx_factor\": 1.0, |
    |              | \"extra_specs\": {\"hw_rng:allowed\": \"True\"}}",                                                                                  |
    |              |     "flavor_id": "c1fb5090-e046-42a5-8287-2aa380a8d31a",                                                                            |
    |              |     "aggregate_id": 6,                                                                                                              |
    |              |     "server_group_id": null                                                                                                         |
    |              | }                                                                                                                                   |
    | start_date   | 2024-08-23T14:00:00.000000                                                                                                          |
    | status       | PENDING                                                                                                                             |
    | trust_id     | 8023d766983a493c898991430493e81a                                                                                                    |
    | updated_at   | 2024-08-23 12:40:53                                                                                                                 |
    | user_id      | 3ecacbbc4acc467faa664ee26eea115d                                                                                                    |
    +--------------+-------------------------------------------------------------------------------------------------------------------------------------+

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

    +--------------------------------------+---------+----------------------------+----------------------------+
    | id                                   | name    | start_date                 | end_date                   |
    +--------------------------------------+---------+----------------------------+----------------------------+
    | d7779e56-2b78-4465-8f19-9cc916d97b11 | lease-1 | 2024-08-23T14:00:00.000000 | 2024-09-08T15:00:00.000000 |
    +--------------------------------------+---------+----------------------------+----------------------------+

..

3. Use the leased resources
---------------------------

While the reservation you created is active you can see and use the flavor of your reservation.

.. sourcecode:: console

    openstack flavor list

..

Result:

.. sourcecode:: console

    +--------------------------------------+--------------------------------------------------+-------+------+-----------+-------+-----------+
    | ID                                   | Name                                             |   RAM | Disk | Ephemeral | VCPUs | Is Public |
    +--------------------------------------+--------------------------------------------------+-------+------+-----------+-------+-----------+
    | 1                                    | m1.tiny                                          |   512 |    1 |         0 |     1 | True      |
    | 2                                    | m1.small                                         |  2048 |   20 |         0 |     1 | True      |
    | 3                                    | m1.medium                                        |  4096 |   40 |         0 |     2 | True      |
    | 4                                    | m1.large                                         |  8192 |   80 |         0 |     4 | True      |
    | 42                                   | m1.nano                                          |   192 |    1 |         0 |     1 | True      |
    | 5                                    | m1.xlarge                                        | 16384 |  160 |         0 |     8 | True      |
    | 84                                   | m1.micro                                         |   256 |    1 |         0 |     1 | True      |
    | c1                                   | cirros256                                        |   256 |    1 |         0 |     1 | True      |
    | c1fb5090-e046-42a5-8287-2aa380a8d31a | reservation:c1fb5090-e046-42a5-8287-2aa380a8d31a |  4096 |   40 |         0 |     2 | False     |
    +--------------------------------------+--------------------------------------------------+-------+------+-----------+-------+-----------+

..

1. Create a server: Please specify the flavor of the reservation.

.. sourcecode:: console

    openstack server create --flavor c1fb5090-e046-42a5-8287-2aa380a8d31a  --image <image> --network <network> <server-name>

..

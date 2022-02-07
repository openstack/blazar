====================
Instance Reservation
====================

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

    blazar host-create compute-1

..

2. Check hosts in the freepool:

.. sourcecode:: console

    blazar host-list

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

    blazar lease-create --reservation resource_type=virtual:instance,vcpus=1,memory_mb=1024,disk_gb=20,amount=1 --start-date "2020-07-24 20:00" --end-date "2020-08-09 21:00" lease-1

..

Result:

.. sourcecode:: console

    +---------------+--------------------------------------------------------------------------------------------------------------------------+
    | Field         | Value                                                                                                                    |
    +---------------+--------------------------------------------------------------------------------------------------------------------------+
    | action        |                                                                                                                          |
    | created_at    | 2017-07-31 07:55:59                                                                                                      |
    | end_date      | 2020-08-09T21:00:00.000000                                                                                               |
    | events        | {"status": "UNDONE", "lease_id": "becf2f3b-0177-4c0f-a7e7-0123370849a3", "event_type": "end_lease", "created_at":        |
    |               | "2017-07-31 07:55:59", "updated_at": null, "time": "2020-08-09T21:00:00.000000", "id": "0f269526-c32d-4e53-bc6b-         |
    |               | 09fb7adf4354"}                                                                                                           |
    |               | {"status": "UNDONE", "lease_id": "becf2f3b-0177-4c0f-a7e7-0123370849a3", "event_type": "start_lease", "created_at":      |
    |               | "2017-07-31 07:55:59", "updated_at": null, "time": "2020-07-24T20:00:00.000000", "id": "7dbf3904-7d23-4db3-bfbd-         |
    |               | 5cc8cb9d4d92"}                                                                                                           |
    |               | {"status": "UNDONE", "lease_id": "becf2f3b-0177-4c0f-a7e7-0123370849a3", "event_type": "before_end_lease", "created_at": |
    |               | "2017-07-31 07:55:59", "updated_at": null, "time": "2020-08-07T21:00:00.000000", "id": "f16151d4-04b4-403c-              |
    |               | b0d7-f60d3810e37e"}                                                                                                      |
    | id            | becf2f3b-0177-4c0f-a7e7-0123370849a3                                                                                     |
    | name          | lease-1                                                                                                                  |
    | project_id    | 6f6f9b596d47441294eb40f565063833                                                                                         |
    | reservations  | {"status": "pending", "memory_mb": 1024, "lease_id": "becf2f3b-0177-4c0f-a7e7-0123370849a3", "disk_gb": 20,              |
    |               | "resource_id": "061198b0-53e4-4545-9d85-405ca93a7bdf", "created_at": "2017-07-31 07:55:59", "updated_at": "2017-07-31    |
    |               | 07:55:59", "aggregate_id": 3, "server_group_id": "ba03ebb4-e55c-4da4-9d39-87e13354f3b7", "amount": 1, "affinity": null,  |
    |               | "flavor_id": "db83d6fd-c69c-4259-92cf-012db2e55a58", "id": "db83d6fd-c69c-4259-92cf-012db2e55a58", "vcpus": 1,           |
    |               | "resource_type": "virtual:instance"}                                                                                     |
    | start_date    | 2020-07-24T20:00:00.000000                                                                                               |
    | status        |                                                                                                                          |
    | status_reason |                                                                                                                          |
    | trust_id      | 65da707498914c7992ee7170647a3472                                                                                         |
    | updated_at    |                                                                                                                          |
    | user_id       |                                                                                                                          |
    +---------------+--------------------------------------------------------------------------------------------------------------------------+

..

2. Check leases:

.. sourcecode:: console

    blazar lease-list

..

Result:

.. sourcecode:: console

    +--------------------------------------+---------+----------------------------+----------------------------+
    | id                                   | name    | start_date                 | end_date                   |
    +--------------------------------------+---------+----------------------------+----------------------------+
    | becf2f3b-0177-4c0f-a7e7-0123370849a3 | lease-1 | 2020-07-24T20:00:00.000000 | 2020-08-09T21:00:00.000000 |
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

    +--------------------------------------+--------------------------------------------------+-----------+------+-----------+------+-------+-------------+-----------+
    | ID                                   | Name                                             | Memory_MB | Disk | Ephemeral | Swap | VCPUs | RXTX_Factor | Is_Public |
    +--------------------------------------+--------------------------------------------------+-----------+------+-----------+------+-------+-------------+-----------+
    | 1                                    | m1.tiny                                          | 512       | 1    | 0         |      | 1     | 1.0         | True      |
    | 2                                    | m1.small                                         | 2048      | 20   | 0         |      | 1     | 1.0         | True      |
    | 3                                    | m1.medium                                        | 4096      | 40   | 0         |      | 2     | 1.0         | True      |
    | 4                                    | m1.large                                         | 8192      | 80   | 0         |      | 4     | 1.0         | True      |
    | 5                                    | m1.xlarge                                        | 16384     | 160  | 0         |      | 8     | 1.0         | True      |
    | c1                                   | cirros256                                        | 256       | 0    | 0         |      | 1     | 1.0         | True      |
    | d1                                   | ds512M                                           | 512       | 5    | 0         |      | 1     | 1.0         | True      |
    | d2                                   | ds1G                                             | 1024      | 10   | 0         |      | 1     | 1.0         | True      |
    | d3                                   | ds2G                                             | 2048      | 10   | 0         |      | 2     | 1.0         | True      |
    | d4                                   | ds4G                                             | 4096      | 20   | 0         |      | 4     | 1.0         | True      |
    | db83d6fd-c69c-4259-92cf-012db2e55a58 | reservation:db83d6fd-c69c-4259-92cf-012db2e55a58 | 1024      | 20   | 0         |      | 1     | 1.0         | False     |
    +--------------------------------------+--------------------------------------------------+-----------+------+-----------+------+-------+-------------+-----------+

..

1. Create a server: Please specify the flavor of the reservation.

.. sourcecode:: console

    openstack server create --flavor db83d6fd-c69c-4259-92cf-012db2e55a58 --image <image> --network <network> <server-name>

..

================
Host Reservation
================

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

1. Create a lease (compute host reservation) using lease-create command:

.. sourcecode:: console

 # Using the blazar CLI
 blazar lease-create --physical-reservation min=1,max=1,hypervisor_properties='[">=", "$vcpus", "2"]' --start-date "2020-06-08 12:00" --end-date "2020-06-09 12:00" lease-1

 # Using the openstack CLI
 openstack reservation lease create --reservation resource_type=physical:host,min=1,max=1,hypervisor_properties='[">=", "$vcpus", "2"]' --start-date "2020-06-08 12:00" --end-date "2020-06-09 12:00" lease-1

..

.. note::
   The :code:`--physical-reservation` flag is not available in the openstack
   client, instead use :code:`--reservation resource_type=physical:host` as
   shown above.

Result:

.. sourcecode:: console

    +---------------+---------------------------------------------------------------------------------------------------------------------------------------------+
    | Field         | Value                                                                                                                                       |
    +---------------+---------------------------------------------------------------------------------------------------------------------------------------------+
    | action        |                                                                                                                                             |
    | created_at    | 2020-06-08 02:43:40                                                                                                                         |
    | end_date      | 2020-06-09T12:00:00.000000                                                                                                                  |
    | events        | {"status": "UNDONE", "lease_id": "6638c31e-f6c8-4982-9b98-d2ca0a8cb646", "event_type": "before_end_lease", "created_at": "2020-06-08        |
    |               | 02:43:40", "updated_at": null, "time": "2020-06-08T12:00:00.000000", "id": "420caf25-dba5-4ac3-b377-50503ea5c886"}                          |
    |               | {"status": "UNDONE", "lease_id": "6638c31e-f6c8-4982-9b98-d2ca0a8cb646", "event_type": "start_lease", "created_at": "2020-06-08 02:43:40",  |
    |               | "updated_at": null, "time": "2020-06-08T12:00:00.000000", "id": "b9696139-55a1-472d-baff-5fade2c15243"}                                     |
    |               | {"status": "UNDONE", "lease_id": "6638c31e-f6c8-4982-9b98-d2ca0a8cb646", "event_type": "end_lease", "created_at": "2020-06-08 02:43:40",    |
    |               | "updated_at": null, "time": "2020-06-09T12:00:00.000000", "id": "ff9e6f52-db50-475a-81f1-e6897fdc769d"}                                     |
    | id            | 6638c31e-f6c8-4982-9b98-d2ca0a8cb646                                                                                                        |
    | name          | lease-1                                                                                                                                     |
    | project_id    | 4527fa2138564bd4933887526d01bc95                                                                                                            |
    | reservations  | {"status": "pending", "lease_id": "6638c31e-f6c8-4982-9b98-d2ca0a8cb646", "resource_id": "8", "max": 1, "created_at": "2020-06-08           |
    |               | 02:43:40", "min": 1, "updated_at": null, "hypervisor_properties": "[\">=\", \"$vcpus\", \"2\"]", "resource_properties": "", "id":           |
    |               | "4d3dd68f-0e3f-4f6b-bef7-617525c74ccb", "resource_type": "physical:host"}                                                                   |
    | start_date    | 2020-06-08T12:00:00.000000                                                                                                                  |
    | status        |                                                                                                                                             |
    | status_reason |                                                                                                                                             |
    | trust_id      | ba4c321878d84d839488216de0a9e945                                                                                                            |
    | updated_at    |                                                                                                                                             |
    | user_id       |                                                                                                                                             |
    +---------------+---------------------------------------------------------------------------------------------------------------------------------------------+

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
    | 6638c31e-f6c8-4982-9b98-d2ca0a8cb646 | lease-1 | 2020-06-08T12:00:00.000000 | 2020-06-09T12:00:00.000000 |
    +--------------------------------------+---------+----------------------------+----------------------------+

..

3. Use the leased resources
---------------------------

1. Create a server: Please specify the reservation id as a scheduler hint.

.. sourcecode:: console

    openstack server create --flavor <flavor> --image <image> --network <network> --hint reservation=4d3dd68f-0e3f-4f6b-bef7-617525c74ccb <server-name>

..

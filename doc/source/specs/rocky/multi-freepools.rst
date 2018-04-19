..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

================================
Multi Availability Zones Support
================================

https://blueprints.launchpad.net/blazar/+spec/multi-freepools

Support multiple availability zones and enable users to reserve both of hosts
and instances with aware of az.

Problem description
===================

Blazar manages hosts registered in the freepool for reservations. The freepool
is agnostic for Nova's availability zone (az) now. All hosts belong to one
freepool and reserved hosts for a reservation can be picked up from different
az in Nova. Additionally, users can't specify az the reserved hosts/instances
belong to when they create a reservation.

Use Cases
---------

* An user want to reserve instances to deploy a software cluster in one az.
* An user want to reserve hosts in specific az due to the location of the az.

Proposed change
===============

This BP enables users to specify az in the host reservation and the instance
reservation. If users specify az in their request, Blazar picks up hosts which
belong to the specified az. If not, Blazar picks up hosts as usual. For the
details of API change, please read the Rest API impact section.

Blazar records the original az information a host belongs to when operators
register a host by the create host API. The az information comes from Nova's
service list API.

For backword compatibility, this BP introduce a new config, "az_aware",
to utils.openstack.nova.py. If it's False, Blazar handles reservation requests
like before. If it's True, Blazar tracks availability zone of each hosts.

Alternatives
------------

Multi freepools approach
````````````````````````

Blazar manages multi freepools that is one-to-one mapping to each availability
zone.  Then users specify a freepool when they reserve resources if needed.

This approach also can support multiple availability zone. However, Blazar
need to introduce new API sets to create the one-to-one mapping between az
and freepool. The API set add extra tasks that operators define the mappings
before they call the create host API.

ComputeExtraCapability approach
```````````````````````````````

Operators define az infomation as ComputeExtraCapability to enable users can
specify az when they create a reservation.

The good point of this approach is there is no need to change Blazar's APIs
and config since operators only call existing APIs to create extra_capability
key and value set.

The drawback is that if Blazar automatically stores az info to
ComputeExtraCapability it's not a good place to store Nova's info queried by
Blazar. ComputeExtraCapability is a table for data specified by operators
and ComputeHost is a table for data queried by Blazar.

Data model impact
-----------------

A availability_zone column is added to the ComputeHost table. This column
stores the availability zone the host belongs to.

  .. sourcecode:: none

     ALTER TABLE computehosts ADD
         availability_zone VARCHAR(255) AFTER status;

NULL is assigned to the colum for the upgrade from Pike to later.

REST API impact
---------------

* URL: POST /v1/leases

  * Introduce the availability_zone key in physical:host and virtual:instance
    resource_type.
  * The availability_zone key is an optional parameter in request body.

Request Example:

  .. sourcecode:: json

     {
       "name": "instance-reservation-1",
       "reservations": [
         {
           "resource_type": "virtual:instance",
           "vcpus": 4,
           "memory_mb": 4096,
           "disk_gb": 10,
           "amount": 5,
           "affinity": False,
           "availability_zone", "az1"
         }
        ],
       "start": "2020-05-17 09:00"
       "end": "2020-05-17 10:00",
       "events": []
     }


Response Example:

  * The availability_zone is set to specified az name if an user sends a
    request with the key. If not, the key is set to None.

  .. sourcecode:: json

     {
       "leases": {
         "reservations": [
           {
             "id": "reservation-id",
             "status": "pending",
             "lease_id": "lease-id-1",
             "resource_id": "resource_id",
             "resource_type": "virtual:instance",
             "vcpus": 4,
             "memory_mb": 4096,
             "disk_gb": 10,
             "amount": 5,
             "affinity": False,
             "availability_zone", "az1",
             "created_at": "2017-05-01 10:00:00",
             "updated_at": "2017-05-01 11:00:00",
           }],
        ..snippet..
       }
     }


* URL: GET /v1/leases
* URL: GET /v1/leases/{lease-id}
* URL: PUT /v1/leases/{lease-id}
* URL: DELETE /v1/leases/{lease-id}

  * The change is the same as POST /v1/leases

Security impact
---------------

None

Notifications impact
--------------------

None

Other end user impact
---------------------

The original az name a hypervisor belongs to is only visible through
Blazar API. Nova returns az name based on meta data of host aggregate and
Blazar sets blazar_* az name to an aggregate of host reservation. It results
users need to call Blazar Host details API if they want to know what az value
is available in "availability_zone" key.

In most cases, only admin is allowed to configure az in Nova.
Admins/cloud providers/cloud deployers inform end users of list of az name.
So the impact described above has less impact to end users.

Performance Impact
------------------

None

Other deployer impact
---------------------

When upgrading Blazar, availability_zone column is filled by NULL. If
depoloyers set the az_aware flag to True, they need to re-create all hosts
registered in Blazar's freeppol after upgrading to store availability zone
information into computehost table. If hosts are used for a host reservation
Blazar can't find out the original az information while deployers upgrade
Blazar.

Developer impact
----------------

None

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  muroi-masahito

Other contributors:
  None

Work Items
----------

* Add availability_zone column to computehosts table
* Implement availability_zone support in the create host API
* Support availability_zone flag in blazarclient

Dependencies
============

None

Testing
=======

* Unit tests

Documentation Impact
====================

* API reference

References
==========

None

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Queens
     - Introduced
   * - Rocky
     - Re-proposed

..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

====================================
Extra specs for instance reservation
====================================

https://blueprints.launchpad.net/blazar/+spec/flavors-extra-specs

Support extra-specs in the instance reservation.

.. note:: There are two different phrases, `extra specs` and
          `resource_properties` in this spec. The two phrases refer to the same
          thing that is defined as ComputeHostExtraCapability. In this
          document, the title and the problem description use `extra specs` to
          retain the original phrase used in the BP.

Problem description
===================

Users can request vcpus, memory, disk, amount and affinity as a parameter for
instance reservation. Blazar checks whether the requested instances can be
reserved or not based on the user's request.

The demands for reserved instances are not only size of its flavor and amount,
but specific hardware spec or features. For example, some users want to reserve
GPU instances. However, the instance reservation plugin doesn't support extra specs
as a parameter.

Use Cases
---------

For NFV area, some kinds of instances need to run on specific hypervisors, like
DPDK, SR-IOV, etc. If the instance reservation doesn't support extra specs,
reserved instances could be scheduled to non-DPDK hypervisors though the user want
the instance to be scheduled to DPDK hypervisors.

For HPC area, GPGPU is common in the area. So when users reserve instances,
they may want to request GPU instances.

Proposed change
===============

Instance reservation plugin supports resource_properties key in its request
body. See the REST API impact section for the change of the request body. This
specs focuses only on supporting resource_properties matches to
ComputeHostExtraCapability.

When an user reserves instances with resource_properties, Blazar picks up
hypervisors which can accommodate the requested flavor and the resource_properties.

When admins update ComputeHostExtraCapability, Blazar re-allocates reservations
related to the updated ExtraCapability. The re-allocation strategy is the same
as used by the update_reservation API and resource-monitoring feature.


Alternatives
------------

An user directly specifies the list of hypervisors which have the specific features
in a request body. Users check which hypervisors have the features before they
create instance reservations, then they decide which hypervisors they want to
use.

This approach could be easier to implement than the proposed change since what
Blazar needs to do is just pick up hypervisors from the list.  However, the
admin can change ComputeHostExtraCapability anytime. When a specific feature
users want to use is changed, the user have to send a new list of hypervisors
again. Additionally, a cloud may be configured to forbid users from looking up
hosts and their extra capabilities.


Data model impact
-----------------

A resource_properties column is added to the InstanceReservations table. This
column stores the raw string of the resource_properties sent by users.

The change for the InstanceReservations table is as follows:

  .. sourcecode:: none

     ALTER TABLE instance_reservations ADD
         resource_properties MEDIUMTEXT AFTER affinity;

NULL is assigned to the column for the upgrade from Pike to later.


REST API impact
---------------

* URL: POST /v1/leases

  * Introduce the resource_properties key in virtual:instance resource_type

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
           "resource_properties": {
               "property_key1": "value1",
               "property_key2": "value2"
           }
         }
        ],
       "start": "2020-05-17 09:00"
       "end": "2020-05-17 10:00",
       "events": []
     }


Response Example:

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
             "resource_properties": {
                "property_key1": "value1",
                "property_key2": "value2"
             }
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

python-blazarclient needs to support resource_properties parameter in lease
handling commands.

Performance Impact
------------------

None

Other deployer impact
---------------------

None

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

* Add resource_properties column to InstanceReservation table
* Support resource_properties key in instance reservation plugin
* Add re-allocation logic to ComputeHostExtraCapability management
* Support resource_properties parameter at python-blazarclient

Dependencies
============

None

Testing
=======

* The scenario test for instance reservation should support resource_properties

Documentation Impact
====================

* API reference

References
==========

1. OPNFV Promise : http://artifacts.opnfv.org/promise/docs/development_manuals/index.html
2. resource-monitoring BP: https://blueprints.launchpad.net/blazar/+spec/resource-monitoring

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Queens
     - Introduced

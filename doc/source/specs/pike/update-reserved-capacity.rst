..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

======================================
Update a capacity of reserved resource
======================================

https://blueprints.launchpad.net/blazar/+spec/update-reserved-capacity

Support updating the capacity of an existing reservation.

Problem description
===================

The start date and the end date of a lease can be updated through the update
lease request. However, the capacity of reserved resource cannot be changed
once the reservation is created for now. The capacity should be able to be
changed for improving the flexibility of resource usage requests.

Use Cases
---------

* As Wei, I want to be able to query/update/terminate a resource usage request
  at any point in time. (Required in the capacity management development
  proposal[1])

Proposed change
===============

The update_reservation() method of a resource plugin currently checks only the
*start_date* and *end_date* of the request body. Change it to check other
parameters, e.g., min, max, hypervisor_properties and resource_properties for
the host plugin. And enable the update_reservation() method to update
allocations.

The update_reservation() succeeds if **all** of the request parameters can be
satisfied. Otherwise, it raises exceptions.

First target is the host plugin. For the host plugin, min, max,
hypervisor_properties and resource_properties can be updated if an update
request satisfies all of following conditions:

* Enough resources are available for the new request.

* Any host does not removed from the aggregate associated with the lease if the
  lease has already started. This condition is needed for preventing unexpected
  deletion and error of instances on the reserved host.

Otherwise, Blazar returns an error and nothing is updated.


Alternatives
------------

None.

Data model impact
-----------------

None.

REST API impact
---------------

* Users send a update-lease request with some parameters that they want to
  update.

Security impact
---------------

None.

Notifications impact
--------------------

None.

Other end user impact
---------------------

None.

Performance Impact
------------------

The resource allocation algorithm of resource plugins can be more complex. So
the performance impact should be carefully tested.

Other deployer impact
---------------------

None.

Developer impact
----------------

Developers of new resource plugins should consider this capability for the
update_reservation() method.

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  hiro-kobayashi

Work Items
----------

* Change the update_reservation() method of the host plugin.

Dependencies
============

None

Testing
=======

* Adds unit tests of update capacity request for the update_reservation()
  method
* Adds scenario test of update capacity request

Documentation Impact
====================

Write a release note.

References
==========

1. Capacity management development proposal: http://git.openstack.org/cgit/openstack/development-proposals/tree/development-proposals/proposed/capacity-management.rst

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Pike
     - Introduced

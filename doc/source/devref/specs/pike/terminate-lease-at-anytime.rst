..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

===========================
Terminate lease at any time
===========================

https://blueprints.launchpad.net/blazar/+spec/terminate-lease-at-anytime

Enable lease termination at any time even if the lease has already started.

Problem description
===================

Blazar does not allow any leases to be deleted if they have already started.
Though it is possible to change the end time of a lease by the lease update
request with the appropriate "end_date" parameter, a more intuitive operation
for immediate lease termination should be provided.

Use Cases
---------

* As Wei, I want to be able to query/update/terminate a resource usage request
  at any point in time. (from the `capacity management user story`_)

.. _capacity management user story: http://specs.openstack.org/openstack/openstack-user-stories/user-stories/proposed/capacity-management.html

Proposed change
===============

Support two ways for the lease termination.

1. Lease termination by the update lease request with "end_date" = "now"

   Change the update_lease() method of the ManagerService class to accept a
   request with the "end_date" parameter equal to "now." Then, the
   update_lease() method calls the on_end() method of resource plugins for
   terminating the lease.

2. Lease termination by the delete lease request

   Change the delete_lease() method of the ManagerService class to accept a
   request even if the lease has been already started. Then, the update_lease()
   method calls the on_end() method of resource plugins and delete the entry of
   the lease from the Blazar DB.

Alternatives
------------

None.

Data model impact
-----------------

None.

REST API impact
---------------

* URL: PUT /<version>/leases/<id>

  Allow the "end_date" parameter to be "now."

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

None.

Other deployer impact
---------------------

None.

Developer impact
----------------

None.

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  hiro-kobayashi

Work Items
----------

* Change the update_lease() method of the ManagerService class.
* Change the delete_lease() method of the ManagerService class.

Dependencies
============

Depends on the `on-end-options blueprint`_ because it changes the on_end
behavior of resource plugins which are called by the update_lease() and
delete_lease() method. This terminate-lease-at-anytime blueprint should be
implemented after the force-deletion feature of the on-end-options blueprint is
implemented.

.. _on-end-options blueprint: https://blueprints.launchpad.net/blazar/+spec/on-end-options

Testing
=======

* Check a lease can be terminated by the update lease request with the
  "end_date" equal to "now."
* Check a lease can be terminated and deleted by the delete lease request even
  if it has already been started.

Documentation Impact
====================

None.

References
==========

* `on-end-options blueprint`_
* `Capacity management user story`_

.. _on-end-options blueprint: https://blueprints.launchpad.net/blazar/+spec/on-end-options
.. _Capacity management user story: http://specs.openstack.org/openstack/openstack-user-stories/user-stories/proposed/capacity-management.html

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Pike
     - Introduced

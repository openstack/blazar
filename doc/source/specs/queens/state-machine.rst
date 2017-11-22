..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

=====================
Define state machines
=====================


https://blueprints.launchpad.net/blazar/+spec/state-machine

Define state machines for leases, reservations, and events, and use the status
field of the leases table which is unused for now.

Problem description
===================

Statuses of leases, reservations, and events cannot properly describe some
actual statuses because state machines for leases, reservations, and events are
not well defined for now. It causes inconsistency of statuses, unrecoverable
failures and so on.

Actually, currently leases have no status. Even though the leases table has a
status field, it is not used. It should be used to describe the status of a
lease properly.

Use Cases
---------

* A lease owner can see the exact status of the lease in the lease parameters
  included in the request response.

Proposed change
===============

Overview
--------

Define state machines of leases, reservations, and events as follows.

Lease statuses
^^^^^^^^^^^^^^

Lease statuses are categorized into 2 types: stable or transitional.
In the state machine shown below, stable statuses are drawn as black nodes
while transitional statuses are drawn as gray nodes. Stable statuses change to
transitional statuses when a specific method of the blazar manager is called.
After the method has completed or failed, the transitional statuses change to
stable statuses.

A lease has the following four stable statuses:

* **PENDING**: A lease has been successfully created and is ready to start.
  The lease stays in this status until it starts.

* **ACTIVE**: A lease has been started and is active.

* **TERMINATED**: A lease has been successfully terminated.

* **ERROR**: Unrecoverable failures happened to the lease.

Transitional statuses are as follows:

* **CREATING**: A lease is being created.

* **STARTING**: A lease is being started.

* **UPDATING**: A lease is being updated.

* **TERMINATING**: A lease is being terminated.

* **DELETING**: A lease is being deleted. Any status can change to this status
  because delete is the highest prioritized operation. e.g. when a lease hangs
  up in the STARTING status, delete should be allowed.

.. image:: ../../images/lease_statuses.png
   :width: 600 px

Reservation statuses
^^^^^^^^^^^^^^^^^^^^

A reservation has the following four statuses. Small letters are used for
backward compatibility:

* **pending**: A reservation has been successfully created and is ready to
  start. The reservation stays in this status until it starts.

* **active**: A reservation has been started and is active.

* **deleted**: Reserved resources have been successfully released.

* **error**: Unrecoverable failures happened to resources.

.. image:: ../../images/reservation_statuses.png
   :width: 600 px

Event statuses
^^^^^^^^^^^^^^

Event statuses are not changed.

.. image:: ../../images/event_statuses.png
   :width: 600 px

Relationships between statuses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following table shows conditions of statuses of reservations and events
that have to be satisfied for each lease status.

+-------------+-------------------+--------------------------+
| Lease       | Reservations      | Events                   |
+=============+===================+==========================+
| CREATING    | pending           | start_lease: UNDONE      |
|             |                   | , end_lease: UNDONE      |
+-------------+-------------------+--------------------------+
| PENDING     | pending           | start_lease: UNDONE      |
|             |                   | , end_lease: UNDONE      |
+-------------+-------------------+--------------------------+
| STARTING    | pending or active | start_lease: IN_PROGRESS |
|             | or error          | , end_lease: UNDONE      |
+-------------+-------------------+--------------------------+
| ACTIVE      | active            | start_lease: DONE        |
|             |                   | , end_lease: UNDONE      |
+-------------+-------------------+--------------------------+
| TERMINATING | active or deleted | start_lease: DONE        |
|             | or error          | , end_lease: IN_PROGRESS |
+-------------+-------------------+--------------------------+
| TERMINATED  | deleted           | start_lease: DONE        |
|             |                   | , end_lease: DONE        |
+-------------+-------------------+--------------------------+
| DELETING    | Any status        | Any status               |
+-------------+-------------------+--------------------------+
| UPDATING    | Any status        | Any status other than    |
|             |                   | IN_PROGRESS              |
+-------------+-------------------+--------------------------+


Alternatives
------------

Express resource capacity sufficiency as a lease status like *_DEGRADED
statuses and a reservation status like *_MISSING_RESOURCES and
*_RESOURCES_CHANGED.
The problem of this solution is that it complicates state machines.
Instead, we will introduce boolean flags like *degraded* to leases and
reservations for expressing such resource capacity sufficiency.
See the resource-monitoring spec[1] in detail.

Data model impact
-----------------

None

RESTAPI impact
---------------

None

Security impact
---------------

None

Notifications impact
--------------------

None

Other end user impact
---------------------

* Users can see the lease status.

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
  hiro-kobayashi

Work Items
----------

* Implement LeaseStatus, ReservationStatus and EventStatus class that contain
  statuses and basic methods for managing these statuses.
* Implement a decorator that checks/updates the lease status before/after
  *-lease methods of manager.
* Decorate *-lease methods with the decorator.

Dependencies
============

None

Testing
=======

* Test status transitions.

Documentation Impact
====================

None

References
==========

* [1] resource-monitoring blueprint: https://blueprints.launchpad.net/blazar/+spec/resource-monitoring

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Queens
     - Introduced

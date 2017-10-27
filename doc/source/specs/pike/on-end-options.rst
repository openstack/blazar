..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

=============================
Add options for on-end action
=============================

https://blueprints.launchpad.net/blazar/+spec/on-end-options

For the host reservation feature, we propose to change the behavior at the end
of a lease to force-delete running instances for avoiding failure of following
leases. In addition, we propose to add options for the action taken before the
force-deletion. Of course the owner of a lease is also free to request "update
lease" prior to the lease end time to extend the lease.

Problem description
===================

Currently, the physical host reservation feature does not terminate running
instances at the end of lease period. That can cause failures of following
leases. The solution is to delete the instances by default and provide options
for the action before the deletion, e.g. snapshot.

Use Cases
---------

* All users want Blazar to be punctual for guaranteeing fairness for all
  leases.

* A user wants to snapshot the instances of the lease if the workload does not
  finish in the lease period. Then, the user will resume the snapshotted
  instances and restart the workload at the next lease period.

* A user wants to use instances just temporarily and wants those instances to
  be auto-deleted at the end of the lease period.

Proposed change
===============

Change the on_end() method of the PhysicalHostPlugin class to delete running
instances at the end of the lease period by default.

Furthermore, support options for the action taken before the deletion. For this
purpose, extend the existing before_end_lease event which is used only for the
before_end notification for now. We plan to support the following actions for
the before_end_lease event:

* notification: Notify the lease owner that the lease will end soon. (Currently
  supported)
* snapshot: Take snapshots of running instances before deletion.
* migration: Migrate running instances.

We expect other options will be proposed in the future.

The before_end_lease event is registered and changed when creating and updating
a lease. A default before_end_lease action and the time triggering the event
can be configured. In addition, users can specify them through request
parameters.

Alternatives
------------

Use NOT the "before_end_lease" BUT the "end_lease" event for the actions like
snapshot. The end_lease event is triggered at the end of a lease for now.
Change that to be triggered at the specific time window prior to the end of a
lease. Make the length of the time window configurable.

This change may complicate event handling because the end_lease event can
trigger multiple actions, e.g., take snapshot and then delete the instance,
while the before_end_lease solution keeps one-event-to-one-action relationship.
Therefore, we prefer the before_end_lease solution.

Data model impact
-----------------

* A new attribute "before_end_action" will be added to the reservation table.

REST API impact
---------------

* Plan to update only v2 API and not to support before_end_lease related
  capabilities for v1 API.

* URL: POST /v2/leases

  * Add a new parameter "before_end_action"
  * Change the parameter "before_end_lease" to "before_end_date". This change
    is for aligning the terminology with the other parameters.

    Example:

    .. sourcecode:: json

      {
          "name": "lease_foo",
	  "start_date": "2017-3-21 15:00",
	  "end_date": "2017-03-24 15:00",
	  "before_end_date": "2017-3-24 14:00",
	  "reservations": [
	      {
	          "resource_id": "1234",
		  "min": 1,
		  "max": 3,
		  "resource_type": "physical:host",
		  "hypervisor_properties": "[\">=\", \"$memory_mb\", \"4096\"]",
		  "before_end_action": "snapshot"
	      }
	  ],
	  "events": []
      }

* URL: PUT /v2/leases

  Same changes as for the POST request.

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

* New config options will be added in the ``physical:host`` group:

  * before_end_action: Configure default action for the before_end_lease.
  * hours_before_end_lease: Configure default hours (prior to the end_lease)
    that triggers the before_end_lease action.

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

* STEP1: Change the behavior at the end of a lease to force-delete running
  instances.

* STEP2: Change the before_end_lease event to support configurable actions.

* STEP3: Change REST APIs.

Dependencies
============

None.

Testing
=======

Add the following tests:

* Unit tests

  * STEP1: Check all running instances being deleted at the end of lease.
  * STEP2: Check the before_end_lease action being triggered and completed.
  * STEP3: Check the new parameters being correctly processed.

Documentation Impact
====================

Update the following documents:

* Add a release note
* Blazar REST API docs (API v2 docs will be auto updated.)

References
==========

* Discussion log:

  * http://eavesdrop.openstack.org/meetings/blazar/2017/blazar.2017-03-07-09.00.log.html
  * http://eavesdrop.openstack.org/meetings/blazar/2017/blazar.2017-03-21-09.03.log.html

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Pike
     - Introduced

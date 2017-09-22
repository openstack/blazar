..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

===========================
Monitor states of resources
===========================

https://blueprints.launchpad.net/blazar/+spec/resource-monitoring

States of leased/reserved resources are not tracked currently. This spec
proposes a new feature that monitors the states of leased/reserved resources
and heals the lease from failure conditions.

Problem description
===================

A lease owner cannot use leased resources if the resources go down, even though
the lease was successfully created. To make matters worse, the lease owner
cannot even notice such a failure condition from the lease object because
Blazar does not track states of leased/reserved resources.

Use Cases
---------

* Lease owners expects leased resources are available if the status of the
  lease is fine.

* Admins who have a privilege of resource operations, e.g. CRUD for /v1/hosts,
  expects Blazar to notify them about failures of resources in the pool.

Proposed change
===============

Overview
--------

Blazar monitors the states of resources, and heals damaged leases.

Monitor states of resources
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Have the blazar-manager monitor states of resources. At least one of the
following two types of monitoring features should be supported for each
resource plugin.

1. Push-based monitoring

   The blazar-manager listens to notification messages sent by other
   components, e.g. sent by Nova for the host/instance plugins.
   And it picks up messages which refer to the resources managed by Blazar,
   i.e. a record of the resource is stored in the Blazar database.
   A publisher ID and topics to subscribe are provided by each resource plugin.

2. Polling-based monitoring

   The blazar-manager periodically calls a states check method of each
   resource plugin. Then, the resource plugin checks states of resources,
   e.g. *List Hypervisors* of the Compute API is used for the host/instance
   plugins. If any failure is detected, it is notified to the blazar-manager.

The blazar-manager starts monitoring after loading resource plugins. A type of
monitoring feature is configurable for each resource plugin.

Update states of resources
^^^^^^^^^^^^^^^^^^^^^^^^^^

If any failure is detected, the blazar-manager calls the resource plugin to
handle it. The resource plugin updates the field named *reservable* in the
record of the failure resource to *FALSE*. The record here means the record
stored in the resource table of the Blazar database, e.g. the record of the
computehosts table for the host/instance plugins.

Even though the computehosts table has a field named *status*, we do not use
this field because it leads to misunderstanding that the *status* field copies
the status of the hypervisor in Nova. Instead, we introduce a new boolean field
named *reservable* which is decided by the combination of the state and the
status of the hypervisor in Nova. Only if the state is *up* and the status is
*enabled*, the *reservable* field becomes *TRUE*. i.e. it becomes *FALSE* if
the state becomes *down* or the status becomes *disabled*.

Heal damaged leases
^^^^^^^^^^^^^^^^^^^

The following boolean flags are introduced for expressing resource conditions.
They are set to False by default:

* Lease

  * degraded

* Reservation

  * missing_resources
  * resources_changed

After updating the status (= *reservable* field) of the failed resource, the
resource plugin discovers leases which suffer from the failure, and tries to
heal the leases. In the healing process, the resource plugin looks for
available resources which satisfy requirements of the lease. Then, it takes
the following actions:

* Case 1. Lease is not started yet

   * Case 1-1. Enough resources are available

     Reserve new resources instead of failure resources. Although resources are
     changed, keep the *resources_changed* flag False because it does not
     affect the lease from the lease owner perspective if it is not started
     yet.

   * Case 1-2.  Alternative resource is not available

     Set the *degraded* flag of the lease and the *missing_resources* flag of
     the reservation to True.

* Case 2. Lease has been already started

   * Case 2-1. Enough resources are available:

     Set the *degraded* flag of the lease and the *resources_changed* flag of
     the reservation to True.

   * Case 2-2.  Alternative resource is not available

     Set the *degraded* flag of the lease and the *missing_resources* flag of
     the reservation to True.

Once the *degraded* and *missing_resources* flags are set True, they are kept
True even if the failed resource is recovered. To make them False, the lease
owner sends an update lease request and requested capacity have to be
satisfied. Note that the *resources_changed* flag never becomes False once it
becomes True. In this case, the *degraded* flag never becomes False, neither.

From the architectural view, resource-dependent tables like the computehosts,
computehost_allocations, computehost_reservations and instance_reservations
tables are updated by the resource plugin. General tables like leases and
reservations tables are updated by the manager.

Notifications
^^^^^^^^^^^^^

The blazar-mangaer publishes notifications if states of leases, reservations or
resources are changed.

Alternatives
------------

Other monitoring services like Monasca can be used instead. However, it is not
a good solution in terms of cross-components dependencies. Dependencies should
be reduced as much as possible.

Data model impact
-----------------

* The leases table: a new boolean field  *degraded* is added.

* The reservations table: new boolean fields  *missing_resources* and
  *resource_changed* are added.

* The computehosts table: a new boolean field *reservable* is added.

REST API impact
---------------

* With the data model changes described above, some fields included in the REST
  API response body will be changed a little.

  New fields of the response of GET /v1/<lease-id>:

  .. sourcecode:: json

      {
        "lease": {
          "degraded": false,
          "reservations": [
            {
              "missing_resources": false,
              "resources_changed": false,
            }
          ],
        }
      }

Security impact
---------------

None.

Notifications impact
--------------------

The blazar-manager sends the following two new notifications:

* Lease status change: notifies changes of the status of lease and reservations
  included in the lease.

* Resource status change: notifies the change of the status of the resource
  which is managed by Blazar. i.e. Notifies the change of the *reservable*
  field in the resource table of the Blazar database.

Other end user impact
---------------------

None.

Performance Impact
------------------

None.

Other deployer impact
---------------------

* New configuration options related to the monitoring feature like a type of
  monitoring, publisher ID and topics to subscribe will be added for each
  resource plugin.

Developer impact
----------------

All resource plugins (including new plugins supported in the future) have to
support at least one type of resource monitoring feature.


Implementation
==============

Assignee(s)
-----------

Primary assignee: hiro-kobayashi

Work Items
----------

1. Define complete set of states of a lease and a reservation. This will be
   done by the state-machine blueprint[1].

2. Implement the monitoring mechanism into the blazar-manager.

3. Change the schema of the computehosts table. Concretely, remove the
   *status* field and add a new *reservable* field.

4. Change resource look-up features, e.g. _matching_hosts() method for the host
   plugin and the pickup_hosts() method for the instance plugin, to care for
   the *reservable* field of the record in the computehosts table.

5. Implement a resource specific monitoring feature called by the
   blazar-manager into each resource plugin. Focus on a push-based monitoring
   feature of the host plugin first.

6. Implement the lease-healing feature into each resource plugin.

7. Implement the notifications feature.

8. Change the DevStack setup script to enable the monitoring feature

9. Write a user guide

Dependencies
============

* Possible states of a lease and a reservation depend on the state-machine
  blueprint[1].

Testing
=======

* Test the monitoring feature.

* Test the lease-healing feature.

Documentation Impact
====================

* This new feature should be described in the introduction document.

* The installation guide will be updated to mention how to setup the monitoring
  feature.

* API references will be updated because the response body will be changed a
  little.

References
==========

* [1] state-machine blueprint <https://blueprints.launchpad.net/blazar/+spec/state-machine>
* [2] Discussion at the Denver PTG <https://etherpad.openstack.org/p/blazar-resource-monitoring>

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Queens
     - Introduced

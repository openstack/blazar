..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

========================
New instance reservation
========================

https://blueprints.launchpad.net/blazar/+spec/new-instance-reservation

Telecom operators want to keep instance slots for varied reasons, such as
planned scale-out, maintenance works, Disaster Recovery, etc., and for high
priority VNF service on hypervisors in a specific time window in order to
accept an expected workload increase in their network, such as big events,
sports games, etc. On the other hand, they also need to keep some free
instance slots or hypervisors for non-planned scale-out against unexpected
workload increases, such as bursty traffic.

Public cloud users often get the impression of unlimited resources in
OpenStack, like instances and hypervisors, because of the scale of public
cloud providers, but the resources are in reality limited. Operators need
to handle the inconsistency.


Problem description
===================

Some problems are well described in the Capacity Management development
proposal[1]. Please check the story for details of the problems.

Use Cases
---------

As Wei the project owner of a Telco operator, I want to specify my resource
usage request for planned events. Some examples of time-based usage requests:

  * I plan to use up to 60 vCPUs and 240GB of RAM from 06/01/2017 to 08/14/2017.
  * I want guaranteed access to 4 instances with 1 vCPU, 1GB of RAM, and 10GB of
    disk. This example is similar to what would be described in the VNFD[2].


Proposed change
===============

Blazar enables users to specify the amount of instances of a particular flavor.
As described in use cases, users who reserve instances specify a tuple of
amount of instances and a flavor definition of the instances. A flavor
definition contains three pieces of information: the number of vcpus, the amount
of RAM, and the size of the disk.

A basic idea and a sequence of the change follows:

    1. A tenant user creates its reservation, in Blazar terms called a
       "lease", with a set of time frame, definitions of a flavor for reserved
       instances, and how many instances.
    2. Blazar issues a lease id to the user if the total amount of instances
       defined in the request (e.g. size of flavor times number of instances)
       is less than the amount of unused capacity for reservations in the time
       frame. Blazar leases can contain multiple reservations. Blazar checks
       whether the unused capacity can accommodate all reservations or not.
       If not, Blazar does not issue a lease id.
    3. The user creates its instances via the Nova API with the reservation id.
       The request with the id is only accepted within the reservation
       time frame.
    4. Nova creates the instance onto the hypervisor that Blazar marked as
       having capacity for the reservation.

To realize the sequence, this BP introduces a new resource plugin
"virtual:instance" for the Blazar project. The plugin will be implemented in
two phases because of the following reasons.

Short-term goal
---------------

With respect to affinity and anti-affinity rules, instance reservation only
supports anti-affinity rule reservation because affinity rule reservation
has already been achieved by host reservation. Affinity rule reservation by
host reservation feature is not an ideal goal. For the data center usage
efficiency, host reservation is not a good choice because a total amount of
resources in a reservation is usually less than one hypervisor spec. It
results in unused instance slots in the reserved hypervisors.

On the other hand, a hypervisor in the OpenStack cluster must accept total
amount of instances in one reservation, it is equal to instance size times
instance number, as affinity rule reservation. So the host reservation feature
that is already implemented can handle instance reservation with affinity rule.

Prerequisites:

  * The following three scheduler configuration values must be defined in
    nova.conf to use instance reservation:

    * AggregateInstanceExtraSpecsFilter
    * AggregateMultiTenancyIsolationFilter
    * ServerGroupAntiAffinityFilter

For the anti-affinity rule, Blazar will do the following steps:

  0. As a preparation, Blazar adds filter_tenant_id=blazar-user-id to the
     freepool aggregate to prevent non-reservation instances from being
     scheduled into the freepool.

  1. A tenant user creates their reservation, in Blazar terms called a
     "lease", with a time frame, the instance size, and how many instances.

     One "reservation" in Blazar terms represents a tuple of
     <flavor, number of instances with the flavor> and one "lease" can have
     multiple "reservations". Thus one lease can have multiple instance
     types.

  2. Blazar checks whether the reservation is acceptable during the time
     frame or not. If acceptable, Blazar records the reservation request in
     its database and updates hypervisor usage in the freepool. Then Blazar
     returns the reservation id. If not, Blazar responds that the reservation is
     not acceptable and provides additional information to the tenant, e.g.
     the number of instances reserved is greater than the instance quota.

  3. At the start time of the reservation, Blazar creates a server group,
     a flavor, and a host aggregate related to the reservation. Then it adds the
     hypervisors onto which reserved instances are scheduled to the aggregate.

     The tricks Blazar is doing here are:

      * create server group with anti-affinity policy
      * create a flavor with two extra_specs, is_public=False and flavor
        access rights to the user. The extra_specs are
        aggregate_instance_extra_specs:reservations:<reservation-id> and
        affinity_id:<server-group-id>
      * create a new host aggregate with above aggregate_instance_extra_specs
        and filter_tenant_id of the requesting user's project id
      * does not bring out the hypervisor from the freepool because other
        user's reservations also use other instance slots in the hypervisor

  4. The user fetches the server_group id by calling the flavor show API in
       Nova, then creates reserved instances with a scheduling hint, like --hint
       group=group-id, and the newly created flavor.

Scheduling mechanism in Nova
````````````````````````````

Blazar manages some host aggregates to handle instance scheduling in Nova.
Blazar expects Nova to schedule instances as follows for non-reserved
instances (usual instances), instances related to host reservation, and
instances related to instance reservation:

  * non-reserved instances: scheduled to hypervisors which are outside of both
    the freepool aggregate and reservation-related aggregates.
  * instances related to host reservation: scheduled to hypervisors which are
    inside the reservation-related aggregate. The hypervisors are not
    included in the freepool aggregate.
  * instances related to instance reservation: scheduled to hypervisors which
    are inside the reservation-related aggregate. The hypervisors are
    included in the freepool aggregate.

Nova filters used by Blazar choose hypervisors with the following rules:

  * AggregateInstanceExtraSpecsFilter picks up hypervisors from the aggregate
    related to an instance reservation based on extra_specs of the flavor, if
    the request is related to instance reservation. If not, the filter picks up
    hypervisors from neither reservation-related aggregates nor the freepool.
  * BlazarFilter picks up hypervisors from the aggregate related to a host
    reservation based on the 'reservation' scheduler hint, if the request is
    related to host reservation. If not, the filter picks up hypervisors from
    neither host reservation-related aggregates nor the freepool.
  * AggregateMultiTenancyIsolationFilter blocks requests to be scheduled to
    the freepool by users who do not have active reservation.
  * Combination of AggregateInstanceExtraSpecsFilter and
    AggregateMultiTenancyIsolationFilter enables requests using instance
    reservation to be scheduled in the corresponding aggregate.
  * ServerGroupAntiAffinityFilter ensures instance reservation related
    instances are spread on different hypervisors.

Summary of short term goal
``````````````````````````

  * Use the host reservation function for an affinity rule reservation.
  * Use the new instance reservation function for an anti-affinity rule
    reservation.
  * Create reserved instances with a reserved flavor and a scheduling hint.


Long-term goal
--------------

Instance reservation supports both affinity rule and anti-affinity rule.

The affinity rule reservation allows other instances or reservation to use
unused instance slots in reserved hypervisors. The Nova team is developing
placement API[1]. The API already has custom resource classes[2] and is now
implementing a scheduler function[3] that uses custom resources classes.
It enables operator to more efficiently manage hypervisors in the freepool.

Blazar will do the following steps:

  1. A tenant user creates their reservation, in term of Blazar called
     "lease", with a time frame, the instance size, and how many instances.
  2. Blazar checks whether the reservation is acceptable during the time
     frame or not. If acceptable, Blazar records the reservation request
     in its database and updates the usage of hypervisor in freepool. Then
     Blazar returns the reservation id. If not, Blazar responds the reservation
     is not acceptable.
  3. At the start time of the reservation, Blazar creates a custom resource
     class, a flavor, and a resource provider of the custom resource class.
  4. The user creates reserved instances with the newly created flavor.

Some functionality of the placement API is under implementation. Once the
development is finished, the Blazar team will start using the placement API.

Alternatives
------------

This feature could be achieved on the Blazar side or on the Nova side.

Blazar side approach
````````````````````
* one reservation represents one instance

In the above sequence, a tenant user creates a reservation configured only with
the instance size (e.g. flavor), reserving only one instance.

While it could technically work for users, they would need to handle a large
number of reservations at client side when they would like to use many
instances. The use case shows users would like to create multiple instances for
one reservation.

Nova side approach
``````````````````

* Pre-block the slots by stopped instances

A user creates as many instances as they want to reserve, then stops them until
start time. It would work from a user perspective.

On the other hand, from a cloud provider perspective, it is hard to accept this
method of "reservation". Stopped instances keep holding hypervisor resources,
like vCPUs, for instances while they are stopped. It means cloud providers need
to plan their hypervisor capacity to accept the total amount of usage of future
reservations. For example, if all users reserve their instance for one year in
advance, cloud providers need to plan hypervisors that can accept the total
amount of instances reserved in the next year.

Of course, we do not prevent users from stopping their instances: users can call
the stop API for their own reason and cloud provider bill them a usage fee for
the hypervisor slot usage. However, from NFV motivations, telecom operators
cannot prepare and deploy hypervisors with a large enough capacity to
accommodate future usage demand in advance.

* Prepared images for the reservation by shelved instances

A user creates as many instances as they want to reserve, then shelves them
until start time. It would work from a cloud provider perspective: shelved
instances release their hypervisor slot, so the problem described earlier in the
"stopped instance" solution would not happen.

On the other hand, from the user perspective, some problems could happen. As
described in motivation section, VNF applications need affinity or anti-affinity
rule for placement of their instances. Nova has a 'server group' API for the
affinity and anti-affinity placement, but it does not ensure the required amount
of instances can be located on the same host. Similarly, it does not ensure the
required amount of instances can be accommodated by hypervisors when hypervisors
slots are consumed by others.

Of course, cloud providers should usually plan enough resources to accommodate
user requests. However, it is hard to plan enough hypervisors to make the cloud
look like unlimited resources in NFV use cases. Requiring a very large number of
spare hypervisors is not realistic.


Data model impact
-----------------

A new table, called "instance_reservations", is introduced in the Blazar
database. The instance reservation feature uses the existing
computehost_allocations table to store allocation information. Usage of the
table is as follows:

  1. In the create lease/reservation, Blazar queries hosts that are used for
     instance reservations or are not used by any reservations during the
     reservation time window.
  2. If some hosts are already used for instance reservations, Blazar checks
     that the reserved instances could be allocated onto the hosts.
  3. If some hosts are not used by any reservation, Blazar adds a mapping of the
     reservation to computehost as computehost_allocations table.
  4. For the host reservation, the current design will never pick hosts which
     have a mapping, a reservation to hosts, during the reservation time window,
     so instance reservation does not impact host reservation queries.


The table has size of reserved flavor, vcpu, memory size in MB and disk size in
GB, amount of instances created with the flavor, and an affinity flag.

  .. sourcecode:: none

     CREATE TABLE instance_reservations (
         id VARCHAR(36) NOT NULL,
         reservation_id VARCHAR(255) NOT NULL,
         vcpus INT UNSIGNED NOT NULL,
         memory_mb INT UNSIGNED NOT NULL,
         disk_gb INT UNSIGNED NOT NULL,
         amount INT UNSIGNED NOT NULL,
         affinity BOOLEAN NOT NULL,
         flavor_id VARCHAR(36),
         aggregate_id INT,
         server_group_id VARCHAR(36),

         PRIMARY key (id),
         INDEX (id, reservation_id)
         FOREIGN KEY (reservation_id)
           REFERENCES reservations(id)
           ON DELETE CASCADE,
     );

In the short term goal, the affinity flag only supports False since instance
reservation only supports anti-affinity rule. The plugin manages multiple types
of Nova resources. The mappings with each resources to column data as follows:

  * In the db
    * reservations.resource_id is equal to instance_reservations.id

  * With Nova resources

    * flavor id is equal to reservations.id

      * the extra_spec for scheduling, aggregate_instance_extra_specs, is equal
        to prefix+reservations.id

    * aggregate name is equal to reservations.id

      * the metadata for scheduling is equal to prefix+reservations.id

    * server_group id is recorded in extra_spec of the flavor. This id will be
      removed in the long term goal, as it is better encapsulated in the Nova
      API.


REST API impact
---------------

* URL: POST /v1/leases

  * Introduce new resource_type "virtual:instance" for a reservation

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
           "affinity": false
         }
        ],
       "start": "2017-05-17 09:07"
       "end": "2017-05-17 09:10",
       "events": []
     }


Response Example:

  .. sourcecode:: json

     {
       "lease": {
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
             "affinity": false,
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

python-blazarclient needs to support resource reservations of type
virtual:instance in lease handling commands.

Performance Impact
------------------

None

Other deployer impact
---------------------

The freepool that is used in physical:host plugin is also used by the
virtual:instance plugin if the deployer activates the new plugin.

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

* Create the new table in blazar
* Create instance reservation plugin
* Change reservation_pool.py and nova_inventory.py to be more generic since both
  host_plugin and instance_plugin will use these classes
* Change BlazarFilter to pass hosts which are in instance reservation aggregates
  if the reservation's extra_spec is specified.
* Add instance reservation supports in python-blazarclient
* Add scenario tests in gate job, mainly Tempest job

Dependencies
============

For the long term goal, the Placement API needs to support custom resource
classes and a mechanism to use them for Nova scheduling.

Testing
=======

  * The following scenarios should be tested:

    * Creating an anti-affinity reservation and verify all instances belonging
      to the reservation are scheduled onto different hosts.
    * Verify that both host reservation and instance reservation pick hosts from
      the same freepool and that Blazar coordinates all reservations correctly.

Documentation Impact
====================

* API reference

References
==========

1. Capacity Management development proposal: http://git.openstack.org/cgit/openstack/development-proposals/tree/development-proposals/proposed/capacity-management.rst
2. VNFD: http://www.etsi.org/deliver/etsi_gs/NFV-IFA
3. Placement API: https://docs.openstack.org/developer/nova/placement.html
4. Custom Resource Classes: https://specs.openstack.org/openstack/nova-specs/specs/ocata/implemented/custom-resource-classes.html
5. Custom Resource Classes Filter: http://specs.openstack.org/openstack/nova-specs/specs/pike/approved/custom-resource-classes-in-flavors.html

History
=======

  .. list-table:: Revisions
     :header-rows: 1

     * - Pike
       - Introduced

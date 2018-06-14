..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

==============================================
Placement API support for instance reservation
==============================================

https://blueprints.launchpad.net/blazar/+spec/placement-api

Placement API [#placement_api]_ was introduced to Nova at the 14.0.0 Newton
release to separate API and data model for tracking resource provider
inventories and usages. It can be used for improving instance reservation.


Problem description
===================

Current instance reservation has the following constraints:

* A user has to create instance reservation with the anti-affinity policy.
  Therefore, the amount of instances in one reservation cannot be larger than
  the amount of hosts.

* A user has to specify the server group when the user launches instances on
  reserved resources. If it is not specified, more instances than the reserved
  amount are possibly launched.

Use Cases
---------

* A user wants to reserve instance resources with arbitrary affinity policy.
* A user wants to reserve more instances than the number of hosts.

Proposed change
===============

Use the `custom resource class`_ to represent reservation resources and use the
`nested resource provider`_ to manage capacity and usage of reservation
resources.
The following sections describe how Blazar interacts with Nova and Placement
for supporting instance reservation.

When creating a host:
---------------------

1. Get hypervisor information and store it into the computehosts table.

2. Create a `nested resource provider`_ as a child of the compute node
   resource provider by calling the `Create resource provider API`_. The UUID
   of the compute node resource provider can be retrieved by calling the `List
   resource providers API`_ with the **name** option query,
   e.g. ``GET /placement/resource_proiders?name=compute-1``.

   The child resource provider is referred to as *'reservation provider'* in
   the following sections.

   Create reservation provider request body example:

   ``POST /placement/resource_providers``

.. sourcecode:: json

    {
        "name": "blazar_compute-1",
        "parent_provider_uuid": "542df8ed-9be2-49b9-b4db-6d3183ff8ec8"
    }

.. note::

   "542df8ed-9be2-49b9-b4db-6d3183ff8ec8" is the UUID of the "compute-1"
   compute node.

3. Add the host into the freepool.

When creating a lease:
----------------------

1. Look for available resources with arbitrary affinity policy.
2. Update the computehost_allocations table.
3. Create a custom resource class **CUSTOM_RESERVATION_{reservation UUID}** by
   calling the `Create resource class API`_.

   Create resource class request body example:

   ``POST /placement/resource_classes``

.. sourcecode:: json

    {
        "name": "CUSTOM_RESERVATION_4D17D41A_830D_47B2_91C7_4F9FC0AE611E"
    }

.. note::

   Use upper case and under score for the custom resource class name because
   lower case and hyphen cannot be used.

4. Create a private flavor which has
   ``resources:CUSTOM_RESERVATION_{reservation UUID}=1`` in its `extra_spec`_.

.. note::

   * A host aggregate is not created for each instance reservation anymore
     because reserved hosts can be distinguished by the reservation provider
     inventory.
   * A server group is not created anymore because the proposed approach does
     not depend on the ServerGroup(Anti)AffinityFilter.

When starting a lease:
----------------------

1. Add the custom resource class **CUSTOM_RESERVATION_{reservation UUID}** into
   the reservation provider's inventory by calling the `Update resource
   provider inventories API`_ with the **total**  parameter which equals to the
   amount of instances reserved for the host.

   Update resource provider inventories request body example:

   ``PUT /placement/resource_providers/{reservation_provider_uuid}/inventories``

.. sourcecode:: json

    {
        "inventories": {
            "CUSTOM_RESERVATION_4D17D41A_830D_47B2_91C7_4F9FC0AE611E": {
                "total": 3,
                "allocation_ratio": 1.0,
                "min_unit": 1,
                "max_unit": 1,
                "step_size": 1
            },
            "snip"
        },
        "resource_provider_generation": 5
    }

.. note::

   Existing hosts which were created before this spec is implemented do not
   have the reservation provider. So, check if the reservation provider exists
   and create it if it does not exist before this step.

2. Add the lease owner's project to the private flavor access rights list.

.. note::

   The previous implementation of starting lease should be kept until the
   previous instance reservation is deprecated and completely removed. The
   previous instance reservations can be distinguished by checking the
   aggregate_id or server_group_id column in the instance_reservations table.

When launching instances (from user point of view):
---------------------------------------------------

1. A lease owner uses the private flavor and the instance is launched on the
   reserved host which has the **CUSTOM_RESERVATION_{reservation UUID}** in
   it's child resource provider inventory, i.e. reservation provider inventory.

   Consumption of **CUSTOM_RESERVATION_{reservation UUID}** resources in the
   reservation provider inventory is claimed by the Nova scheduler. It means
   that usage of reserved resources is automatically tracked by the Placement.

.. note::

   It still depends on the *BlazarFilter* though the *BlazarFilter* will be
   ideally removed in the future. The *BlazarFilter* is changed to check if
   ``resources:CUSTOM_RESERVATION_*`` is in flavor extra specs to distinguish
   the request from normal, i.e. non-reserved, instance creation requests.

   `Traits`_ or other features would be able to be used for solving
   *BlazarFilter* dependency. It would be addressed by another blueprint.

   On the other hand, dependency on the following filters are solved. These
   filters are not needed any more.

   * AggregateInstanceExtraSpecsFilter
   * AggregateMultiTenancyIsolationFilter
   * ServerGroupAntiAffinityFilter

   Note that above filters and existing logic in the BlazarFilter should be
   kept to keep backward compatibility until the previous instance reservation
   is deprecated and completely removed.

When terminating a lease:
-------------------------

1. Delete related instances and the private flavor.
2. Remove the **CUSTOM_RESERVATION_{reservation UUID}** class from the
   reservation provider's inventory by calling the `Delete resource provider
   inventory API`_.
3. Delete the **CUSTOM_RESERVATION_{reservation_UUID}** resource class by
   calling the `Delete resource class API`_.

.. note::

   The previous implementation of terminating lease should be kept until the
   previous instance reservation is deprecated and completely removed. The
   previous instance reservations can be distinguished by checking the
   aggregate_id or server_group_id column in the instance_reservations table.

When deleting a host:
---------------------

1. Delete the reservation provider which is associated with the host by
   calling the `Delete resource provider API`_.
2. Remove the host from the freepool.
3. Update the computehosts table.

.. _custom resource class: https://specs.openstack.org/openstack/nova-specs/specs/ocata/implemented/custom-resource-classes.html
.. _nested resource provider: https://specs.openstack.org/openstack/nova-specs/specs/ocata/approved/nested-resource-providers.html
.. _Create resource provider API: https://developer.openstack.org/api-ref/placement/#create-resource-provider
.. _List resource providers API: https://developer.openstack.org/api-ref/placement/#list-resource-providers
.. _Create resource class API: https://developer.openstack.org/api-ref/placement/#create-resource-class
.. _extra_spec: https://specs.openstack.org/openstack/nova-specs/specs/pike/implemented/custom-resource-classes-in-flavors.html
.. _Update resource provider inventories API: https://developer.openstack.org/api-ref/placement/#update-resource-provider-inventories
.. _Delete resource provider inventory API: https://developer.openstack.org/api-ref/placement/#delete-resource-provider-inventory
.. _Delete resource class API: https://developer.openstack.org/api-ref/placement/#delete-resource-class
.. _Traits: https://specs.openstack.org/openstack/nova-specs/specs/pike/implemented/resource-provider-traits.html
.. _Delete resource provider API: https://developer.openstack.org/api-ref/placement/#delete-resource-provider

Alternatives
------------

Dummy resources approach
^^^^^^^^^^^^^^^^^^^^^^^^

Update inventories of the general resources, e.g. VCPU, of compute nodes in the
freepool to be **zero** or **reserved**. And add dummy resources like
**CUSTOM_VCPU_{reservation UUID}** into the inventory. This approach
complicates resource usage tracking because real usage of each general resource
cannot be seen through the top level compute node inventory.

Traits approach
^^^^^^^^^^^^^^^

Use `Traits`_ to express reserved resources. The problem is that traits are
just traits and they cannot be used for managing capacity and usage of reserved
resources.

Data model impact
-----------------

The **affinity** column of the instance_reservations table is changed to allow
``NULL``. ``NULL`` means ``no affinity policy is applied`` while ``True`` means
``affinity is applied`` and ``False`` means ``anti-affinity is applied``.

.. _instance_reservations table:

The instance_reservations table:

.. sourcecode:: none

    ALTER TABLE instance_reservations
        ALTER COLUMN affinity NULL;

After the previous instance reservation is deprecated and completely removed,
drop the following columns in the instance_reservations table:

.. sourcecode:: none

    ALTER TABLE instance_reservations
        DROP COLUMN aggregate_id, server_group_id;

REST API impact
---------------

The **affinity** parameter of the `Create lease API`_ is changed to be an
optional parameter. If the **affinity** parameter is not given, no affinity
policy is applied.

.. _Create lease API: https://developer.openstack.org/api-ref/reservation/v1/index.html#create-lease

Security impact
---------------

None

Notifications impact
--------------------

None

Other end user impact
---------------------

None

Performance Impact
------------------

None

Other deployer impact
---------------------

* The Placement API has to be newer than or equal to Ver. 1.29.
* To upgrade from the previous version, run the DB upgrade script and the
  instance_reservations table schema will be updated.

Developer impact
----------------

None

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  <tetsuro>

Other contributors:
  <hiro-kobayashi>

Work Items
----------

Base:

* Update DB schema: update the instance_reservations table.
* Add placement library in blazar/utils/openstack module.

To support the host creation:

* Update the create_computehost() of the host plugin to call Placement APIs and
  update related tables.

To support the host deletion:

* Update the delete_computehost() of the host plugin to delete Placement
  related resources.

To support the lease creation:

* Update the query_available_hosts() to return how many instance can be
  launched on each available host.
* Update the pickup_hosts() to support arbitrary affinity policy.
* Update the reserve_resource() and update_reservation() to support multiple
  allocations which have the same pair of reservation_id and computehost_id.
* Update the _create_resources() of the instance plugin to create the
  **CUSTOM_RESERVATION_{reservation UUID}** class and add it into the private
  flavor extra specs.

To support starting the lease:

* Update the on_start() of the instance plugin to add the
  **CUSTOM_RESERVATION_{reservation UUID}** into the reservation provider
  inventory. The **total** parameter equals to the number of entries of the
  computehost_allocations table which have the same reservation id and
  computehost id.

To support launching reserved instances:

* Update the *BlazarFilter*.

To support termination of the lease:

* Update the on_end() of the instance plugin to remove the custom resource from
  the reservation provider inventory and delete the class itself.

Others:

* Update the api module and the python-blazarclient to support arbitrary
  affinity policies.
* Update the blazar-dashboard to support arbitrary affinity policies.
* Update documentation.

Dependencies
============

WIP: Check Placement API development status.

Testing
=======

* Add unit tests for new features of each method described in the work items
  section.
* Add test scenarios of instance reservation with the affinity policy and no
  affinity policy.

Documentation Impact
====================

* Parameter description of the Create Lease API reference will be updated.
* Instance reservation part of the Command-Line Interface Reference will be
  updated.
* Release notes will be added.

References
==========

.. [#placement_api] https://docs.openstack.org/nova/latest/user/placement.html

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Rocky
     - Introduced

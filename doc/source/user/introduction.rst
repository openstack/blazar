============
Introduction
============

Blazar is a resource reservation service for OpenStack.
Idea of creating Blazar originated with two different use cases:

* Compute host reservation (when user with admin privileges can reserve
  hardware resources that are dedicated to the sole use of a project)
* Virtual machine (instance) reservation (when user may ask reservation service
  to provide him working VM not necessarily now, but also in the future)

Now these ideas have been transformed to more general view: with Blazar, user
can request the resources of cloud environment to be provided ("leased") to his
project for specific amount of time, immediately or in the future.

Both virtual (Instances, Volumes, Networks) and hardware (full hosts with
specific characteristics of RAM, CPU, etc) resources can be allocated via
"lease".

In terms of benefits added, Resource Reservation Service will:

* improve visibility of cloud resources consumption (current and planned for
  future);
* enable cloud resource planning based on current and future demand from end
  users;
* automate the processes of resource allocation and reclaiming;
* provide energy efficiency for physical hosts (both compute and storage ones);
* potentially provide leases as billable items for which customers can be
  charged a flat fee or a premium price depending on the amount of reserved cloud
  resources and their usage.

Glossary of terms
-----------------

**Reservation** is an allocation of certain cloud resource (Nova instance, Cinder
volume, compute host, etc.) to a particular project. Speaking about virtual
reservations, we may have not only simple, solid ones (like already mentioned
instances and volumes), but also complex ones - like Heat stacks and Savanna
clusters. Reservation is characterized by status, resource type, identifier
and lease it belongs to.

**Lease** is a negotiation agreement between the provider (Blazar, using OpenStack
resources) and the consumer (user) where the former agrees to make some kind of
resources (both virtual and physical) available to the latter, based on a set of
lease terms presented by the consumer. Here lease may be described as a contract
between user and reservation service about cloud resources to be provided right
now or later. Technically speaking, lease is a group of reservations granted to
a particular project upon request. Lease is characterized by start time, end
time, set of individual reservations and associated events.

**Event** is simply something that may happen to a lease. In most simple case, event
might describe lease start and lease end. Also it might be a notification to user
(e.g. about soon lease expiration) and some extra actions.

Rationale
---------

Blazar is created to:

* manage cloud resources not only right now, but also in the future;
* have dedicated resources for a certain amount of time;
* prepare for the peak loads and perform capacity planning;
* optimize energy consumption.

Lease types (concepts)
----------------------

* **Immediate reservation**. Resources are provisioned immediately (like VM
  boot or moving host to reserved user aggregate) or not at all. If request can
  be fulfilled, lease is created and **success** status is returned. Lease
  should be marked as **active** or **to_be_started**. Otherwise (if
  request resource cannot be provisioned right now) failure status for this
  request should be returned.
* **Reservation with retries**. Mostly looks like previous variant, but in case
  of failure, user may want to have several (configurable number) retries to
  process lease creation action. In this case request will be processed till
  that will be possible to create lease but not more than set in configuration
  file number of times.
* **Best-effort reservation**. Also might have place if lease creation request
  cannot be fulfilled immediately. Best-effort mechanism starts something like
  scavenger hunt trying to find resources for reservations. For compute hosts
  reservation that makes much sense, because in case there are instances
  belonging to other project on eligible hosts, and without them there will be
  possible to reserve these hosts, Blazar may start instances migration.
  This operation can be timely and fairly complex and so different strategies
  may be applied depending on heuristic factors such as the number, type and
  state of the instances to be migrated. Also Blazar should assert that there
  are at least enough potential candidates for the migration prior to starting
  the actual migration. If Blazar decides to start migration, it returns
  **success** state and marks lease as **in_progress**, otherwise -
  **failure**. If this 'hunting' ends successfully before configurable
  timeout has passed, lease should be marked as **active**, otherwise its
  status is set to **timedout**.
* **Delayed resource acquiring** or **scheduled reservation**. In this
  reservation type, lease is created successfully if Blazar thinks there will
  be enough resources to process provisioning later (otherwise this request
  returns **failure** status). Lease is marked as **inactive** till all
  resources will be actually provisioned. That works pretty nice and
  predictable speaking about compute hosts reservation (because hosts as
  resources are got not from common cloud pool, but from admin defined pool).
  So it is possible for Blazar to predict these physical resources usage and use
  that information during lease creation. If we speak about virtual reservations,
  here situation is more complicated, because all resources are got from common
  cloud resources pool, and Blazar cannot guarantee there will be enough
  resources to provision them. In this failure case lease state will be marked
  as **error** with appropriate explanation.
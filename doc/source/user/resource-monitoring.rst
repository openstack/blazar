===================
Resource Monitoring
===================

Blazar monitors states of resources and heals reservations which are expected
to suffer from resource failure.
Resource specific functionality, e.g., calling Nova APIs, is provided as a
monitoring plugin.
The following sections describes the resource monitoring feature in detail.

Monitoring Type
===============

Blazar supports 2 types of monitoring - push-based and polling-based.

1. Push-based monitoring

   The monitor listens to notification messages sent by other components,
   e.g., sent by Nova for the host monitoring plugin.
   And it picks up messages which refer to the resources managed by Blazar.
   Event types, topics to subscribe and notification callbacks are provided by
   monitoring plugins.

2. Polling-based monitoring

   The blazar-manager periodically calls a states check method of monitoring
   plugins. Then, the monitoring plugins check states of resources, e.g.,
   *List Hypervisors* of the Compute API is used for the host monitoring
   plugin.

Admins can enable/disable these monitoring by setting configuration options.

Healing
=======

When the monitor detects a resource failure, it heals reservations which
are expected to suffer from the failure.

Flags
=====

Leases and reservations have flags that indicate states of reserved
resources. Reservations have the following two flags:

* **missing_resources**: If any resource allocated to the reservation fails
  and no alternative resource found, this flag is set *True*.

* **resources_changed**: If any resource allocated to the *active* reservation
  and alternative resource is reallocated, this flag is set *True*.

Leases have the following flag:

* **degraded**: If the **missing_resources** or the **resources_changed** flags
  of any reservation included in the lease is *True*, then it is *True*.

Lease owners can see health of the lease and reservations included in the
lease by checking these flags.

Monitoring Resources
====================

Resource specific functionality is provided as a monitoring plugin.
The following resource is currently supported.

.. toctree::
   :maxdepth: 1

   compute-host-monitor.rst


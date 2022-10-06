.. _Introduction:

============
Introduction
============

Blazar is the *Resource Reservation Service* for OpenStack.

The idea of creating Blazar originated with two different use cases:

* Compute host reservation (when user with admin privileges can reserve
  hardware resources that are dedicated to the sole use of a project)
* Virtual machine (instance) reservation (when user may ask Blazar
  to provide them working VM not necessarily now, but also in the future)

These ideas have been transformed to a more general view: with Blazar, user
can request the resources of cloud environment to be provided ("leased") to their
project for specific amount of time, immediately or in the future.

Currently, Blazar supports reservations of:

* Nova resources:

  * Compute hosts / hypervisors
  * Instances / servers

* Neutron resources:

  * Floating IPs

In terms of benefits added, Blazar:

* improves visibility of cloud resources consumption (current and planned for
  future);
* enables cloud resource planning based on current and future demand from end
  users;
* automates the processes of resource allocation and reclaiming.

Glossary of terms
-----------------

**Reservation** is an allocation of cloud resources to a particular project.
Main properties of a reservation are its status, resource type, identifier and
the lease it belongs to.

**Lease** is a negotiation agreement between the provider (Blazar, using OpenStack
resources) and the consumer (user) where the former agrees to make some kind of
cloud resources available to the latter, based on a set of lease terms presented
by the consumer. Technically speaking, lease is a group of reservations granted to
a particular project upon request. Main properties of a lease are its start time, end
time, set of reservations and set of events.

**Event** is something that may happen to a lease. In the simplest case, an event
might describe lease start and lease end. It might also be a notification to user
(e.g. about an upcoming lease expiration).

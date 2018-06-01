====================
Blazar architecture
====================

Blazar design can be described by following diagram:

.. image:: ../images/blazar-architecture.png
    :width: 700 px
    :scale: 99 %
    :align: left

**blazar-client** - provides the opportunity to communicate with Blazar via
*REST API* (blazar-api service).

**blazar-api** - waits for the REST calls from the outside world to redirect
them to the manager. blazar-api communicates with blazar-manager via RPC.
Runs as a separated process.

**blazar-manager** - implements all logic and operations with leases,
reservations and events. Communicates with Blazar DB and stores there data
structure of connected leases, reservations (both physical and virtual) and
events. blazar-manager service is responsible for running events created for
lease and process all actions that should be done this moment. Manager uses
resource-plugins to work with concrete resources (instances, volumes, compute
hosts).

**resource-plugin** - responsible for exact actions to do with reserved
resources (VMs, volumes, etc.) When working knows only about resource ID and
token to use. All resource plugins work in the same process as blazar-manager.

Virtual instance reservation
----------------------------

**Note** virtual instance reservation feature is not available in current
release. Expected to be available in the future (`bug tracker`_).

.. _bug tracker: https://blueprints.launchpad.net/blazar/+spec/new-instance-reservation

Virtual instance reservation mostly looks like usual instance booting for user
- he/she only passes special hints to Nova containing information about future
lease - lease start and end dates, its name, etc. Special Nova API extensions
parse these parameter and use them to call Blazar, passing to it ID of just
created instance. If there is a need to reserve all instances in cloud (like in
developer labs to automate process of resource reclaiming), default reservation
extension might be used. By default it starts lease at the moment of request
and gives it one month of lifetime.

During the time lease has not started yet, instance will be shelved.

Compute host reservation
------------------------

Now process of compute hosts reserving contains two steps:

* admin marks hosts from common pool as possible to be reserved. That is
  implemented by moving these hosts to special aggregate;
* user asks for reserving of host with specified characteristics like:

  * the region
  * the availability zone
  * the host capabilities extra specs (scoped and non-scoped format is
    accepted)
  * the number of CPU cores
  * the amount of free RAM
  * the amount of free disk space
  * the number of hosts

Technically speaking, resource ID here will be not host ID, because there might
be many of them wanted. Resource here will be new aggregate containing reserved
hosts. The time lease starts, user may use reserved compute capacity to run
his/her instances on it passing special scheduler hint to Nova. When host is
reserved, it's not used for usual instance running, it might be used only when
lease starts and only by passing reservation ID to Nova. That is implemented
using special Nova Scheduler filter, that passes reservation ID to Blazar and
checks if user really can use reserved compute capacity.

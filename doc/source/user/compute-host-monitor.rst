====================
Compute Host Monitor
====================

Compute host monitor detects failure and recovery of compute hosts.
If it detects failures, it triggers healing of host reservations and instance
reservations. This document describes the compute host monitor plugin in
detail.

Monitoring Type
===============

Both of the push-based and the polling-based monitoring types are supported
for the compute host monitor.
These monitors can be enabled/disabled by the following configuration options:

* **enable_notification_monitor**: Set *True* to enable it.
* **enable_polling_monitor**: Set *True* to enable it.

Failure Detection
=================

Compute host monitor detects failure and recovery hosts by subscribing Nova
notifications or polling the *List Hypervisors* of Nova API. If any failure is
detected, Blazar sets the *reservable* field of the failed host *False* and
heals suffering reservations as follows.

Reservation Healing
===================

If a host failure is detected, Blazar tries to heal host/instance reservations
which use the failed host by reserving alternative host.
The length of the *healing interval* can be configured by the
*healing_interval* option.

Configurations
==============

To enable the compute host monitor, enable *enable_notification_monitor*
or *enable_polling_monitor* option, and set *healing_interval* as
appropriate for your cloud.
See also the :doc:`../configuration/blazar-conf` in detail.

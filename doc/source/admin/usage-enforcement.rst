=================
Usage Enforcement
=================

Synopsis
========

Usage enforcement and lease constraints can be implemented by operators via
custom usage enforcement filters or an external service.

Description
===========

Usage enforcement filters are called on ``lease_create``, ``lease_update`` and
``on_end`` operations. The filters check whether or not lease values or
allocation criteria pass admin defined thresholds. There are currently two
filters provided out-of-the-box. ``MaxLeaseDurationFilter`` restricts the
duration of leases. ``ExternalServiceFilter`` calls a third-party service for
implementing policies using a URL configured in ``blazar.conf``.

Options
=======

All filters are a subclass of the BaseFilter class located in
``blazar/enforcement/filter/base_filter.py``. Custom filters must implement
methods for ``check_create``, ``check_update``, and ``on_end``. The
``MaxLeaseDurationFilter`` is a good example to follow. Filters are enabled in
``blazar.conf`` under the ``[enforcement]`` group. For example, enabling the
``MaxLeaseDurationFilter`` to limit lease durations to only one day would work
as follows:

.. sourcecode:: console

   [enforcement]
   enabled_filters = MaxLeaseDurationFilter
   max_lease_duration = 86400

..

MaxLeaseDurationFilter
----------------------

This filter simply examines the lease ``start_date`` and ``end_date``
attributes and rejects the lease if its duration exceeds a threshold. It
supports two configuration options:

* ``max_lease_duration``
* ``max_lease_duration_exempt_project_ids``

See the :doc:`../configuration/blazar-conf` page for a description of these
options.


ExternalServiceFilter
---------------------

This filter delegates the decision for each API to an external HTTP service.
The service must use token-based authentication and implement the following
endpoints for POST method:

* ``POST /v1/check-create``
* ``POST /v1/check-update``
* ``POST /v1/on-end``

The external service should return ``204 No Content`` if the parameters meet
defined criteria and ``403 Forbidden`` if not.

Example format of data the external service will receive in a request body:

* Request example:

.. sourcecode:: json

   {
     "context": {
       "user_id": "c631173e-dec0-4bb7-a0c3-f7711153c06c",
       "project_id": "a0b86a98-b0d3-43cb-948e-00689182efd4",
       "auth_url": "https://api.example.com:5000/v3",
       "region_name": "RegionOne"
     },
     "current_lease": {
       "start_date": "2020-05-13 00:00",
       "end_time": "2020-05-14 23:59",
       "reservations": [
         {
           "resource_type": "physical:host",
           "min": 1,
           "max": 2,
           "hypervisor_properties": "[]",
           "resource_properties": "[\"==\", \"$availability_zone\", \"az1\"]",
           "allocations": [
             {
               "id": "1",
               "hypervisor_hostname": "32af5a7a-e7a3-4883-a643-828e3f63bf54",
               "extra": {
                 "availability_zone": "az1"
               }
             }
           ]
         }
       ]
     },
     "lease": {
       "start_date": "2020-05-13 00:00",
       "end_time": "2020-05-14 23:59",
       "reservations": [
         {
           "resource_type": "physical:host",
           "min": 2,
           "max": 3,
           "hypervisor_properties": "[]",
           "resource_properties": "[\"==\", \"$availability_zone\", \"az1\"]",
           "allocations": [
             {
               "id": "1",
               "hypervisor_hostname": "32af5a7a-e7a3-4883-a643-828e3f63bf54",
               "extra": {
                 "availability_zone": "az1"
               }
             },
             {
               "id": "2",
               "hypervisor_hostname": "af69aabd-8386-4053-a6dd-1a983787bd7f",
               "extra": {
                 "availability_zone": "az1"
               }
             }
           ]
         }
       ]
     }
   }

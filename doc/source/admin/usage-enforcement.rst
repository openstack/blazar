=================
Usage Enforcement
=================

Synopsis
========

Usage enforcement and lease constraints can be implemented by operators via
custom usage enforcement filters.

Description
===========

Usage enforcement filters are called on ``lease_create``, ``lease_update`` and
``on_end`` operations. The filters check whether or not lease values or
allocation criteria pass admin defined thresholds. There is currently one
filter provided out-of-the-box. The ``MaxLeaseDurationFilter`` restricts the
duration of leases.

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

This filter simply examines the lease ``start_time`` and ``end_time``
attributes and rejects the lease if its duration exceeds a threshold. It
supports two configuration options:

* ``max_lease_duration``
* ``max_lease_duration_exempt_project_ids``

See the :doc:`../configuration/blazar-conf` page for a description of these
options.

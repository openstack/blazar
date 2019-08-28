Team and repository tags
========================

.. image:: https://governance.openstack.org/tc/badges/blazar.svg
    :target: https://governance.openstack.org/tc/reference/tags/index.html

.. Change things from this point on

Blazar
======

Blazar is a resource reservation service for OpenStack. Blazar enables users
to reserve a specific type/amount of resources for a specific time period and
it leases these resources to users based on their reservations.

The following two resource types are currently supported:

* Compute host: reserve and lease with a unit of a whole host

* Instance: reserve and lease with a unit of a flavor

Please see the following resources to learn more.

API
---

See `Blazar API reference <https://docs.openstack.org/blazar/latest/restapi/>`__.

Operators
---------

To learn how to deploy and configure Blazar,
see `the installation guide <https://docs.openstack.org/blazar/latest/install/>`__
and `the configuration reference <https://docs.openstack.org/blazar/latest/configuration/>`__.

Developers
----------

To learn how to contribute to Blazar, see `the contributor guide <https://docs.openstack.org/blazar/latest/contributor/>`__.

Other Resources
---------------

* Source code:

  * `Blazar <https://opendev.org/openstack/blazar>`__
  * `Nova scheduler filter <https://opendev.org/openstack/blazar-nova>`__
  * `Client tools <https://opendev.org/openstack/python-blazarclient>`__
  * `Dashboard (Horizon plugin) <https://opendev.org/openstack/blazar-dashboard>`__

* Blueprints/Bugs: https://launchpad.net/blazar
* Documentation: https://docs.openstack.org/blazar/latest/
* Release notes: https://docs.openstack.org/releasenotes/blazar/
* Design specifications: https://specs.openstack.org/openstack/blazar-specs/

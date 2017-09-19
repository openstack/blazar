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

See `Blazar API reference <http://blazar.readthedocs.io/en/latest/restapi/rest_api_v1.0.html>`__.

Operators
---------

To learn how to deploy and configure Blazar, see `the installation guide <http://blazar.readthedocs.io/en/latest/userdoc/installation.guide.html>`__.

Developers
----------

To learn how to contribute to Blazar, see `the contribution guide <http://blazar.readthedocs.io/en/latest/devref/how.to.contribute.html>`__.

Other Resources
---------------

* Source code:

  * `Blazar <https://git.openstack.org/cgit/openstack/blazar>`__
  * `Nova scheduler filter <https://git.openstack.org/cgit/openstack/blazar-nova>`__
  * `Client tools <https://git.openstack.org/cgit/openstack/python-blazarclient>`__
  * `Dashboard (Horizon plugin) <https://git.openstack.org/cgit/openstack/blazar-dashboard>`__

* Blueprints/Bugs: https://launchpad.net/blazar
* Documentation: https://blazar.readthedocs.io/en/latest/

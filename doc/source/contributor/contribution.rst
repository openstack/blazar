=================
How to contribute
=================

Getting started
---------------

* Read the `OpenStack Developer's Guide
  <https://docs.openstack.org/infra/manual/developers.html#developer-s-guide>`_
* Login to `OpenStack Gerrit <https://review.opendev.org/>`_ using your
  Launchpad ID

  * Sign the `OpenStack Individual Contributor License Agreement
    <https://review.opendev.org/#/settings/agreements>`_
  * Check that your email is listed in `Gerrit identities
    <https://review.opendev.org/#/settings/web-identities>`_

* Subscribe to Blazar-related projects on
  `OpenStack Gerrit <https://review.opendev.org/>`_. Go to your
  settings and in the watched projects add *openstack/blazar*,
  *openstack/blazar-nova*, *openstack/python-blazarclient* and
  *openstack/blazar-dashboard*.

As all bugs/blueprints are listed in `Blazar Launchpad
<https://launchpad.net/blazar/>`_, you may keep track on them and choose some
to work on.

How to keep in touch with community
-----------------------------------

* If you're not yet subscribed to the `OpenStack general mailing list
  <http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack>`_ or to the
  `OpenStack development mailing list
  <http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack-discuss>`_,
  please do. Blazar-related emails must be send with **[blazar]** in the
  subject.
* All questions may be asked on our IRC channel #openstack-blazar on
  `OFTC <http://oftc.net>`_.
* We also have weekly meetings on #openstack-meeting-alt. Please check
  `meeting details <https://wiki.openstack.org/wiki/Meetings/Blazar>`_.

Your first commit to Blazar
----------------------------

* Read the `OpenStack development workflow documentation
  <https://docs.openstack.org/infra/manual/developers.html#development-workflow>`_
* Clone the corresponding Blazar repository:
  `blazar <https://opendev.org/openstack/blazar>`_,
  `blazar-nova <https://opendev.org/openstack/blazar-nova>`_,
  `client <https://opendev.org/openstack/python-blazarclient>`_,
  `blazar-dashboard <https://opendev.org/openstack/blazar-dashboard>`_
* Apply and commit your changes
* Make sure all code checks and tests have passed
* Send your patch for review
* Monitor the status of your change on https://review.openstack.org/

How to contribute
=================

Getting started
---------------

* Create `Github <https://github.com/stackforge/blazar>`_ account if you don't
  have one
* Make sure you have git options *user.name* and *user.email* set in git by
  typing:

  .. sourcecode:: console

      git config --list. If not, configure them.

  ..

* Create `Launchpad <https://launchpad.net/blazar>`_ account if you don't have
  one
* Create `OpenStack profile <https://www.openstack.org/profile/>`_
* Login to `OpenStack Gerrit <https://review.openstack.org/>`_ using your
  Launchpad ID

  * Sign up your `OpenStack Individual Contributor License Agreement
    <https://review.openstack.org/#/settings/agreements>`_
  * Check that your email is listed in `Gerrit identities
    <https://review.openstack.org/#/settings/web-identities>`_

* Subscribe to Blazar-related projects on
  `OpenStack Gerrit <https://review.openstack.org/>`_. Go to your
  settings and in the watched projects add *stackforge/blazar*,
  *stackforge/blazar-nova* and *stackforge/python-blazarclient*

As all bugs/blueprints are listed in `Blazar Launchpad
<https://launchpad.net/blazar/>`_, you may keep track on them and choose some
to work on.

How to keep in touch with community
-----------------------------------

* If you're not subscribed to `OpenStack general mailing list
  <http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack>`_ or to
  `OpenStack development mailing list
  <http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack-dev>`_, do
  that. Blazar-related emails must be send with **[blazar]** in its subject.
* All questions may be asked on our IRC channel #openstack-blazar on
  `freenode <http://freenode.net>`_
* We also have weekly meetings on #openstack-meeting
  `freenode IRC channel <https://wiki.openstack.org/wiki/Meetings/Blazar>`_

Your first commit to Blazar
----------------------------

* Checkout corresponding Blazar repository from `Github
  <https://github.com/stackforge/blazar>`_
* Take a look on how `Gerrit review process
  <https://wiki.openstack.org/wiki/Gerrit_Workflow>`_ goes on in OpenStack
  (read carefully `committing changes
  <https://wiki.openstack.org/wiki/Gerrit_Workflow#Committing_Changes>`_ part)
* Apply and commit your changes
* Make sure all code checkings and tests have passed. See
  `development guidelines <development.guidelines.html>`_ to learn more
* Send your patch to the review (you may use `git-review
  <https://github.com/openstack-infra/git-review>`_ utility for that)
* Monitor status of your change on https://review.openstack.org/#/

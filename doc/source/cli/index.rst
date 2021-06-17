================================
Command-Line Interface Reference
================================

.. toctree::

   host-reservation
   instance-reservation
   floatingip-reservation

Two command-line interfaces exist: one as a standalone ``blazar`` client and
another integrated with the ``openstack`` client. Examples are given for both
where applicable, as shown below:

.. sourcecode:: console

 # Using the blazar CLI
 blazar lease-list

 # Using the openstack CLI
 openstack reservation lease list
..

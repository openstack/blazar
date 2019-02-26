..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

=======================
Floating IP Reservation
=======================

https://blueprints.launchpad.net/blazar/+spec/floatingip-reservation

This network plugin supports floating IP reservation.

Problem description
===================

The Neutron service creates and associates floating IPs to projects in a first
come first serve style. The order sometimes causes lack of floating IPs in a
cloud, especially in a private cloud, since the cloud provider has a limited
number of floating IPs available for their cloud.

Use Cases
---------

* A user plans to scale up a service during a specific time window and the
  service requires a new floating IP for global access.
* A user plans to start a new service and wants to make sure a floating IP is
  available at the start time.
* A cloud admin does not have enough floating IPs to give to all users

  * The admin wants to give a user a floating IP with either the host or
    instance reservation.

Proposed change
===============

Blazar enables users to reserve floating IPs by specifying the external network
ID of floating IPs the users want to reserve. Users can treat the reserved
floating IP as usual, except for the create floating IP operation.

A basic idea for the floating IP reservation and its scenario are as follows:

1. The admin registers some floating IPs used for floating IP reservation with
   Blazar. The admin calls Blazar's floating IP API with a request body which
   includes public network ID and its floating IP address. The floating IP
   address must be out of allocation_pools in the external network subnets.
2. A user calls the create lease API with external network ID, start date, and
   end date. Blazar checks availability of a floating IP for the request.
   If a floating IP is available, Blazar creates an allocation between the
   floating IP and the reservation, then returns the reservation ID. If not,
   Blazar doesn't return a reservation ID.
3. At the start time, Blazar creates the reserved floating IP in the user's
   tenant (project). Then the user can attach, detach, and delete the floating
   IP as usual.
5. At the end time, Blazar removes the reserved floating IP from the user's
   tenant, if the user hasn't deleted the floating IP already.

Blazar regards IP addresses out of Neutron's allocation_pools parameter as
reservable resources. The allocation_pools is just a range of IP addresses from
which Neutron automatically creates floating IPs. When an admin creates a
floating IP with a specific IP address which is out of the range, Neutron
accepts the request and the new floating IP has the requested IP address. It
enables Blazar to manage creation of the reserved floating IPs by itself.

Blazar adds two tags, "blazar" and "reservation:<reservation-id>" to the
reserved floating IP to make it easy for users to query their reserved floating
IPs.

To realize the scenario, this blueprint introduces a new resource plugin, named
"virtual:floatingip" for Blazar.

Alternatives
------------

Dedicated External Network approach
```````````````````````````````````

Blazar maps the reserved floating IPs to a dedicated external network. The
external network is hidden from the regular users by neutron's policy.json.
Blazar creates the reserving user's external network at lease start time and
deletes the network at lease end time on behalf of the user.

The advantage of this approach is the reserved resource is separated from
user's non-reserved resources. It's easy for Blazar to handle the reserved
resources at start date and end date.

The disadvantage is that this approach needs the same amount of physical
networks/configuration as the number of reserved networks.
For example, if a cloud admin sets up their external network as type_driver is
flat and mechanical_driver is ovs, Neutron needs as many OVS bridges as the
number of reserved external networks.

Associated Port approach
````````````````````````

Blazar attaches the reserved floating IPs to a specific port while the floating
IP reservation is active. When the reservable floating IP is not in use, the IP
belongs to Blazar's service tenant. It prevents users from creating floating
IPs using the reservable IPs.

The advantage is that Blazar can handle the creation and deletion of floating
IP and the reservable floating IPs belongs to the range of the allocation_pools
parameter.

The drawback is that users need to use a new workflow to manage the reserved
floating IP. Without Blazar, users can associate and de-associate a floating IP
to/from a port. But Blazar does in this approach instead of users. It requires
users to have two workflows for managing floating IPs.

Data model impact
-----------------

This plugin introduces four new tables, "floatingip_reservations",
"required_floatingips", "floatingip_allocations" and "floatingips".

The "floatingip_reservations" table keeps user request information for their
floating IP reservations. The role of this table is similar to the role of the
computehost_reservations table in the host reservation plugin. This table has
id, network_id and amount columns. The table has a relationship with the set of
floating IPs requested by user.

The "required_floatingips" table represents floating IPs that a user requests
for a reservation.

The "floatingip_allocations" table has the relationship between the
floatingip_reservations table and the floatingips table.

The "floatingips" table stores information of floating IPs themselves.
The reservable floating IPs are registered in the table.
The floating_ip_address column has unique constraints because the id column
is generated by Blazar. Neutron generates floating ip's id during floating ip
creation.

The table definitions are as follows:

.. sourcecode:: none

   CREATE TABLE floatingip_reservations (
       id VARCHAR(36) NOT NULL,
       reservation_id VARCHAR(255) NOT NULL,
       network_id VARCHAR(255) NOT NULL,
       amount INT UNSIGNED NOT NULL,

       PRIMARY key (id),
       INDEX (id, reservation_id)
       FOREIGN KEY (reservation_id)
         REFERENCES reservations(id)
         ON DELETE CASCADE,
   );

   CREATE TABLE required_floatingips (
       id VARCHAR(36) NOT NULL,
       floatingip_reservation_id VARCHAR(36) NOT NULL,
       address VARCHAR(255) NOT NULL,

       PRIMARY key (id),
       FOREIGN KEY (floatingip_reservation_id)
         REFERENCES floatingip_reservations(id)
         ON DELETE CASCADE,
   );

   CREATE TABLE floatingip_allocations (
       id VARCHAR(36) NOT NULL,
       reservation_id VARCHAR(255) NOT NULL,
       floatingip_id VARCHAR(255) NOT NULL,
   );

   CREATE TABLE floatingips (
       id VARCHAR(36) NOT NULL,
       floating_network_id VARCHAR(255) NOT NULL,
       subnet_id VARCHAR(255) NOT NULL,
       floating_ip_address VARCHAR(255) NOT NULL,
       reservable BOOLEAN NOT NULL,

       UNIQUE (subnet_id, floating_ip_address)
   );

REST API impact
---------------

The floating IP reservation introduces a new resource_type to the lease APIs
and four new admin APIs to manages floating IPs.

Changes in the lease APIs
`````````````````````````

* URL: POST /v1/leases

  * Introduced new resource_type, virtual:floatingip, for a reservation.
  * The network_id is an external network ID from which the user wants to
    reserve a floating ip.
  * The required_floatingips is an optional key. The key represents a list of
    floating IPs which must be included in the reservation. In the request
    sample, an user wants 3 floating IPs, and wants to spcifiy 2 of 3
    floating IPs and doesn't care of 1 of 3 floating IP.

Request Example:

.. sourcecode:: json

   {
     "name": "floatingip-reservation-1",
     "reservations": [
       {
         "resource_type": "virtual:floatingip",
         "network_id": "external-network-id",
         "required_floatingips": [
           "172.24.4.10",
           "172.24.4.11"
         ],
         "amount": 3
       }
      ],
     "start_date": "2017-05-17 09:07",
     "end_date": "2017-05-17 09:10",
     "events": []
   }

Response Example:

.. sourcecode:: json

   {
     "lease": {
       "name": "floatingip-reservation-1",
       "reservations": [
         {
           "id": "reservation-id",
           "status": "pending",
           "lease_id": "lease-id-1",
           "resource_id": "resource_id",
           "resource_type": "virtual:floatingip",
           "network_id": "external-network-id",
           "required_floatingips": [
             "172.24.4.10",
             "172.24.4.11"
           ],
           "allocated_floatingips": [
             "172.24.4.10",
             "172.24.4.11",
             "172.24.4.100"
           ],
           "amount": 3,
           "created_at": "2017-05-01 10:00:00",
           "updated_at": "2017-05-01 11:00:00",
         }],
       "start_date": "2017-05-17 09:07",
       "end_date": "2017-05-17 09:07",
       ..snip..
     }
   }


* URL: GET /v1/leases
* URL: GET /v1/leases/{lease-id}
* URL: PUT /v1/leases/{lease-id}
* URL: DELETE /v1/leases/{lease-id}

  * The change is the same as POST /v1/leases

New floating IP APIs
````````````````````

The four new APIs are admin APIs by default.

* URL: POST /v1/floatingips

  * The floating_network_id is an external network ID the admin adds as
    Blazar's resource.
  * The floating_ip_address is a specific floating IP address the admin wants
    to add. The IP address must be the out of allocation_pools. When admin
    calls the API, Blazar fetches the subnet info from Neutron and verifies
    the floating IP is out of allocation_pools and within its CIDR network.
  * The floating_ip_address can't be an optional parameter since IPs outside of
    the allocation_pool is commonly used by network equipment, a router,
    a loadbalancer and etc.

Request Example:

.. sourcecode:: json

   {
     "floating_network_id": "external-network-id",
     "floating_ip_address": "floating_ip_address"
   }

* The reservable key is a flag describing if the floating IP is reservable or
  not. The flag is always True until the floating IP plugin supports the
  resource healing feature. (Supporting resource healing to floating IP is out
  of scope in this spec)


Response Example:

.. sourcecode:: json

   {
     "floatingip": {
         "id": "floating-ip-id",
         "floating_network_id": "external-network-id",
         "floating_ip_address": "floating_ip_address",
         "subnet_id": "subnet-id",
         "reservable": true,
         "created_at": "2020-01-01 10:00:00",
         "updated_at": null
     }
   }

* URL: GET /v1/floatingips

Response Example:

.. sourcecode:: json

   {
     "floatingips": [
         {
           "id": "floating-ip-id",
           "floating_network_id": "external-network-id",
           "floating_ip_address": "floating_ip_address",
           "subnet_id": "subnet-id",
           "reservable": true,
           "created_at": "2020-01-01 10:00:00",
           "updated_at": null
         }
     ]
   }


* URL: GET /v1/floatingips/{floatingip-id}

Response Example:

.. sourcecode:: json

   {
     "floatingip": {
         "id": "floating-ip-id",
         "floating_network_id": "external-network-id",
         "floating_ip_address": "floating_ip_address",
         "subnet_id": "subnet-id",
         "reservable": true,
         "created_at": "2020-01-01 10:00:00",
         "updated_at": null
     }
   }

* URL: DELETE /v1/floatingips/{floatingip-id}

No Request body and Response body.

The floating IP API doesn't have an update API because all of the information
is retrieved from Neutron API.

Security impact
---------------

None

Notifications impact
--------------------

None

Other end user impact
---------------------

An user can reserve floating IPs as well as host or instance reservation in one
lease.

python-blazarclient will support the floating IP reservation.

Performance Impact
------------------

None

Other deployer impact
---------------------

None

Developer impact
----------------

This is a first implementation for networking resources.

Upgrade impact
--------------

Some configurations for Neutron util class will be introduced to blazar.conf.
If the cloud admin want to activate the network reservation, they needs to
setup the configuration.

Implementation
==============

Assignee(s)
-----------

Primary assignee:
  muroi-masahito

Other contributors:
  None

Work Items
----------

* Create Neutron API utility class
* Create the new DB tables
* Create the floating IP reservation plugin
* Create the floating IP API object and its route in blazar.api.v1
* Add floating IP reservation supports in python-blazarclient
* Add scenario tests and API tests in blazar-tempest-plugin
* Update Blazar docs, API reference and user guide

Dependencies
============

None

Testing
=======

API tests and scenario tests need to be implemented.

Documentation Impact
====================

This BP adds new APIs and resource type to the lease APIs. The API reference
and the Blazar documentation need to be updated.

References
==========

1. Draft for floating IP reservation: https://etherpad.openstack.org/p/network-resource-reservation
2. Denver PTG discussion: https://etherpad.openstack.org/p/blazar-ptg-stein

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Stein
     - Introduced

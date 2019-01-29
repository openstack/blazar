..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

=========================
Resource Allocation API
=========================

https://blueprints.launchpad.net/blazar/+spec/resource-availability-api

Introducing new APIs for querying current usage of each resource.

Problem description
===================

A Blazar reservation consumes at least one reservable resource.
For host reservation and instance reservation, a reservation is tied
to specific hosts and the relationship is stored in the Blazar DB.

Blazar has no API describing the consumption relationship. Blazar has list
APIs for leases and hosts, which show cloud users and cloud admins either
list of leases or reservable hosts. However, the scope of both APIs is only
individual resource information.

Cloud admins have no way to find the relationship through the Blazar API.
If they would like to know the usage of hosts for a specific time window, they
need to query the Blazar DB directly. Direct DB querying by users is not
supported in general.

Use Cases
---------

* A cloud admin want to find the upcoming usage of a specific host for
  maintenance.

Proposed change
===============

Introducing a new API set, get and list reservation allocation API, to host
APIs. This APIs show list of reservations which consumes reservable hosts.
If cloud admins call this API, they can find all reservations consuming
specific hosts.

.. note:: The spec and the blueprint are named resource **availability** API.
          However, the proposed API change responds existing reservation's
          allocations. The name of the API set are changed from availability
          to reservation allocation API.

The API set are part of Hosts API. The default authorization policy
is admin API.

See the REST API impact section for the details of the API.

Alternatives
------------

Appending a new key-value pair to the lease get API and the lease list API.
The pair could form like ``"hosts": [{"id": 1}, {"id": 2}]``, and be added to
each reservation details.

The good point of this change is not introducing a new API.  Introducing a new
API always has an impact for pythonclient, too.

The drawback is the authentification and the authorization for the API call
become more complex. The response body changes depending on the keystone token.
If a token scopes admin role, the API needs to create its response with host
information. If not, the API doesn't have to add the information.

Data model impact
-----------------

None.

REST API impact
---------------

* URL: GET /v1/os-hosts/allocations

  * The API replies the all allocations between reservations and hosts.
  * Nomal response code: 200
  * Error response code: Bad Request(400), Unauthorized(401), Forbidden(403),
    Internal Server Error(500)

Response Example:

  .. sourcecode:: json

     {
       "allocations": [
           {
                "resource_id": "host-id1",
                "reservations": [
                  {
                    "id": "reservation-id1",
                    "lease_id": "lease-id1"
                  },
                  {
                    "id": "reservation-id2",
                    "lease_id": "lease-id1"
                  }
                ]
           },
           ..snippet..
       ]
     }


* URL: GET /v1/os-hosts/{host-id}/allocation

  * The API replies the all allocations only for the host.
  * Nomal response code: 200
  * Error response code: Bad Request(400), Unauthorized(401), Forbidden(403),
    Not Found(404), Internal Server Error(500)

Response Example:

  .. sourcecode:: json

     {
       "allocation": {
           "resource_id": "host-id1",
           "reservations": [
             {
               "id": "reservation-id1",
               "lease_id": "lease-id1"
             },
             {
               "id": "reservation-id2",
               "lease_id": "lease-id1"
             }
           ]
        }
      }


Both APIs support some query parameters.

* lease_id: A parameter that filters allocations belonging to the lease_id
* reservation_id: A parameter that filters allocations belonging to the reservation_id
* terminated: A flag that filters allocations already terminated or not

Security impact
---------------

None

Notifications impact
--------------------

None

Other end user impact
---------------------

The pythonclient will support the allocation APIs.

Performance Impact
------------------

List all allocations API, GET /v1/os-hosts/allocations, returns all
allocations. When the number of hosts and reservations are huge, the
DB query and response body could become huge, too.

To try reducing the number of DB query, the two API use queries
like followings.

  .. sourcecode:: none

     # List reservation allocations API
     SELECT computehost_allocations.host, reservation.id, reservations.lease_id
       FROM computehost_allocations
         JOIN reservations ON computehost_allocations.reservation_id = reservations.id;

    # Get reservation allocations API
     SELECT computehost_allocations.host, reservation.id, reservations.lease_id
       FROM computehost_allocations
         JOIN reservations ON computehost_allocations.reservation_id = reservations.id
       WHERE computehost_allocations.host = host_id;

Other deployer impact
---------------------

None

Developer impact
----------------

None

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

* Support query parameters for GET request
* Implement the reservation allocation API in host plugin
* Support the reservation allocation API in blazarclient

Dependencies
============

None

Testing
=======

* Unit tests
* Tempest scenario tests

Documentation Impact
====================

* API reference

References
==========

.. [DublinPTG] Discussion at the Dublin PTG <https://etherpad.openstack.org/p/blazar-ptg-rocky>

History
=======

.. list-table:: Revisions
   :header-rows: 1

   * - Release Name
     - Description
   * - Rocky
     - Introduced

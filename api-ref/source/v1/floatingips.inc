.. -*- rst -*-

============
Floating IPs
============

List FloatingIPs
================

.. rest_method:: GET v1/floatingips

List floating IPs.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Internal Server Error(500)

Request
-------

No body content, path, nor query option.

Response
--------

.. rest_parameters:: parameters.yaml

  - floatingips: floatingips
  - id: floatingip_id
  - floating_network_id: floating_network_id
  - subnet_id: floating_subnet_id
  - floating_ip_address: floating_ip_address
  - reservable: floatingip_reservable
  - created_at: created_at
  - updated_at: updated_at

**Example of List Hosts Response**

.. literalinclude:: ../../../doc/api_samples/floatingips/floatingip-list-resp.json
  :language: javascript

Create Floating IP
==================

.. rest_method:: POST v1/floatingips

Create a floating IP.

**Response codes**

Normal response code: 201

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Conflict(409), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - floating_network_id: floating_network_id
  - floating_ip_address: floating_ip_address_create

**Example of Create Host Request**

.. literalinclude:: ../../../doc/api_samples/floatingips/floatingip-create-req.json
  :language: javascript

Response
--------

.. rest_parameters:: parameters.yaml

  - floatingip: floatingip
  - id: floatingip_id
  - floating_ip_address: floating_ip_address
  - network_id: floating_network_id
  - subnet_id: floating_subnet_id
  - reservable: floatingip_reservable
  - created_at: created_at
  - updated_at: updated_at

**Example of Create Host Response**

.. literalinclude:: ../../../doc/api_samples/floatingips/floatingip-create-resp.json
  :language: javascript

Show Floating IP Details
========================

.. rest_method:: GET v1/floatingips/{floatingip_id}

Show details of a floating IP.

**Preconditions**

The floating IP must exist.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Not Found(404), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - floatingip_id: floatingip_id_path

Response
--------

.. rest_parameters:: parameters.yaml

  - floatingip: floatingip
  - id: floatingip_id
  - floating_network_id: floating_network_id
  - floating_ip_address: floating_ip_address
  - reservable: floatingip_reservable
  - created_at: created_at
  - updated_at: updated_at

**Example of Show Floating IP Details Response**

.. literalinclude:: ../../../doc/api_samples/floatingips/floatingip-details-resp.json
  :language: javascript

Delete Floating IP
==================

.. rest_method:: DELETE v1/floatingips/{floatingip_id}

Delete a floating IP.

**Preconditions**

The floating IP must exist.

**Response codes**

Normal response code: 204

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Not Found(404), Conflict(409), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - floatingip_id: floatingip_id_path

Repsponse
---------

No body content is returned on a successful DELETE.

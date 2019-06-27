.. -*- rst -*-

==================
Global Request ID
==================

Users can specify a global request ID as a request header.

**Request**

.. rest_parameters:: parameters.yaml

  - X-Openstack-Request-Id: x-openstack-request-id_req

**Request Header**

In each REST API request, you can specify a global request ID
in the ``X-Openstack-Request-Id`` header.
The format must be ``req-`` + UUID (UUID4).
If not in accordance with the format, the global request ID is
ignored by Blazar.

Request header example::

  X-Openstack-Request-Id: req-e19f8f4f-40e7-441e-b776-7b43ed15c7dd

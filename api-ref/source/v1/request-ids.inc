.. -*- rst -*-

===========
Request ID
===========

For each REST API request, a local request ID is returned as a header in the response.

**Response**

.. rest_parameters:: parameters.yaml

  - X-Openstack-Request-Id: x-openstack-request-id_resp

**Response Header**

For each REST API request, the response contains a ``X-Openstack-Request-Id`` header.

The value of the ``X-Openstack-Request-Id`` header is the local request ID assigned to the request.

Response header example::

  X-Openstack-Request-Id: req-d7bc29d0-7b99-4aeb-a356-89975043ab5e

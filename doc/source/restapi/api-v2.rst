===============================
Blazar REST API v2 (deprecated)
===============================

**NOTE**: This version is deprecated. Please use the Blazar REST API v1.

1 General API information
-------------------------

This section contains base information about the Blazar REST API design,
including operations with different Blazar resource types and examples of
possible requests and responses. Blazar supports JSON data serialization
format, which means that requests with non empty body have to contain
"application/json" Content-Type header or it should be added ".json" extension
to the resource name in the request.

This should look like the following:

.. sourcecode:: http

    GET /v2/leases.json

or

.. sourcecode:: http

    GET /v2/leases
    Accept: application/json


2 Leases
--------

**Description**

Lease is the main abstraction for the user in the Blazar case. Lease means
some kind of contract where start time, end time and resources to be reserved
are mentioned.

.. rest-controller:: blazar.api.v2.controllers.extensions.lease:LeasesController
   :webprefix: /v2/leases

.. autotype:: blazar.api.v2.controllers.extensions.lease.Lease
   :members:


3 Hosts
-------

**Description**

Host is the abstraction for a computehost in the Blazar case. Host means
a specific type of resource to be allocated.

.. rest-controller:: blazar.api.v2.controllers.extensions.host:HostsController
   :webprefix: /v2/os-hosts

.. autotype:: blazar.api.v2.controllers.extensions.host.Host
   :members:

Climate REST API v2
*********************


1 General API information
=========================

This section contains base information about the Climate REST API design,
including operations with different Climate resource types and examples of
possible requests and responses. Climate supports JSON data serialization
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
=======

**Description**

Lease is the main abstraction for the user in the Climate case. Lease means
some kind of contract where start time, end time and resources to be reserved
are mentioned.

.. rest-controller:: climate.api.v2.controllers.lease:LeasesController
   :webprefix: /v2/leases

.. autotype:: climate.api.v2.controllers.lease.Lease
   :members:


3 Hosts
=======

**Description**

Host is the abstraction for a computehost in the Climate case. Host means
a specific type of resource to be allocated.

.. rest-controller:: climate.api.v2.controllers.host:HostsController
   :webprefix: /v2/os-hosts

.. autotype:: climate.api.v2.controllers.host.Host
   :members:

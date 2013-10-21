Climate REST API v1.0
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

    GET /v1/{tenant_id}/leases.json

or

.. sourcecode:: http

    GET /v1/{tenant_id}/leases
    Accept: application/json


2 Leases
========

**Description**

Lease is the main abstraction for the user in the Climate case. Lease means
some kind of contract where start time, end time and resources to be reserved
are mentioned.

**Lease ops**

+-----------------+--------------------------------------------+-------------------------------------------------------------------------------+
| Verb            | URI                                        | Description                                                                   |
+=================+============================================+===============================================================================+
| GET             | /v1/{tenant_id}/leases                     | Lists all leases registered in Climate.                                       |
+-----------------+--------------------------------------------+-------------------------------------------------------------------------------+
| POST            | /v1/{tenant_id}/leases                     | Create new lease with passed parameters.                                      |
+-----------------+--------------------------------------------+-------------------------------------------------------------------------------+
| GET             | /v1/{tenant_id}/leases/{lease_id}          | Shows information about specified lease.                                      |
+-----------------+--------------------------------------------+-------------------------------------------------------------------------------+
| PUT             | /v1/{tenant_id}/leases/{lease_id}          | Updates specified lease (only name modification and prolonging are possible). |
+-----------------+--------------------------------------------+-------------------------------------------------------------------------------+
| DELETE          | /v1/{tenant_id}/leases/{lease_id}          | Deletes specified lease and frees all reserved resources.                     |
+-----------------+--------------------------------------------+-------------------------------------------------------------------------------+

2.1 List all leases
-------------------

.. http:get:: /v1/{tenant_id}/leases

* Normal Response Code: 200 (OK)
* Returns the list of all leases.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET http://climate/v1/123456/leases

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        {
            "leases": [
                {
                    "id": "aaaa-bbbb-cccc-dddd",
                    "name": "lease_foo_1",
                    "start_date": "1234",
                    "end_date": "2345",
                    "reservations": [
                        {
                            "id": "fake_id_1",
                            "lease_id": "aaaa-bbbb-cccc-dddd",
                            "resource_id": "1234-1234-1234",
                            "resource_type": "virtual:instance",
                            "status": "Reserved"
                        }
                    ]
                },
                {
                    "id": "eeee-ffff-gggg-hhhh",
                    "name": "lease_foo_2",
                    "start_date": "1234",
                    "end_date": "2345",
                    "reservations": [
                        {
                            "id": "fake_id_2",
                            "lease_id": "eeee-ffff-gggg-hhhh",
                            "resource_id": "2345-2345-2345",
                            "resource_type": "physical:host",
                            "status": "Reserved"
                        }
                    ]
                }
            ]
        }

2.2 Create new lease
--------------------

.. http:post:: /v1/{tenant_id}/leases

* Normal Response Code: 202 (ACCEPTED)
* Returns the information about created lease.
* Requires a request body.

**Example**
    **request**

    .. sourcecode:: http

        POST http://climate/v1/123456/leases

    .. sourcecode:: json

        {
            "name": "lease_foo",
            "start_date": "1234",
            "end_date": "2345",
            "reservations": [
                {
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "Reserved"
                }
            ]
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "id": "aaaa-bbbb-cccc-dddd",
            "name": "lease_foo",
            "start_date": "1234",
            "end_date": "2345",
            "reservations": [
                {
                    "id": "fake_resource_id",
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "Reserved"
                }
            ],
            "events": [
                {
                    "id": "fake_event_id",
                    "event_type": "notification",
                    "event_date": "3456",
                    "message": "Lease $(lease_id) will be expired in 15 min."
                }
            ]
        }

2.3 Show info about lease
-------------------------

.. http:get:: /v1/{tenant_id}/leases/{lease_id}

* Normal Response Code: 200 (OK)
* Returns the information about specified lease.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET http://climate/v1/123456/leases/aaaa-bbbb-cccc-dddd

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        {
            "id": "aaaa-bbbb-cccc-dddd",
            "name": "lease_foo_1",
            "start_date": "1234",
            "end_date": "2345",
            "reservations": [
                {
                    "id": "fake_resource_id_1",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "Reserved"
                }
            ],
            "events": [
                {
                    "id": "fake_event_id",
                    "event_type": "notification",
                    "event_date": "3456",
                    "message": "Lease $(lease_id) will be expired in 15 min."
                }
            ]
        }

2.4 Update existing lease
-------------------------

.. http:put:: /v1/{tenant_id}/leases/{lease_id}

* Normal Response Code: 202 ACCEPTED
* Returns the updated information about lease.
* Requires a request body.

**Example**
    **request**

    .. sourcecode:: http

        PUT http://climate/v1/123456/leases/aaaa-bbbb-cccc-dddd

    .. sourcecode:: json

        {
            "name": "new_name",
            "end_date": "new_date",
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "id": "aaaa-bbbb-cccc-dddd",
            "name": "new_name",
            "start_date": "1234",
            "end_date": "new_date",
            "reservations": [
                {
                    "id": "fake_resource_id",
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "Reserved"
                }
            ],
            "events": [
                {
                    "id": "fake_event_id",
                    "event_type": "notification",
                    "event_date": "3456",
                    "message": "Lease $(lease_id) will be expired in 15 min."
                }
            ]
        }

2.5 Delete existing lease
-------------------------

.. http:delete:: /v1/{tenant_id}/leases/{lease_id}

* Normal Response Code: 204 NO CONTENT
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        DELETE http://climate/v1/123456/leases/aaaa-bbbb-cccc-dddd

    **response**

    .. sourcecode:: http

        HTTP/1.1 204 ACCEPTED
        Content-Type: application/json


3 Plugins
=========

+-----------------+--------------------------------------+-------------------------------------------------------------------------------+
| Verb            | URI                                  | Description                                                                   |
+=================+======================================+===============================================================================+
| GET             | /v1/{tenant_id}/plugins            | Lists all plugins registered in Climate.                                      |
+-----------------+--------------------------------------+-------------------------------------------------------------------------------+

3.1 List plugins
----------------

.. http:get:: /v1/{tenant_id}/plugins

* Normal Response Code: 200 (OK)
* Returns the list of all plugins.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET http://climate/v1/123456/plugins

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        {
            "plugins": [
                {
                    "id": "aaaa-bbbb-cccc-dddd",
                    "name": "plugin_name_1",
                    "resource_type": "virtual:instance",
                    "description": "Starts VM when lease begins and deletes it when lease ends."
                },
                {
                    "id": "eeee-ffff-gggg-hhhh",
                    "name": "plugin_name_2",
                    "resource_type": "virtual:volume",
                    "description": "Creates volume when lease begins and deletes it when lease ends."
                },

            ]
        }
Blazar REST API v1.0
*********************


1 General API information
=========================

This section contains base information about the Blazar REST API design,
including operations with different Blazar resource types and examples of
possible requests and responses. Blazar supports JSON data serialization
format, which means that requests with non empty body have to contain
"application/json" Content-Type header or it should be added ".json" extension
to the resource name in the request.

This should look like the following:

.. sourcecode:: http

    GET /v1/leases.json HTTP/1.1

or

.. sourcecode:: http

    GET /v1/leases HTTP/1.1
    Accept: application/json


2 Leases
========

**Description**

Lease is the main abstraction for the user in the Blazar case. Lease means
some kind of contract where start time, end time and resources to be reserved
are mentioned.

**Lease ops**

+--------+-----------------------+-------------------------------------------------------------------------------+
| Verb   | URI                   | Description                                                                   |
+========+=======================+===============================================================================+
| GET    | /v1/leases            | Lists all leases registered in Blazar.                                       |
+--------+-----------------------+-------------------------------------------------------------------------------+
| POST   | /v1/leases            | Create new lease with passed parameters.                                      |
+--------+-----------------------+-------------------------------------------------------------------------------+
| GET    | /v1/leases/{lease_id} | Shows information about specified lease.                                      |
+--------+-----------------------+-------------------------------------------------------------------------------+
| PUT    | /v1/leases/{lease_id} | Updates specified lease (only name modification and prolonging are possible). |
+--------+-----------------------+-------------------------------------------------------------------------------+
| DELETE | /v1/leases/{lease_id} | Deletes specified lease and frees all reserved resources.                     |
+--------+-----------------------+-------------------------------------------------------------------------------+

2.1 List all leases
-------------------

.. http:get:: /v1/leases

* Normal Response Code: 200 (OK)
* Returns the list of all leases.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET /v1/leases HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        [
            {
                "created_at": "2014-02-26 10:00:00",
                "end_date": "2345",
                "events": [
                    {
                        "created_at": "2014-02-26 10:00:00",
                        "event_type": "start_lease",
                        "id": "event_id_1",
                        "lease_id": "aaaa-bbbb-cccc-dddd",
                        "status": "UNDONE",
                        "time": "1234",
                        "updated_at": null
                    },
                    {
                        "created_at": "2014-02-26 10:25:52",
                        "event_type": "end_lease",
                        "id": "event_id_2",
                        "lease_id": "aaaa-bbbb-cccc-dddd",
                        "status": "UNDONE",
                        "time": "2345",
                        "updated_at": null
                    }
                ],
                "id": "aaaa-bbbb-cccc-dddd",
                "name": "lease_foo",
                "reservations": [
                    {
                        "created_at": "2014-02-26 10:00:00",
                        "id": "reservation_id",
                        "lease_id": "aaaa-bbbb-cccc-dddd",
                        "resource_id": "1234-1234-1234",
                        "resource_type": "virtual:instance",
                        "status": "pending",
                        "updated_at": null
                    }
                ],
                "start_date": "1234",
                "project_id": "project_id",
                "trust_id": "trust_id",
                "updated_at": null,
                "user_id": "user_id"
            }
        ]

2.2 Create new lease
--------------------

.. http:post:: /v1/leases

* Normal Response Code: 202 (ACCEPTED)
* Returns the information about created lease.
* Requires a request body.

**Example**
    **request**

    .. sourcecode:: http

        POST /v1/leases HTTP/1.1

    .. sourcecode:: json

        {
            "name": "lease_foo",
            "start_date": "1234",
            "end_date": "2345",
            "reservations": [
                {
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance"
                }
            ],
            "events": []
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "created_at": "2014-02-26 10:00:00",
            "end_date": "2345",
            "events": [
                {
                    "created_at": "2014-02-26 10:00:00",
                    "event_type": "start_lease",
                    "id": "event_id_1",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "status": "UNDONE",
                    "time": "1234",
                    "updated_at": null
                },
                {
                    "created_at": "2014-02-26 10:25:52",
                    "event_type": "end_lease",
                    "id": "event_id_2",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "status": "UNDONE",
                    "time": "2345",
                    "updated_at": null
                }
            ],
            "id": "aaaa-bbbb-cccc-dddd",
            "name": "lease_foo",
            "reservations": [
                {
                    "created_at": "2014-02-26 10:00:00",
                    "id": "reservation_id",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "pending",
                    "updated_at": null
                }
            ],
            "start_date": "1234",
            "project_id": "project_id",
            "trust_id": "trust_id",
            "updated_at": null,
            "user_id": "user_id"
        }

2.3 Show info about lease
-------------------------

.. http:get:: /v1/leases/{lease_id}

* Normal Response Code: 200 (OK)
* Returns the information about specified lease.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET /v1/leases/aaaa-bbbb-cccc-dddd  HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        {
            "created_at": "2014-02-26 10:00:00",
            "end_date": "2345",
            "events": [
                {
                    "created_at": "2014-02-26 10:00:00",
                    "event_type": "start_lease",
                    "id": "event_id_1",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "status": "UNDONE",
                    "time": "1234",
                    "updated_at": null
                },
                {
                    "created_at": "2014-02-26 10:25:52",
                    "event_type": "end_lease",
                    "id": "event_id_2",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "status": "UNDONE",
                    "time": "2345",
                    "updated_at": null
                }
            ],
            "id": "aaaa-bbbb-cccc-dddd",
            "name": "lease_foo",
            "reservations": [
                {
                    "created_at": "2014-02-26 10:00:00",
                    "id": "reservation_id",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "pending",
                    "updated_at": null
                }
            ],
            "start_date": "1234",
            "project_id": "project_id",
            "trust_id": "trust_id",
            "updated_at": null,
            "user_id": "user_id"
        }

2.4 Update existing lease
-------------------------

.. http:put:: /v1/leases/{lease_id}

* Normal Response Code: 202 ACCEPTED
* Returns the updated information about lease.
* Requires a request body.

**Example**
    **request**

    .. sourcecode:: http

        PUT /v1/leases/aaaa-bbbb-cccc-dddd  HTTP/1.1

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
            "created_at": "2014-02-26 10:00:00",
            "end_date": "new_date",
            "events": [
                {
                    "created_at": "2014-02-26 10:00:00",
                    "event_type": "start_lease",
                    "id": "event_id_1",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "status": "UNDONE",
                    "time": "1234",
                    "updated_at": null
                },
                {
                    "created_at": "2014-02-26 10:25:52",
                    "event_type": "end_lease",
                    "id": "event_id_2",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "status": "UNDONE",
                    "time": "2345",
                    "updated_at": null
                }
            ],
            "id": "aaaa-bbbb-cccc-dddd",
            "name": "new_name",
            "reservations": [
                {
                    "created_at": "2014-02-26 10:00:00",
                    "id": "reservation_id",
                    "lease_id": "aaaa-bbbb-cccc-dddd",
                    "resource_id": "1234-1234-1234",
                    "resource_type": "virtual:instance",
                    "status": "pending",
                    "updated_at": null
                }
            ],
            "start_date": "1234",
            "project_id": "project_id",
            "trust_id": "trust_id",
            "updated_at": null,
            "user_id": "user_id"
        }

2.5 Delete existing lease
-------------------------

.. http:delete:: /v1/leases/{lease_id}

* Normal Response Code: 204 NO CONTENT
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        DELETE /v1/leases/aaaa-bbbb-cccc-dddd HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 204 NO CONTENT
        Content-Type: application/json


3 Hosts
=======

**Description**

Host is the main abstraction for a Nova Compute host. It is necessary to
enroll compute hosts in Blazar so that the host becomes dedicated to Blazar,
and won't accept other VM creation requests but the ones asked subsequently by
leases requests for dedicated hosts within Blazar. If no extra arguments but
the name are passed when creating a host, Blazar will take Nova
specifications, like VCPUs, RAM or cpu_info. There is a possibility to add what
we call arbitrary extra parameters (not provided within the Nova model) like
number of GPUs, color of the server or anything that needs to be filtered for a
user query.

**Hosts ops**

+--------+------------------------+---------------------------------------------------------------------------------+
| Verb   | URI                    | Description                                                                     |
+========+========================+=================================================================================+
| GET    | /v1/os-hosts           | Lists all hosts registered in Blazar.                                          |
+--------+------------------------+---------------------------------------------------------------------------------+
| POST   | /v1/os-hosts           | Create new host with possibly extra parameters.                                 |
+--------+------------------------+---------------------------------------------------------------------------------+
| GET    | /v1/os-hosts/{host_id} | Shows information about specified host, including extra parameters if existing. |
+--------+------------------------+---------------------------------------------------------------------------------+
| PUT    | /v1/os-hosts/{host_id} | Updates specified host (only extra parameters are possible to change).          |
+--------+------------------------+---------------------------------------------------------------------------------+
| DELETE | /v1/os-hosts/{host_id} | Deletes specified host.                                                         |
+--------+------------------------+---------------------------------------------------------------------------------+

3.1 List all hosts
------------------

.. http:get:: /v1/hosts

* Normal Response Code: 200 (OK)
* Returns the list of all hosts.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET /v1/os-hosts HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        [
            {
                "cpu_info": "{'some_cpu_info': 'some_cpu_info'}",
                "created_at": "2014-01-01 08:00:00",
                "hypervisor_hostname": "compute1",
                "hypervisor_type": "QEMU",
                "hypervisor_version": 1000000,
                "id": "1",
                "local_gb": 8,
                "memory_mb": 3954,
                "status": null,
                "updated_at": null,
                "vcpus": 2
            },
            {
                "cpu_info": "{'some_cpu_info': 'some_cpu_info'}",
                "created_at": "2014-01-01 09:00:00",
                "hypervisor_hostname": "compute2",
                "hypervisor_type": "QEMU",
                "hypervisor_version": 1000000,
                "id": "2",
                "local_gb": 8,
                "memory_mb": 3954,
                "status": null,
                "updated_at": null,
                "vcpus": 2
            }
        ]

3.2 Create host
---------------

.. http:post:: /v1/hosts

* Normal Response Code: 202 (ACCEPTED)
* Returns the information about created host, including extra parameters if
  any.
* Requires a request body.

**Example**
    **request**

    .. sourcecode:: http

        POST /v1/os-hosts HTTP/1.1

    .. sourcecode:: json

        {
            "name": "compute",
            "values": {
                "banana": "true"
            }
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "banana": "true",
            "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                          'arch': 'x86_64', 'features': [
                              'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                              'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                              'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                              'clflush', 'pse36', 'pat', 'cmov', 'mca',
                              'pge', 'mtrr', 'apic', 'pae'],
                          'topology': {
                              'cores': 1, 'threads': 1, 'sockets': 2}}",
            "created_at": "2014-02-26 08:00:00",
            "hypervisor_hostname": "compute",
            "hypervisor_type": "QEMU",
            "hypervisor_version": 1000000,
            "id": "1",
            "local_gb": 8,
            "memory_mb": 3954,
            "status": null,
            "updated_at": null,
            "vcpus": 2
        }

3.3 Show info about host
------------------------

.. http:get:: /v1/hosts/{host_id}

* Normal Response Code: 200 (OK)
* Returns the information about specified host, including extra parameters if
  any.
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        GET /v1/os-hosts/1 HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        {
            "banana": "true",
            "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                          'arch': 'x86_64', 'features': [
                              'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                              'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                              'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                              'clflush', 'pse36', 'pat', 'cmov', 'mca',
                              'pge', 'mtrr', 'apic', 'pae'],
                          'topology': {
                              'cores': 1, 'threads': 1, 'sockets': 2}}",
            "created_at": "2014-02-26 08:00:00",
            "hypervisor_hostname": "compute",
            "hypervisor_type": "QEMU",
            "hypervisor_version": 1000000,
            "id": "1",
            "local_gb": 8,
            "memory_mb": 3954,
            "status": null,
            "updated_at": null,
            "vcpus": 2
        }

3.4 Update existing host
------------------------

.. http:put:: /v1/hosts/{host_id}

* Normal Response Code: 202 (ACCEPTED)
* Returns the updated information about host.
* Requires a request body.

**Example**
    **request**

    .. sourcecode:: http

        PUT /v1/os-hosts/1 HTTP/1.1

    .. sourcecode:: json

        {
            "values": {
                "banana": "false"
            }
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "banana": "false",
            "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                          'arch': 'x86_64', 'features': [
                              'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                              'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                              'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                              'clflush', 'pse36', 'pat', 'cmov', 'mca',
                              'pge', 'mtrr', 'apic', 'pae'],
                          'topology': {
                              'cores': 1, 'threads': 1, 'sockets': 2}}",
            "created_at": "2014-02-26 08:00:00",
            "hypervisor_hostname": "compute",
            "hypervisor_type": "QEMU",
            "hypervisor_version": 1000000,
            "id": "1",
            "local_gb": 8,
            "memory_mb": 3954,
            "status": null,
            "updated_at": null,
            "vcpus": 2
        }

3.5 Delete existing host
------------------------

.. http:delete:: /v1/hosts/{host_id}

* Normal Response Code: 204 (NO CONTENT)
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        DELETE /v1/os-hosts/1 HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 204 NO CONTENT
        Content-Type: application/json

4 Plugins
=========

**Description**

Plugins are working with different resources types. Technically speaking they
are implemented using stevedore extensions. Currently plugins API requests are
not implemented, listed below examples are their possible view.

**Plugin ops**

**TBD** - https://blueprints.launchpad.net/blazar/+spec/create-plugin-api-endpoint

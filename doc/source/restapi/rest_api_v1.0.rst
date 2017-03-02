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
| GET    | /v1/leases            | Lists all leases registered in Blazar.                                        |
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

        {
            "leases": [
                {
                    "status": null,
                    "user_id": null,
                    "name": "lease_foo",
                    "end_date": "2017-02-24T20:00:00.000000",
                    "reservations": [
                        {
                            "status": "pending",
                            "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                            "min": 1,
                            "max": 1,
                            "resource_id": "5",
                            "created_at": "2017-02-21 14:50:38",
                            "updated_at": null,
                            "hypervisor_properties": "[\"==\", \"$hypervisor_hostname\", \"compute\"]",
                            "resource_properties": "",
                            "id": "087bc740-6d2d-410b-9d47-c7b2b55a9d36",
                            "resource_type": "physical:host"
                        }
                    ],
                    "created_at": "2017-02-21 14:50:38",
                    "updated_at": null,
                    "events": [
                        {
                            "status": "UNDONE",
                            "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                            "event_type": "start_lease",
                            "created_at": "2017-02-21 14:50:38",
                            "updated_at": null,
                            "time": "2017-02-21T20:00:00.000000",
                            "id": "188a8584-f832-4df9-9a4a-51e6364420ff"
                        },
                        {
                            "status": "UNDONE",
                            "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                            "event_type": "end_lease",
                            "created_at": "2017-02-21 14:50:38",
                            "updated_at": null,
                            "time": "2017-02-24T20:00:00.000000",
                            "id": "277d6436-dfcb-4eae-ae5e-ac7fa9c2fd56"
                        },
                        {
                            "status": "UNDONE",
                            "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                            "event_type": "before_end_lease",
                            "created_at": "2017-02-21 14:50:38",
                            "updated_at": null,
                            "time": "2017-02-22T20:00:00.000000",
                            "id": "f583af71-ca21-4b66-87de-52211d118029"
                        }
                    ],
                    "id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                    "action": null,
                    "project_id": "aa45f56901ef45ee95e3d211097c0ea3",
                    "status_reason": null,
                    "start_date": "2017-02-21T20:00:00.000000",
                    "trust_id": "b442a580b9504ababf305bf2b4c49512"
                }
            ]
        }

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
            "start_date": "2017-2-21 20:00",
            "end_date": "2017-2-24 20:00",
            "reservations": [
                {
                    "hypervisor_properties": "[\"==\", \"$hypervisor_hostname\", \"compute\"]",
                    "max": 1,
                    "min": 1,
                    "resource_type": "physical:host",
                    "resource_properties": ""
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
            "lease":
            {
                "status": null,
                "user_id": null,
                "name": "lease_foo",
                "end_date": "2017-02-24T20:00:00.000000",
                "reservations": [
                    {
                        "status": "pending",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "min": 1,
                        "max": 1,
                        "hypervisor_properties": "[\"==\", \"$hypervisor_hostname\", \"compute\"]",
                        "resource_id": "5",
                        "resource_properties": "",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "id": "087bc740-6d2d-410b-9d47-c7b2b55a9d36",
                        "resource_type": "physical:host"
                    }
                ],
                "created_at": "2017-02-21 14:50:38",
                "updated_at": null,
                "events": [
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "start_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-21T20:00:00.000000",
                        "id": "188a8584-f832-4df9-9a4a-51e6364420ff"
                    },
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "end_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-24T20:00:00.000000",
                        "id": "277d6436-dfcb-4eae-ae5e-ac7fa9c2fd56"
                    },
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "before_end_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-22T20:00:00.000000",
                        "id": "f583af71-ca21-4b66-87de-52211d118029"
                    }
                ],
                "id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                "action": null,
                "project_id": "aa45f56901ef45ee95e3d211097c0ea3",
                "status_reason": null,
                "start_date": "2017-02-21T20:00:00.000000",
                "trust_id": "b442a580b9504ababf305bf2b4c49512"
            }
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

        GET /v1/leases/6ee55c78-ac52-41a6-99af-2d2d73bcc466  HTTP/1.1

    **response**

    .. sourcecode:: http

        HTTP/1.1 200 OK
        Content-Type: application/json

    .. sourcecode:: json

        {
            "lease": 
            {
                "status": null,
                "user_id": null,
                "name": "lease_foo",
                "end_date": "2017-02-24T20:00:00.000000",
                "reservations": [
                    {
                        "status": "pending",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "min": 1,
                        "max": 1,
                        "resource_id": "5",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "hypervisor_properties": "[\"==\", \"$hypervisor_hostname\", \"compute\"]",
                        "resource_properties": "",
                        "id": "087bc740-6d2d-410b-9d47-c7b2b55a9d36",
                        "resource_type": "physical:host"
                    }
                ],
                "created_at": "2017-02-21 14:50:38",
                "updated_at": null,
                "events": [
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "start_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-21T20:00:00.000000",
                        "id": "188a8584-f832-4df9-9a4a-51e6364420ff"
                    },
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "end_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-24T20:00:00.000000",
                        "id": "277d6436-dfcb-4eae-ae5e-ac7fa9c2fd56"
                    },
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "before_end_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-22T20:00:00.000000",
                        "id": "f583af71-ca21-4b66-87de-52211d118029"
                    }
                ],
                "id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                "action": null,
                "project_id": "aa45f56901ef45ee95e3d211097c0ea3",
                "status_reason": null,
                "start_date": "2017-02-21T20:00:00.000000",
                "trust_id": "b442a580b9504ababf305bf2b4c49512"
            }
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

        PUT /v1/leases/6ee55c78-ac52-41a6-99af-2d2d73bcc466  HTTP/1.1

    .. sourcecode:: json

        {
            "name": "lease_new_foo",
            "end_date": "2017-3-12 12:00",
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "lease": 
            {
                "status": null,
                "user_id": null,
                "name": "lease_new_foo",
                "end_date": "2017-03-12T12:00:00.000000",
                "reservations": [
                    {
                        "status": "pending",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "min": 1,
                        "max": 1,
                        "resource_id": "5",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "hypervisor_properties": "[\"==\", \"$hypervisor_hostname\", \"compute\"]",
                        "resource_properties": "",
                        "id": "087bc740-6d2d-410b-9d47-c7b2b55a9d36",
                        "resource_type": "physical:host"
                    }
                ],
                "created_at": "2017-02-21 14:50:38",
                "updated_at": "2017-02-21 14:56:32",
                "events": [
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "start_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": null,
                        "time": "2017-02-21T20:00:00.000000",
                        "id": "188a8584-f832-4df9-9a4a-51e6364420ff"
                    },
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "end_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": "2017-02-21 14:56:32",
                        "time": "2017-03-12T12:00:00.000000",
                        "id": "277d6436-dfcb-4eae-ae5e-ac7fa9c2fd56"
                    },
                    {
                        "status": "UNDONE",
                        "lease_id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                        "event_type": "before_end_lease",
                        "created_at": "2017-02-21 14:50:38",
                        "updated_at": "2017-02-21 14:56:32",
                        "time": "2017-03-10T12:00:00.000000",
                        "id": "f583af71-ca21-4b66-87de-52211d118029"
                    }
                ],
                "id": "6ee55c78-ac52-41a6-99af-2d2d73bcc466",
                "action": null,
                "project_id": "aa45f56901ef45ee95e3d211097c0ea3",
                "status_reason": null,
                "start_date": "2017-02-21T20:00:00.000000",
                "trust_id": "b442a580b9504ababf305bf2b4c49512"
            }
        }

2.5 Delete existing lease
-------------------------

.. http:delete:: /v1/leases/{lease_id}

* Normal Response Code: 204 NO CONTENT
* Does not require a request body.

**Example**
    **request**

    .. sourcecode:: http

        DELETE /v1/leases/6ee55c78-ac52-41a6-99af-2d2d73bcc466 HTTP/1.1

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
| GET    | /v1/os-hosts           | Lists all hosts registered in Blazar.                                           |
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

        {
            "hosts": [
                {
                    "status": null,
                    "hypervisor_type": "QEMU",
                    "created_at": "2017-02-21 14:29:55",
                    "updated_at": null,
                    "hypervisor_hostname": "compute-1",
                    "memory_mb": 5968,
                    "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                                  'arch': 'x86_64', 'features': [
                                      'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                                      'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                                      'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                                      'clflush', 'pse36', 'pat', 'cmov', 'mca',
                                      'pge', 'mtrr', 'apic', 'pae'],
                                  'topology': {
                                      'cores': 1, 'threads': 1, 'sockets': 2, 'cells': 1}}",              
                    "vcpus": 1,
                    "service_name": "blazar",
                    "hypervisor_version": 2005000,
                    "local_gb": 13,
                    "id": "1",
                    "trust_id": "454ebdadd56142c896571d749ea86e95"
                }, 
                {
                    "status": null,
                    "hypervisor_type": "QEMU",
                    "created_at": "2017-02-20 12:20:31",
                    "updated_at": null,
                    "hypervisor_hostname": "compute-2",
                    "memory_mb": 5968,
                    "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                                  'arch': 'x86_64', 'features': [
                                      'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                                      'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                                      'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                                      'clflush', 'pse36', 'pat', 'cmov', 'mca',
                                      'pge', 'mtrr', 'apic', 'pae'],
                                  'topology': {
                                      'cores': 2, 'threads': 2, 'sockets': 2, 'cells': 1}}",                    
                    "vcpus": 1,
                    "service_name": "blazar",
                    "hypervisor_version": 2005000,
                    "local_gb": 20,
                    "id": "2",
                    "trust_id": "345adbead12345c769081d971ea86e36"
                }
            ]
        }

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
            "name": "compute"
        }

    **response**

    .. sourcecode:: http

        HTTP/1.1 202 ACCEPTED
        Content-Type: application/json

    .. sourcecode:: json

        {
            "host":
            {
                "status": null,
                "hypervisor_type": "QEMU",
                "created_at": "2017-02-21 14:29:55",
                "updated_at": null,
                "hypervisor_hostname": "compute",
                "memory_mb": 5968,
                "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                              'arch': 'x86_64', 'features': [
                                  'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                                  'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                                  'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                                  'clflush', 'pse36', 'pat', 'cmov', 'mca',
                                  'pge', 'mtrr', 'apic', 'pae'],
                              'topology': {
                                  'cores': 1, 'threads': 1, 'sockets': 2, 'cells': 1}}",
                "vcpus": 1,
                "service_name": "blazar",
                "hypervisor_version": 2005000,
                "local_gb": 13,
                "id": "1",
                "trust_id": "454ebdadd56142c896571d749ea86e95"
            }
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
            "host": 
            {
                "status": null,
                "hypervisor_type": "QEMU",
                "created_at": "2017-02-21 14:29:55",
                "updated_at": null,
                "hypervisor_hostname": "blazar",
                "memory_mb": 5968,
                "cpu_info": "{'vendor': 'Intel', 'model': 'pentium',
                              'arch': 'x86_64', 'features': [
                                  'lahf_lm', 'lm', 'nx', 'syscall', 'hypervisor',
                                  'aes', 'popcnt', 'x2apic', 'sse4.2', 'cx16',
                                  'ssse3', 'pni', 'ss', 'sse2', 'sse', 'fxsr',
                                  'clflush', 'pse36', 'pat', 'cmov', 'mca',
                                  'pge', 'mtrr', 'apic', 'pae'],
                              'topology': {
                                  'cores': 1, 'threads': 1, 'sockets': 2, 'cells': 1}}",                    
                "vcpus": 1,
                "service_name": "blazar",
                "hypervisor_version": 2005000,
                "local_gb": 13,
                "id": "1",
                "trust_id": "454ebdadd56142c896571d749ea86e95"
            }
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

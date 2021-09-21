.. -*- rst -*-

=====
Hosts
=====

List Hosts
==========

.. rest_method:: GET v1/os-hosts

List hosts.

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

  - hosts: hosts
  - id: host_id
  - hypervisor_hostname: host_hypervisor_hostname
  - hypervisor_type: host_hypervisor_type
  - hypervisor_version: host_hypervisor_version
  - vcpus: host_vcpus
  - cpu_info: host_cpu_info
  - memory_mb: host_memory_mb
  - local_gb: host_local_gb
  - service_name: host_service_name
  - reservable: host_reservable
  - status: host_status
  - trust_id: host_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - extra_capability: host_extra_capability

**Example of List Hosts Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-list-resp.json
  :language: javascript

Create Host
===========

.. rest_method:: POST v1/os-hosts

Create a host.

**Response codes**

Normal response code: 201

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Conflict(409), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - name: host_name
  - extra_capability: host_extra_capability

**Example of Create Host Request**

.. literalinclude:: ../../../doc/api_samples/hosts/host-create-req.json
  :language: javascript

Response
--------

.. rest_parameters:: parameters.yaml

  - host: host
  - id: host_id
  - hypervisor_hostname: host_hypervisor_hostname
  - hypervisor_type: host_hypervisor_type
  - hypervisor_version: host_hypervisor_version
  - vcpus: host_vcpus
  - cpu_info: host_cpu_info
  - memory_mb: host_memory_mb
  - local_gb: host_local_gb
  - service_name: host_service_name
  - reservable: host_reservable
  - status: host_status
  - trust_id: host_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - extra_capability: host_extra_capability

**Example of Create Host Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-create-resp.json
  :language: javascript

Show Host Details
=================

.. rest_method:: GET v1/os-hosts/{host_id}

Show details of a host.

**Preconditions**

The host must exist.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Not Found(404), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - host_id: host_id_path
  - private: property_private

Response
--------

.. rest_parameters:: parameters.yaml

  - host: host
  - id: host_id
  - hypervisor_hostname: host_hypervisor_hostname
  - hypervisor_type: host_hypervisor_type
  - hypervisor_version: host_hypervisor_version
  - vcpus: host_vcpus
  - cpu_info: host_cpu_info
  - memory_mb: host_memory_mb
  - local_gb: host_local_gb
  - service_name: host_service_name
  - reservable: host_reservable
  - status: host_status
  - trust_id: host_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - extra_capability: host_extra_capability

**Example of Show Host Details Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-details-resp.json
  :language: javascript

Update Host
===========

.. rest_method:: PUT v1/os-hosts/{host_id}

Update a host.

**Preconditions**

The host must exist.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Not Found(404), Conflict(409), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - host_id: host_id_path
  - extra_capability: host_extra_capability

**Example of Update Host Request**

.. literalinclude:: ../../../doc/api_samples/hosts/host-update-req.json
  :language: javascript

Response
--------

.. rest_parameters:: parameters.yaml

  - host: host
  - id: host_id
  - hypervisor_hostname: host_hypervisor_hostname
  - hypervisor_type: host_hypervisor_type
  - hypervisor_version: host_hypervisor_version
  - vcpus: host_vcpus
  - cpu_info: host_cpu_info
  - memory_mb: host_memory_mb
  - local_gb: host_local_gb
  - service_name: host_service_name
  - reservable: host_reservable
  - status: host_status
  - trust_id: host_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - extra_capability: host_extra_capability

**Example of Host Update Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-update-resp.json
  :language: javascript

Delete Host
===========

.. rest_method:: DELETE v1/os-hosts/{host_id}

Delete a host.

**Preconditions**

The host must exist.

**Response codes**

Normal response code: 204

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Not Found(404), Conflict(409), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - host_id: host_id_path

Response
--------

No body content is returned on a successful DELETE.

====================
Resource Allocations
====================

List Allocations
================

.. rest_method:: GET v1/os-hosts/allocations

List allocations of all hosts.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - lease_id: allocation_lease_id_query
  - reservation_id: allocation_reservation_id_query

Response
--------

.. rest_parameters:: parameters.yaml

  - allocations: allocations
  - resource_id: host_id
  - reservations: reservation_allocation
  - reservation.id: reservation_id
  - reservation.lease_id: lease_id
  - reservation.start_date: allocation_start_date
  - reservation.end_date: allocation_end_date

**Example of List Allocations Response**

.. literalinclude:: ../../../doc/api_samples/hosts/allocation-list-resp.json
   :language: javascript

Get Allocation
==============

.. rest_method:: GET v1/os-hosts/{host_id}/allocation

Get allocation of a host.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - host_id: host_id_path
  - lease_id: allocation_lease_id_query
  - reservation_id: allocation_reservation_id_query

Response
--------

.. rest_parameters:: parameters.yaml

  - allocation: allocation
  - resource_id: host_id
  - reservations: reservation_allocation
  - reservation.id: reservation_id
  - reservation.lease_id: lease_id
  - reservation.start_date: allocation_start_date
  - reservation.end_date: allocation_end_date

**Example of Get Allocation Response**

.. literalinclude:: ../../../doc/api_samples/hosts/allocation-get-resp.json
   :language: javascript

List Resource Properties
========================

.. rest_method:: GET v1/os-hosts/properties

Get all resource properties from host

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - detail: resource_property_detail
  - all: resource_property_all

Response
--------

.. rest_parameters:: parameters.yaml

  - resource_properties: resource_properties
  - property: resource_properties_property
  - private: resource_properties_private
  - values: resource_properties_values

**Example of List Resource Properties Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-property-list.json
   :language: javascript

**Example of List Resource Properties With Detail Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-property-list-detail.json
   :language: javascript

Update Resource Properties
==========================

.. rest_method:: PATCH v1/os-hosts/properties/{property_name}

Update a host resource properties

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - property_name: property_name
  - private: property_private

**Example of Update Resource Properties**

.. literalinclude:: ../../../doc/api_samples/hosts/host-property-update.json
  :language: javascript

Response
--------

.. rest_parameters:: parameters.yaml

  - created_at: created_at
  - updated_at: updated_at
  - id: resource_property_id
  - resource_type: resource_property_resource_type
  - property_name: resource_properties_property
  - private: resource_property_private

**Example of List Resource Properties Response**

.. literalinclude:: ../../../doc/api_samples/hosts/host-property-update-res.json
   :language: javascript


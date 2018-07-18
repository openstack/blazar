.. -*- rst -*-

======
Leases
======

A date and time format for *\*_date* parameters is ``CCYY-MM-DD hh:mm``.
For example, ``2017-12-26 12:00``.

List Leases
===========

.. rest_method:: GET v1/leases

List leases.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Internal Server Error(500)

Request
-------

No body content, path, nor query option.

Response
--------

General Parameters
^^^^^^^^^^^^^^^^^^

.. rest_parameters:: parameters.yaml

  - leases: leases
  - id: lease_id
  - name: lease_name
  - start_date: lease_start_date_resp
  - end_date: lease_end_date
  - status: lease_status
  - degraded: lease_degraded
  - user_id: lease_user_id
  - project_id: lease_project_id
  - trust_id: lease_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - reservations: reservations
  - reservation.id: reservation_id
  - reservation.lease_id: reservation_lease_id
  - reservation.status: reservation_status
  - reservation.missing_resources: reservation_missing_resources
  - reservation.resources_changed: reservation_resources_changed
  - reservation.resource_id: reservation_resource_id
  - reservation.resource_type: reservation_resource_type
  - reservation.created_at: created_at
  - reservation.updated_at: updated_at
  - events: events
  - event.id: event_id
  - event.lease_id: event_lease_id
  - event.status: event_status
  - event.event_type: event_type
  - event.time: event_time
  - event.created_at: created_at
  - event_updated_at: updated_at

Parameters for Host Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for host reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.min: reservation_min
  - reservation.max: reservation_max
  - reservation.hypervisor_properties: reservation_hypervisor_properties
  - reservation.resource_properties: reservation_resource_properties
  - reservation.before_end: reservation_before_end

Parameters for Instance Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for instance reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.amount: reservation_amount
  - reservation.vcpus: reservation_vcpus
  - reservation.memory_mb: reservation_memory_mb
  - reservation.disk_gb: reservation_disk_gb
  - reservation.affinity : reservation_affinity
  - reservation.resource_properties: reservation_resource_properties
  - reservation.flavor_id: reservation_flavor_id
  - reservation.server_group_id: reservation_server_group_id
  - reservation.aggregate_id: reservation_aggregate_id

**Example of List Leases Response**

.. literalinclude:: ../../../doc/api_samples/leases/lease-list-resp.json
  :language: javascript

Create Lease
============

.. rest_method:: POST v1/leases

Create a lease.

**Response codes**

Normal response code: 201

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Conflict(409), Internal Server Error(500)

Request
-------

General Parameters
^^^^^^^^^^^^^^^^^^

.. rest_parameters:: parameters.yaml

  - name: lease_name
  - start_date: lease_start_date
  - end_date: lease_end_date
  - before_end_date: lease_before_end_date_optional
  - reservations: reservations
  - reservation.resource_type: reservation_resource_type
  - events: events_optional

Parameters for Host Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are required for host reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.min: reservation_min
  - reservation.max: reservation_max
  - reservation.hypervisor_properties: reservation_hypervisor_properties
  - reservation.resource_properties: reservation_resource_properties
  - reservation.before_end: reservation_before_end_optional

Parameters for Instance Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are required for instance reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.amount: reservation_amount
  - reservation.vcpus: reservation_vcpus
  - reservation.memory_mb: reservation_memory_mb
  - reservation.disk_gb: reservation_disk_gb
  - reservation.affinity : reservation_affinity
  - reservation.resource_properties: reservation_resource_properties

**Example of Create Lease Request**

.. literalinclude:: ../../../doc/api_samples/leases/lease-create-req.json
  :language: javascript

Response
--------

General Parameters
^^^^^^^^^^^^^^^^^^

.. rest_parameters:: parameters.yaml

  - lease: lease
  - id: lease_id
  - name: lease_name
  - start_date: lease_start_date_resp
  - end_date: lease_end_date
  - status: lease_status
  - degraded: lease_degraded
  - user_id: lease_user_id
  - project_id: lease_project_id
  - trust_id: lease_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - reservations: reservations
  - reservation.id: reservation_id
  - reservation.lease_id: reservation_lease_id
  - reservation.status: reservation_status
  - reservation.missing_resources: reservation_missing_resources
  - reservation.resources_changed: reservation_resources_changed
  - reservation.resource_id: reservation_resource_id
  - reservation.resource_type: reservation_resource_type
  - reservation.created_at: created_at
  - reservation.updated_at: updated_at
  - events: events
  - event.id: event_id
  - event.lease_id: event_lease_id
  - event.status: event_status
  - event.event_type: event_type
  - event.time: event_time
  - event.created_at: created_at
  - event_updated_at: updated_at

Parameters for Host Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for host reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.min: reservation_min
  - reservation.max: reservation_max
  - reservation.hypervisor_properties: reservation_hypervisor_properties
  - reservation.resource_properties: reservation_resource_properties
  - reservation.before_end: reservation_before_end

Parameters for Instance Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for instance reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.amount: reservation_amount
  - reservation.vcpus: reservation_vcpus
  - reservation.memory_mb: reservation_memory_mb
  - reservation.disk_gb: reservation_disk_gb
  - reservation.affinity : reservation_affinity
  - reservation.resource_properties: reservation_resource_properties
  - reservation.flavor_id: reservation_flavor_id
  - reservation.server_group_id: reservation_server_group_id
  - reservation.aggregate_id: reservation_aggregate_id

**Example of Create Lease Response**

.. literalinclude:: ../../../doc/api_samples/leases/lease-create-resp.json
  :language: javascript

Show Lease Details
==================

.. rest_method:: GET v1/leases/{lease_id}

Show details of a lease.

**Preconditions**

The lease must exist.

**Response codes**

Normal response code: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403),
Not Found(404), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - lease_id: lease_id_path

Response
--------

General Parameters
^^^^^^^^^^^^^^^^^^

.. rest_parameters:: parameters.yaml

  - lease: lease
  - id: lease_id
  - name: lease_name
  - start_date: lease_start_date_resp
  - end_date: lease_end_date
  - status: lease_status
  - degraded: lease_degraded
  - user_id: lease_user_id
  - project_id: lease_project_id
  - trust_id: lease_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - reservations: reservations
  - reservation.id: reservation_id
  - reservation.lease_id: reservation_lease_id
  - reservation.status: reservation_status
  - reservation.missing_resources: reservation_missing_resources
  - reservation.resources_changed: reservation_resources_changed
  - reservation.resource_id: reservation_resource_id
  - reservation.resource_type: reservation_resource_type
  - reservation.created_at: created_at
  - reservation.updated_at: updated_at
  - events: events
  - event.id: event_id
  - event.lease_id: event_lease_id
  - event.status: event_status
  - event.event_type: event_type
  - event.time: event_time
  - event.created_at: created_at
  - event_updated_at: updated_at

Parameters for Host Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for host reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.min: reservation_min
  - reservation.max: reservation_max
  - reservation.hypervisor_properties: reservation_hypervisor_properties
  - reservation.resource_properties: reservation_resource_properties
  - reservation.before_end: reservation_before_end

Parameters for Instance Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for instance reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.amount: reservation_amount
  - reservation.vcpus: reservation_vcpus
  - reservation.memory_mb: reservation_memory_mb
  - reservation.disk_gb: reservation_disk_gb
  - reservation.affinity : reservation_affinity
  - reservation.resource_properties: reservation_resource_properties
  - reservation.flavor_id: reservation_flavor_id
  - reservation.server_group_id: reservation_server_group_id
  - reservation.aggregate_id: reservation_aggregate_id

**Example of Show Lease Details Response**

.. literalinclude:: ../../../doc/api_samples/leases/lease-details-resp.json
  :language: javascript

Update Lease
============

.. rest_method:: PUT v1/leases/{lease_id}

Update a lease.

**Preconditions**

The lease must exist.

**Response codes**

Normal response codes: 200

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403), Not Found(404),
Conflict(409), Internal Server Error(500)

Request
-------

General Parameters
^^^^^^^^^^^^^^^^^^

.. rest_parameters:: parameters.yaml

  - lease_id: lease_id_path
  - name: lease_name_optional
  - start_date: lease_start_date_optional
  - end_date: lease_end_date_optional
  - before_end_date: lease_before_end_date_optional
  - reservations: reservations_optional
  - reservation.id: reservation_id

Parameters for Host Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are required for host reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.min: reservation_min_optional
  - reservation.max: reservation_max_optional
  - reservation.hypervisor_properties: reservation_hypervisor_properties_optional
  - reservation.resource_properties: reservation_resource_properties_optional
  - reservation.before_end: reservation_before_end_optional

Parameters for Instance Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are required for instance reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.amount: reservation_amount_optional
  - reservation.vcpus: reservation_vcpus_optional
  - reservation.memory_mb: reservation_memory_mb_optional
  - reservation.disk_gb: reservation_disk_gb_optional
  - reservation.affinity : reservation_affinity_optional
  - reservation.resource_properties: reservation_resource_properties_optional

**Example of Update Lease Request**

.. literalinclude:: ../../../doc/api_samples/leases/lease-update-req.json
  :language: javascript

Response
--------

General Parameters
^^^^^^^^^^^^^^^^^^

.. rest_parameters:: parameters.yaml

  - lease: lease
  - id: lease_id
  - name: lease_name
  - start_date: lease_start_date_resp
  - end_date: lease_end_date
  - status: lease_status
  - degraded: lease_degraded
  - user_id: lease_user_id
  - project_id: lease_project_id
  - trust_id: lease_trust_id
  - created_at: created_at
  - updated_at: updated_at
  - reservations: reservations
  - reservation.id: reservation_id
  - reservation.lease_id: reservation_lease_id
  - reservation.status: reservation_status
  - reservation.missing_resources: reservation_missing_resources
  - reservation.resources_changed: reservation_resources_changed
  - reservation.resource_id: reservation_resource_id
  - reservation.resource_type: reservation_resource_type
  - reservation.created_at: created_at
  - reservation.updated_at: updated_at
  - events: events
  - event.id: event_id
  - event.lease_id: event_lease_id
  - event.status: event_status
  - event.event_type: event_type
  - event.time: event_time
  - event.created_at: created_at
  - event_updated_at: updated_at

Parameters for Host Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for host reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.min: reservation_min
  - reservation.max: reservation_max
  - reservation.hypervisor_properties: reservation_hypervisor_properties
  - reservation.resource_properties: reservation_resource_properties
  - reservation.before_end: reservation_before_end

Parameters for Instance Reservation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The following parameters are returned for instance reservation. All parameters
are in the ``reservation`` object.

.. rest_parameters:: parameters.yaml

  - reservation.amount: reservation_amount
  - reservation.vcpus: reservation_vcpus
  - reservation.memory_mb: reservation_memory_mb
  - reservation.disk_gb: reservation_disk_gb
  - reservation.affinity : reservation_affinity
  - reservation.resource_properties: reservation_resource_properties
  - reservation.flavor_id: reservation_flavor_id
  - reservation.server_group_id: reservation_server_group_id
  - reservation.aggregate_id: reservation_aggregate_id

**Example of Update Lease Response**

.. literalinclude:: ../../../doc/api_samples/leases/lease-update-resp.json
  :language: javascript

Delete Lease
============

.. rest_method:: DELETE v1/leases/{lease_id}

Delete a lease.

**Preconditions**

The lease must exist.

**Response codes**

Normal response codes: 204

Error response codes: Bad Request(400), Unauthorized(401), Forbidden(403), Not Found(404),
Conflict(409), Internal Server Error(500)

Request
-------

.. rest_parameters:: parameters.yaml

  - lease_id: lease_id_path

Response
--------

No body content is returned on a successful DELETE.

Blazar
=======

Overview
--------
OpenStack Reservation Service


Prerequisites
-------------
* Keystone v3 API endpoint
* Dedicated account for write operations on behalf of the admin
   climate_username
* Service account

Configuration
-------------

Create identityv3 endpoint
^^^^^^^^^^^^^^^^^^^^^^^^^^
For adding new endpoint for Keystone V3, use the following instructions:
1) keystone service-create --name keystonev3 --type identytiv3 --description "Keystone Identity Service v3"
2) keystone endpoint-create --region <region> --service keystonev3 --publicurl "<auth_protocol>://<auth_host>:5000/v3" --adminurl "<auth_protocol>://<auth_host>:35357/v3" --internalurl "<auth_protocol>://<auth_host>:5000/v3"

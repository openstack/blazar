# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Defines interface for DB access.

Functions in this module are imported into the blazar.db namespace. Call these
functions from blazar.db namespace, not the blazar.db.api namespace.

All functions in this module return objects that implement a dictionary-like
interface.

**Related Flags**

:db_backend:  string to lookup in the list of LazyPluggable backends.
              `sqlalchemy` is the only supported backend right now.

:sql_connection:  string specifying the sqlalchemy connection to use, like:
                  `sqlite:///var/lib/blazar/blazar.sqlite`.

"""

from oslo_config import cfg
from oslo_db import api as db_api
from oslo_db import options as db_options
from oslo_log import log as logging


_BACKEND_MAPPING = {
    'sqlalchemy': 'blazar.db.sqlalchemy.api',
}

db_options.set_defaults(cfg.CONF)
IMPL = db_api.DBAPI(cfg.CONF.database.backend,
                    backend_mapping=_BACKEND_MAPPING)
LOG = logging.getLogger(__name__)


def get_instance():
    """Return a DB API instance."""
    return IMPL


def setup_db():
    """Set up database, create tables, etc.

    Return True on success, False otherwise
    """
    return IMPL.setup_db()


def drop_db():
    """Drop database.

    Return True on success, False otherwise
    """
    return IMPL.drop_db()


# Helpers for building constraints / equality checks


def constraint(**conditions):
    """Return a constraint object suitable for use with some updates."""
    return IMPL.constraint(**conditions)


def equal_any(*values):
    """Return an equality condition object suitable for use in a constraint.

    Equal_any conditions require that a model object's attribute equal any
    one of the given values.
    """
    return IMPL.equal_any(*values)


def not_equal(*values):
    """Return an inequality condition object suitable for use in a constraint.

    Not_equal conditions require that a model object's attribute differs from
    all of the given values.
    """
    return IMPL.not_equal(*values)


def to_dict(func):
    def decorator(*args, **kwargs):
        res = func(*args, **kwargs)

        if isinstance(res, list):
            return [item.to_dict() for item in res]

        if res:
            return res.to_dict()
        else:
            return None

    return decorator


# Reservation

def reservation_create(reservation_values):
    """Create a reservation from the values."""
    return IMPL.reservation_create(reservation_values)


@to_dict
def reservation_get_all_by_lease_id(lease_id):
    """Return all reservations belongs to specific lease."""
    return IMPL.reservation_get_all_by_lease_id(lease_id)


@to_dict
def reservation_get_all_by_values(**kwargs):
    """Returns all entries filtered by col=value."""
    return IMPL.reservation_get_all_by_values(**kwargs)


@to_dict
def reservation_get(reservation_id):
    """Return specific reservation."""
    return IMPL.reservation_get(reservation_id)


def reservation_destroy(reservation_id):
    """Delete specific reservation."""
    IMPL.reservation_destroy(reservation_id)


def reservation_update(reservation_id, reservation_values):
    """Update reservation."""
    IMPL.reservation_update(reservation_id, reservation_values)


# Lease

def lease_create(lease_values):
    """Create a lease from values."""
    return IMPL.lease_create(lease_values)


@to_dict
def lease_get_all():
    """Return all leases."""
    return IMPL.lease_get_all()


@to_dict
def lease_get_all_by_project(project_id):
    """Return all leases in specific project."""
    return IMPL.lease_get_all_by_project(project_id)


@to_dict
def lease_get_all_by_user(user_id):
    """Return all leases belongs to specific user."""
    return IMPL.lease_get_all_by_user(user_id)


@to_dict
def lease_get(lease_id):
    """Return lease."""
    return IMPL.lease_get(lease_id)


@to_dict
def lease_list(project_id=None):
    """Return a list of all existing leases."""
    return IMPL.lease_list(project_id)


def lease_destroy(lease_id):
    """Delete lease or raise if not exists."""
    IMPL.lease_destroy(lease_id)


def lease_update(lease_id, lease_values):
    """Update lease or raise if not exists."""
    IMPL.lease_update(lease_id, lease_values)


# Events

@to_dict
def event_create(event_values):
    """Create an event from values."""
    return IMPL.event_create(event_values)


@to_dict
def event_get_all():
    """Return all events."""
    return IMPL.event_get_all()


@to_dict
def event_get(event_id):
    """Return a specific event."""
    return IMPL.event_get(event_id)


@to_dict
def event_get_first_sorted_by_filters(sort_key, sort_dir, filters):
    """Return instances sorted by param."""
    return IMPL.event_get_first_sorted_by_filters(sort_key, sort_dir,
                                                  filters)


@to_dict
def event_get_all_sorted_by_filters(sort_key, sort_dir, filters):
    """Return instances sorted by param."""
    return IMPL.event_get_all_sorted_by_filters(sort_key, sort_dir,
                                                filters)


def event_destroy(event_id):
    """Delete event or raise if not exists."""
    IMPL.event_destroy(event_id)


def event_update(event_id, event_values):
    """Update event or raise if not exists."""
    IMPL.event_update(event_id, event_values)


# Host reservations

def host_reservation_create(host_reservation_values):
    """Create a host reservation from the values."""
    return IMPL.host_reservation_create(host_reservation_values)


@to_dict
def host_reservation_get_by_reservation_id(reservation_id):
    """Return host reservation belonging to specific reservation."""
    return IMPL.host_reservation_get_by_reservation_id(reservation_id)


@to_dict
def host_reservation_get(host_reservation_id):
    """Return specific host reservation."""
    return IMPL.host_reservation_get(host_reservation_id)


@to_dict
def host_reservation_get_all():
    """Return all hosts reservations."""
    return IMPL.host_reservation_get_all()


def host_reservation_destroy(host_reservation_id):
    """Delete specific host reservation."""
    IMPL.host_reservation_destroy(host_reservation_id)


def host_reservation_update(host_reservation_id,
                            host_reservation_values):
    """Update host reservation."""
    IMPL.host_reservation_update(host_reservation_id,
                                 host_reservation_values)


# Instance reservation

def instance_reservation_create(instance_reservation_values):
    """Create a instance reservation from the values."""
    return IMPL.instance_reservation_create(instance_reservation_values)


def instance_reservation_get(instance_reservation_id):
    """Return specific instance reservation."""
    return IMPL.instance_reservation_get(instance_reservation_id)


def instance_reservation_update(instance_reservation_id,
                                instance_reservation_values):
    """Update instance reservation."""
    return IMPL.instance_reservation_update(instance_reservation_id,
                                            instance_reservation_values)


def instance_reservation_destroy(instance_reservation_id):
    """Delete specific instance reservation."""
    return IMPL.instance_reservation_destroy(instance_reservation_id)


# Allocation

def host_allocation_create(allocation_values):
    """Create an allocation from the values."""
    return IMPL.host_allocation_create(allocation_values)


@to_dict
def host_allocation_get_all_by_values(**kwargs):
    """Returns all entries filtered by col=value."""
    return IMPL.host_allocation_get_all_by_values(**kwargs)


# TODO(frossigneux) get methods


def host_allocation_destroy(allocation_id):
    """Delete specific allocation."""
    IMPL.host_allocation_destroy(allocation_id)


def host_allocation_update(allocation_id, allocation_values):
    """Update allocation."""
    IMPL.host_allocation_update(allocation_id, allocation_values)


# Compute Hosts

def host_create(values):
    """Create a Compute host from the values."""
    return IMPL.host_create(values)


@to_dict
def host_get(host_id):
    """Return a specific Compute host."""
    return IMPL.host_get(host_id)


@to_dict
def host_list():
    """Return a list of events."""
    return IMPL.host_list()


@to_dict
def host_get_all_by_filters(filters):
    """Returns Compute hosts filtered by name of the field."""
    return IMPL.host_get_all_by_filters(filters)


@to_dict
def host_get_all_by_queries(queries):
    """Returns hosts filtered by an array of queries."""
    return IMPL.host_get_all_by_queries(queries)


@to_dict
def reservable_host_get_all_by_queries(queries):
    """Returns reservable hosts filtered by an array of queries."""
    return IMPL.reservable_host_get_all_by_queries(queries)


@to_dict
def unreservable_host_get_all_by_queries(queries):
    """Returns unreservable hosts filtered by an array of queries."""
    return IMPL.unreservable_host_get_all_by_queries(queries)


def host_destroy(host_id):
    """Delete specific Compute host."""
    IMPL.host_destroy(host_id)


def host_update(host_id, values):
    """Update Compute host."""
    IMPL.host_update(host_id, values)


# ComputeHostExtraCapabilities

def host_extra_capability_create(values):
    """Create a Host ExtraCapability from the values."""
    return IMPL.host_extra_capability_create(values)


@to_dict
def host_extra_capability_get(host_extra_capability_id):
    """Return a specific Host Extracapability."""
    return IMPL.host_extra_capability_get(host_extra_capability_id)


@to_dict
def host_extra_capability_get_all_per_host(host_id):
    """Return all extra_capabilities belonging to a specific Compute host."""
    return IMPL.host_extra_capability_get_all_per_host(host_id)


def host_extra_capability_destroy(host_extra_capability_id):
    """Delete specific host ExtraCapability."""
    IMPL.host_extra_capability_destroy(host_extra_capability_id)


def host_extra_capability_update(host_extra_capability_id, values):
    """Update specific host ExtraCapability."""
    IMPL.host_extra_capability_update(host_extra_capability_id, values)


def host_extra_capability_get_all_per_name(host_id,
                                           extra_capability_name):
    return IMPL.host_extra_capability_get_all_per_name(host_id,

                                                       extra_capability_name)


def host_extra_capability_get_latest_per_name(host_id, extra_capability_name):
    return IMPL.host_extra_capability_get_latest_per_name(
        host_id, extra_capability_name
    )


# Host matching

def host_get_all_by_queries_including_extracapabilities(queries):
    """Returns hosts filtered by an array of queries."""
    return IMPL.host_get_all_by_queries_including_extracapabilities(queries)


# Networks

def network_create(values):
    """Create a network from the values."""
    return IMPL.network_create(values)


@to_dict
def network_get(network_id):
    """Return a specific network."""
    return IMPL.network_get(network_id)


@to_dict
def network_list():
    """Return a list of networks."""
    return IMPL.network_list()


@to_dict
def network_get_all_by_filters(filters):
    """Returns Compute networks filtered by name of the field."""
    return IMPL.network_get_all_by_filters(filters)


@to_dict
def network_get_all_by_queries(queries):
    """Returns networks filtered by an array of queries."""
    return IMPL.network_get_all_by_queries(queries)


@to_dict
def reservable_network_get_all_by_queries(queries):
    """Returns reservable networks filtered by an array of queries."""
    return IMPL.reservable_network_get_all_by_queries(queries)


@to_dict
def unreservable_network_get_all_by_queries(queries):
    """Returns unreservable networks filtered by an array of queries."""
    return IMPL.unreservable_network_get_all_by_queries(queries)


def network_destroy(network_id):
    """Delete specific network."""
    IMPL.network_destroy(network_id)


def network_update(network_id, values):
    """Update network."""
    IMPL.network_update(network_id, values)


# Network allocations

def network_allocation_create(allocation_values):
    """Create an allocation from the values."""
    return IMPL.network_allocation_create(allocation_values)


@to_dict
def network_allocation_get_all_by_values(**kwargs):
    """Returns all entries filtered by col=value."""
    return IMPL.network_allocation_get_all_by_values(**kwargs)


def network_allocation_destroy(allocation_id):
    """Delete specific allocation."""
    IMPL.network_allocation_destroy(allocation_id)


# network reservation

def network_reservation_create(network_reservation_values):
    """Create a network reservation from the values."""
    return IMPL.network_reservation_create(network_reservation_values)


def network_reservation_get(network_reservation_id):
    """Return specific network reservation."""
    return IMPL.network_reservation_get(network_reservation_id)


def network_reservation_update(network_reservation_id,
                               network_reservation_values):
    """Update network reservation."""
    return IMPL.network_reservation_update(network_reservation_id,
                                           network_reservation_values)


def network_reservation_destroy(network_reservation_id):
    """Delete specific network reservation."""
    return IMPL.network_reservation_destroy(network_reservation_id)


# NetworkSegmentExtraCapabilities

def network_extra_capability_create(values):
    """Create a network ExtraCapability from the values."""
    return IMPL.network_extra_capability_create(values)


@to_dict
def network_extra_capability_get(network_extra_capability_id):
    """Return a specific network Extracapability."""
    return IMPL.network_extra_capability_get(network_extra_capability_id)


@to_dict
def network_extra_capability_get_all_per_network(network_id):
    """Return all extra_capabilities belonging to a specific network."""
    return IMPL.network_extra_capability_get_all_per_network(network_id)


def network_extra_capability_destroy(network_extra_capability_id):
    """Delete specific network ExtraCapability."""
    IMPL.network_extra_capability_destroy(network_extra_capability_id)


def network_extra_capability_update(network_extra_capability_id, values):
    """Update specific network ExtraCapability."""
    IMPL.network_extra_capability_update(network_extra_capability_id, values)


def network_extra_capability_get_all_per_name(network_id,
                                              extra_capability_name):
    return IMPL.network_extra_capability_get_all_per_name(
        network_id, extra_capability_name)


def network_extra_capability_get_latest_per_name(network_id,
                                                 extra_capability_name):
    return IMPL.network_extra_capability_get_latest_per_name(
        network_id, extra_capability_name
    )

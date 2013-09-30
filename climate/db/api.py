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

Functions in this module are imported into the climate.db namespace. Call these
functions from climate.db namespace, not the climate.db.api namespace.

All functions in this module return objects that implement a dictionary-like
interface.

**Related Flags**

:db_backend:  string to lookup in the list of LazyPluggable backends.
              `sqlalchemy` is the only supported backend right now.

:sql_connection:  string specifying the sqlalchemy connection to use, like:
                  `sqlite:///var/lib/climate/climate.sqlite`.

"""

from oslo.config import cfg

from climate.openstack.common.db import api as db_api
from climate.openstack.common import log as logging


CONF = cfg.CONF

_BACKEND_MAPPING = {
    'sqlalchemy': 'climate.db.sqlalchemy.api',
}

IMPL = db_api.DBAPI(backend_mapping=_BACKEND_MAPPING)
LOG = logging.getLogger(__name__)


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


## Helpers for building constraints / equality checks


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


#Reservation

def reservation_create(context, reservation_values):
    """Create a reservation from the values"""
    return IMPL.reservation_create(context, reservation_values)


@to_dict
def reservation_get_all_by_lease(context, lease_id):
    """Return all reservations belongs to specific lease"""
    return IMPL.reservation_get_all_by_lease(context, lease_id)


@to_dict
def reservation_get(context, reservation_id):
    """Return specific reservation"""
    return IMPL.reservation_get(context, reservation_id)


def reservation_destroy(context, reservation_id):
    """Delete specific reservation"""
    IMPL.reservation_destroy(context, reservation_id)


def reservation_update(context, reservation_id, reservation_values):
    """Update reservation"""
    IMPL.reservation_update(context, reservation_id, reservation_values)


#Lease

def lease_create(context, lease_values):
    """Create a lease from values"""
    return IMPL.lease_create(context, lease_values)


@to_dict
def lease_get_all(context):
    """Return all leases"""
    return IMPL.lease_get_all(context)


@to_dict
def lease_get_all_by_tenant(context, tenant_id):
    """Return all leases in specific tenant"""
    return IMPL.lease_get_all_by_tenant(context, tenant_id)


@to_dict
def lease_get_all_by_user(context, user_id):
    """Return all leases belongs to specific user"""
    return IMPL.lease_get_all_by_user(context, user_id)


@to_dict
def lease_get(context, lease_id):
    """Return lease"""
    return IMPL.lease_get(context, lease_id)


@to_dict
def lease_list(context):
    """Return a list of all existing leases"""
    return IMPL.lease_list(context)


def lease_destroy(context, lease_id):
    """Delete lease or raise if not exists"""
    IMPL.lease_destroy(context, lease_id)


def lease_update(context, lease_id, lease_values):
    """Update lease or raise if not exists"""
    IMPL.lease_update(context, lease_id, lease_values)


#Events

@to_dict
def event_create(context, event_values):
    """Create an event from values"""
    return IMPL.event_create(context, event_values)


@to_dict
def event_get_all(context):
    """Return all events"""
    return IMPL.event_get_all(context)


@to_dict
def event_get(context, event_id):
    """Return a specific event"""
    return IMPL.event_get(context, event_id)


@to_dict
def event_get_all_sorted_by_filters(context, sort_key, sort_dir, filters):
    """Return instances sorted by param"""
    return IMPL.event_get_all_sorted_by_filters(context, sort_key, sort_dir,
                                                filters)


@to_dict
def event_list(context, param):
    """Return a list of events"""
    return IMPL.event_list(context)


def event_destroy(context, event_id):
    """Delete event or raise if not exists"""
    IMPL.event_destroy(context, event_id)


def event_update(context, event_id, event_values):
    """Update event or raise if not exists"""
    IMPL.event_update(context, event_id, event_values)

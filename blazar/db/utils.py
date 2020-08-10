# -*- coding: utf-8 -*-
#
# Author: François Rossigneux <francois.rossigneux@inria.fr>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

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
from oslo_log import log as logging


_BACKEND_MAPPING = {
    'sqlalchemy': 'blazar.db.sqlalchemy.utils',
}

IMPL = db_api.DBAPI(cfg.CONF.database.backend,
                    backend_mapping=_BACKEND_MAPPING)
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


def get_reservations_by_host_id(host_id, start_date, end_date):
    return IMPL.get_reservations_by_host_id(host_id, start_date, end_date)


def get_reservations_by_host_ids(host_ids, start_date, end_date):
    return IMPL.get_reservations_by_host_ids(host_ids, start_date, end_date)


def get_reservation_allocations_by_host_ids(host_ids, start_date, end_date,
                                            lease_id=None,
                                            reservation_id=None):
    return IMPL.get_reservation_allocations_by_host_ids(host_ids,
                                                        start_date, end_date,
                                                        lease_id,
                                                        reservation_id)


def get_reservation_allocations_by_fip_ids(fip_ids, start_date, end_date,
                                           lease_id=None, reservation_id=None):
    return IMPL.get_reservation_allocations_by_fip_ids(
        fip_ids, start_date, end_date, lease_id, reservation_id)


def get_plugin_reservation(resource_type, resource_id):
    return IMPL.get_plugin_reservation(resource_type, resource_id)


def get_free_periods(resource_id, start_date, end_date, duration,
                     resource_type='host'):
    """Returns a list of free periods."""
    return IMPL.get_free_periods(resource_id, start_date, end_date, duration,
                                 resource_type=resource_type)


def get_reserved_periods(resource_id, start_date, end_date, duration,
                         resource_type='host'):
    """Returns a list of reserved periods."""
    return IMPL.get_reserved_periods(resource_id, start_date, end_date,
                                     duration, resource_type=resource_type)

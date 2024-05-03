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

"""Implementation of SQLAlchemy backend."""

import sys

from oslo_db import exception as common_db_exc
from oslo_log import log as logging
import sqlalchemy as sa
from sqlalchemy.sql.expression import asc
from sqlalchemy.sql.expression import desc

from blazar.db import exceptions as db_exc
from blazar.db.sqlalchemy import facade_wrapper
from blazar.db.sqlalchemy import models

RESOURCE_PROPERTY_MODELS = {
    'physical:host': models.ComputeHostExtraCapability,
}

LOG = logging.getLogger(__name__)


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def setup_db():
    try:
        with facade_wrapper.session_for_write(sqlite_fk=True) as session:
            engine = session.get_bind()
            models.Lease.metadata.create_all(engine)
        facade_wrapper._clear_engine()
    except sa.exc.OperationalError as e:
        LOG.error("Database registration exception: %s", e)
        raise
    return True


def drop_db():
    try:
        with facade_wrapper.session_for_write(sqlite_fk=True) as session:
            engine = session.get_bind()
            models.Lease.metadata.drop_all(engine)
        facade_wrapper._clear_engine()
    except Exception as e:
        LOG.error("Database shutdown exception: %s", e)
        raise
    return True


# Helpers for building constraints / equality checks


def constraint(**conditions):
    return Constraint(conditions)


def equal_any(*values):
    return EqualityCondition(values)


def not_equal(*values):
    return InequalityCondition(values)


class Constraint(object):
    def __init__(self, conditions):
        self.conditions = conditions

    def apply(self, model, query):
        for key, condition in self.conditions.items():
            for clause in condition.clauses(getattr(model, key)):
                query = query.filter(clause)
        return query


class EqualityCondition(object):
    def __init__(self, values):
        self.values = values

    def clauses(self, field):
        return sa.or_([field == value for value in self.values])


class InequalityCondition(object):
    def __init__(self, values):
        self.values = values

    def clauses(self, field):
        return [field != value for value in self.values]


# Reservation
def _reservation_get(session, reservation_id):
    query = session.query(models.Reservation)
    return query.filter_by(id=reservation_id).first()


def reservation_get(reservation_id):
    with facade_wrapper.session_for_read() as session:
        return _reservation_get(session, reservation_id)


def reservation_get_all():
    with facade_wrapper.session_for_read() as session:
        query = session.query(models.Reservation)
        return query.all()


def reservation_get_all_by_lease_id(lease_id):
    with facade_wrapper.session_for_read() as session:
        reservations = (session.query(models.Reservation
                                      ).filter_by(lease_id=lease_id))
        return reservations.all()


def reservation_get_all_by_values(**kwargs):
    """Returns all entries filtered by col=value."""
    with facade_wrapper.session_for_read() as session:
        reservation_query = session.query(models.Reservation)
        for name, value in kwargs.items():
            column = getattr(models.Reservation, name, None)
            if column:
                reservation_query = reservation_query.filter(column == value)
        return reservation_query.all()


def reservation_create(values):
    values = values.copy()
    reservation = models.Reservation()
    reservation.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            reservation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=reservation.__class__.__name__, columns=e.columns)

    return reservation_get(reservation.id)


def reservation_update(reservation_id, values):
    with facade_wrapper.session_for_write() as session:
        reservation = _reservation_get(session, reservation_id)
        reservation.update(values)
        reservation.save(session=session)

    return reservation_get(reservation_id)


def reservation_destroy(reservation_id):
    with facade_wrapper.session_for_write() as session:
        reservation = _reservation_get(session, reservation_id)

        if not reservation:
            # raise not found error
            raise db_exc.BlazarDBNotFound(id=reservation_id,
                                          model='Reservation')

        session.delete(reservation)


# Lease
def _lease_get(session, lease_id):
    query = session.query(models.Lease)
    return query.filter_by(id=lease_id).first()


def lease_get(lease_id):
    with facade_wrapper.session_for_read() as session:
        return _lease_get(session, lease_id)


def lease_get_all():
    with facade_wrapper.session_for_read() as session:
        query = session.query(models.Lease)
        return query.all()


def lease_get_all_by_project(project_id):
    raise NotImplementedError


def lease_get_all_by_user(user_id):
    raise NotImplementedError


def lease_list(project_id=None):
    with facade_wrapper.session_for_read() as session:
        query = session.query(models.Lease)
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        return query.all()


def lease_create(values):
    values = values.copy()
    lease = models.Lease()
    reservations = values.pop("reservations", [])
    events = values.pop("events", [])
    lease.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            lease.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=lease.__class__.__name__, columns=e.columns)

        try:
            for r in reservations:
                reservation = models.Reservation()
                reservation.update({"lease_id": lease.id})
                reservation.update(r)
                reservation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=reservation.__class__.__name__, columns=e.columns)

        try:
            for e in events:
                event = models.Event()
                event.update({"lease_id": lease.id})
                event.update(e)
                event.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=event.__class__.__name__, columns=e.columns)

    return lease_get(lease.id)


def lease_update(lease_id, values):
    with facade_wrapper.session_for_write() as session:
        lease = _lease_get(session, lease_id)
        lease.update(values)
        lease.save(session=session)

    return lease_get(lease_id)


def lease_destroy(lease_id):
    with facade_wrapper.session_for_write() as session:
        lease = _lease_get(session, lease_id)

        if not lease:
            # raise not found error
            raise db_exc.BlazarDBNotFound(id=lease_id, model='Lease')

        session.delete(lease)


# Event
def _event_get(session, event_id):
    query = session.query(models.Event)
    return query.filter_by(id=event_id).first()


def _event_get_all(session):
    query = session.query(models.Event)
    return query


def event_get(event_id):
    with facade_wrapper.session_for_read() as session:
        return _event_get(session, event_id)


def event_get_all():
    with facade_wrapper.session_for_read() as session:
        return _event_get_all(session).all()


def _event_get_sorted_by_filters(session, sort_key, sort_dir, filters):
    """Return an event query filtered and sorted by name of the field."""

    sort_fn = {'desc': desc, 'asc': asc}

    events_query = _event_get_all(session)

    if 'status' in filters:
        events_query = (
            events_query.filter(models.Event.status == filters['status']))
    if 'lease_id' in filters:
        events_query = (
            events_query.filter(models.Event.lease_id == filters['lease_id']))
    if 'event_type' in filters:
        events_query = events_query.filter(models.Event.event_type ==
                                           filters['event_type'])
    if 'time' in filters:
        border = filters['time']['border']
        if filters['time']['op'] == 'lt':
            events_query = events_query.filter(models.Event.time < border)
        elif filters['time']['op'] == 'le':
            events_query = events_query.filter(models.Event.time <= border)
        elif filters['time']['op'] == 'gt':
            events_query = events_query.filter(models.Event.time > border)
        elif filters['time']['op'] == 'ge':
            events_query = events_query.filter(models.Event.time >= border)
        elif filters['time']['op'] == 'eq':
            events_query = events_query.filter(models.Event.time == border)

    events_query = events_query.order_by(
        sort_fn[sort_dir](getattr(models.Event, sort_key))
    )

    return events_query


def event_get_first_sorted_by_filters(sort_key, sort_dir, filters):
    """Return first result for events

    Return the first result for all events matching the filters
    and sorted by name of the field.
    """
    with facade_wrapper.session_for_read() as session:
        return _event_get_sorted_by_filters(
            session, sort_key, sort_dir, filters).first()


def event_get_all_sorted_by_filters(sort_key, sort_dir, filters):
    """Return events filtered and sorted by name of the field."""
    with facade_wrapper.session_for_read() as session:
        return _event_get_sorted_by_filters(
            session, sort_key, sort_dir, filters).all()


def event_create(values):
    values = values.copy()
    event = models.Event()
    event.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            event.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=event.__class__.__name__, columns=e.columns)

    return event_get(event.id)


def event_update(event_id, values):
    with facade_wrapper.session_for_write() as session:
        event = _event_get(session, event_id)
        event.update(values)
        event.save(session=session)

    return event_get(event_id)


def event_destroy(event_id):
    with facade_wrapper.session_for_write() as session:
        event = _event_get(session, event_id)

        if not event:
            # raise not found error
            raise db_exc.BlazarDBNotFound(id=event_id, model='Event')

        session.delete(event)


# ComputeHostReservation
def _host_reservation_get(session, host_reservation_id):
    query = session.query(models.ComputeHostReservation)
    return query.filter_by(id=host_reservation_id).first()


def host_reservation_get(host_reservation_id):
    with facade_wrapper.session_for_read() as session:
        return _host_reservation_get(session, host_reservation_id)


def host_reservation_get_all():
    with facade_wrapper.session_for_read() as session:
        query = session.query(models.ComputeHostReservation)
        return query.all()


def _host_reservation_get_by_reservation_id(session, reservation_id):
    query = session.query(models.ComputeHostReservation)
    return query.filter_by(reservation_id=reservation_id).first()


def host_reservation_get_by_reservation_id(reservation_id):
    with facade_wrapper.session_for_read() as session:
        return _host_reservation_get_by_reservation_id(session, reservation_id)


def host_reservation_create(values):
    values = values.copy()
    host_reservation = models.ComputeHostReservation()
    host_reservation.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            host_reservation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=host_reservation.__class__.__name__, columns=e.columns)

    return host_reservation_get(host_reservation.id)


def host_reservation_update(host_reservation_id, values):
    with facade_wrapper.session_for_write() as session:
        host_reservation = _host_reservation_get(session, host_reservation_id)
        host_reservation.update(values)
        host_reservation.save(session=session)

    return host_reservation_get(host_reservation_id)


def host_reservation_destroy(host_reservation_id):
    with facade_wrapper.session_for_write() as session:
        host_reservation = _host_reservation_get(session, host_reservation_id)

        if not host_reservation:
            # raise not found error
            raise db_exc.BlazarDBNotFound(
                id=host_reservation_id, model='ComputeHostReservation')

        session.delete(host_reservation)


# InstanceReservation
def instance_reservation_create(values):
    value = values.copy()
    instance_reservation = models.InstanceReservations()
    instance_reservation.update(value)

    with facade_wrapper.session_for_write() as session:
        try:
            instance_reservation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=instance_reservation.__class__.__name__,
                columns=e.columns)

    return instance_reservation_get(instance_reservation.id)


def instance_reservation_get(instance_reservation_id, session=None):
    if not session:
        with facade_wrapper.session_for_read() as session:
            query = session.query(models.InstanceReservations)
            return query.filter_by(id=instance_reservation_id).first()
    query = session.query(models.InstanceReservations)
    return query.filter_by(id=instance_reservation_id).first()


def instance_reservation_update(instance_reservation_id, values):
    with facade_wrapper.session_for_write() as session:
        instance_reservation = instance_reservation_get(
            instance_reservation_id, session)

        if not instance_reservation:
            raise db_exc.BlazarDBNotFound(
                id=instance_reservation_id, model='InstanceReservations')

        instance_reservation.update(values)
        instance_reservation.save(session=session)

    return instance_reservation_get(instance_reservation_id)


def instance_reservation_destroy(instance_reservation_id):
    with facade_wrapper.session_for_write() as session:
        instance = instance_reservation_get(instance_reservation_id)

        if not instance:
            raise db_exc.BlazarDBNotFound(
                id=instance_reservation_id, model='InstanceReservations')
        session.delete(instance)


# ComputeHostAllocation
def _host_allocation_get(session, host_allocation_id):
    query = session.query(models.ComputeHostAllocation)
    return query.filter_by(id=host_allocation_id).first()


def host_allocation_get(host_allocation_id):
    with facade_wrapper.session_for_read() as session:
        return _host_allocation_get(session, host_allocation_id)


def host_allocation_get_all():
    with facade_wrapper.session_for_read() as session:
        query = session.query(models.ComputeHostAllocation)
        return query.all()


def host_allocation_get_all_by_values(**kwargs):
    """Returns all entries filtered by col=value."""
    with facade_wrapper.session_for_read() as session:
        allocation_query = session.query(models.ComputeHostAllocation)
        for name, value in kwargs.items():
            column = getattr(models.ComputeHostAllocation, name, None)
            if column:
                allocation_query = allocation_query.filter(column == value)
        return allocation_query.all()


def host_allocation_create(values):
    values = values.copy()
    host_allocation = models.ComputeHostAllocation()
    host_allocation.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            host_allocation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=host_allocation.__class__.__name__, columns=e.columns)

    return host_allocation_get(host_allocation.id)


def host_allocation_update(host_allocation_id, values):
    with facade_wrapper.session_for_write() as session:
        host_allocation = _host_allocation_get(session,
                                               host_allocation_id)
        host_allocation.update(values)
        host_allocation.save(session=session)

    return host_allocation_get(host_allocation_id)


def host_allocation_destroy(host_allocation_id):
    with facade_wrapper.session_for_write() as session:
        host_allocation = _host_allocation_get(session,
                                               host_allocation_id)

        if not host_allocation:
            # raise not found error
            raise db_exc.BlazarDBNotFound(
                id=host_allocation_id, model='ComputeHostAllocation')

        session.delete(host_allocation)


# ComputeHost
def _host_get(session, host_id):
    query = session.query(models.ComputeHost)
    return query.filter_by(id=host_id).first()


def _host_get_all(session):
    query = session.query(models.ComputeHost)
    return query


def host_get(host_id):
    with facade_wrapper.session_for_read() as session:
        return _host_get(session, host_id)


def host_list():
    with facade_wrapper.session_for_read() as session:
        return session.query(models.ComputeHost).all()


def host_get_all_by_filters(filters):
    """Returns hosts filtered by name of the field."""

    with facade_wrapper.session_for_read() as session:
        hosts_query = _host_get_all(session)

        if 'status' in filters:
            hosts_query = hosts_query.filter(
                models.ComputeHost.status == filters['status'])

        return hosts_query.all()


def host_get_all_by_queries(queries):
    """Returns hosts filtered by an array of queries.

    :param queries: array of queries "key op value" where op can be
        http://docs.sqlalchemy.org/en/rel_0_7/core/expression_api.html
            #sqlalchemy.sql.operators.ColumnOperators

    """
    with facade_wrapper.session_for_read() as session:
        hosts_query = session.query(models.ComputeHost)

        oper = {
            '<': ['lt', lambda a, b: a >= b],
            '>': ['gt', lambda a, b: a <= b],
            '<=': ['le', lambda a, b: a > b],
            '>=': ['ge', lambda a, b: a < b],
            '==': ['eq', lambda a, b: a != b],
            '!=': ['ne', lambda a, b: a == b],
        }

        hosts = []
        for query in queries:
            try:
                key, op, value = query.split(' ', 2)
            except ValueError:
                raise db_exc.BlazarDBInvalidFilter(query_filter=query)

            column = getattr(models.ComputeHost, key, None)
            if column is not None:
                if op == 'in':
                    filt = column.in_(value.split(','))
                else:
                    if op in oper:
                        op = oper[op][0]
                    try:
                        attr = [e for e in ['%s', '%s_', '__%s__']
                                if hasattr(column, e % op)][0] % op
                    except IndexError:
                        raise db_exc.BlazarDBInvalidFilterOperator(
                            filter_operator=op)

                    if value == 'null':
                        value = None

                    filt = getattr(column, attr)(value)

                hosts_query = hosts_query.filter(filt)
            else:
                # looking for resource properties matches
                extra_filter = (
                    _host_resource_property_query(session)
                    .filter(models.ResourceProperty.property_name == key)
                ).all()

                if not extra_filter:
                    raise db_exc.BlazarDBNotFound(
                        id=key, model='ComputeHostExtraCapability')

                for host, property_name in extra_filter:
                    print(dir(host))
                    if op in oper and oper[op][1](host.capability_value,
                                                  value):
                        hosts.append(host.computehost_id)
                    elif op not in oper:
                        msg = ('Operator %s for resource properties '
                               'not implemented')
                        raise NotImplementedError(msg % op)

                # We must also avoid selecting any host which doesn't have the
                # extra capability present.
                all_hosts = [h.id for h in hosts_query.all()]
                extra_filter_hosts = [h.computehost_id
                                      for h, _ in extra_filter]
                hosts += [h for h in all_hosts if h not in extra_filter_hosts]

        return hosts_query.filter(~models.ComputeHost.id.in_(hosts)).all()


def reservable_host_get_all_by_queries(queries):
    """Returns reservable hosts filtered by an array of queries.

    :param queries: array of queries "key op value" where op can be
        http://docs.sqlalchemy.org/en/rel_0_7/core/expression_api.html
            #sqlalchemy.sql.operators.ColumnOperators

    """
    queries.append('reservable == 1')
    return host_get_all_by_queries(queries)


def unreservable_host_get_all_by_queries(queries):
    """Returns unreservable hosts filtered by an array of queries.

    :param queries: array of queries "key op value" where op can be
        http://docs.sqlalchemy.org/en/rel_0_7/core/expression_api.html
            #sqlalchemy.sql.operators.ColumnOperators

    """

    # TODO(hiro-kobayashi): support the expression 'reservable == False'
    queries.append('reservable == 0')
    return host_get_all_by_queries(queries)


def host_create(values):
    values = values.copy()
    host = models.ComputeHost()
    host.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            host.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=host.__class__.__name__, columns=e.columns)

    return host_get(host.id)


def host_update(host_id, values):
    with facade_wrapper.session_for_write() as session:
        host = _host_get(session, host_id)
        host.update(values)
        host.save(session=session)

    return host_get(host_id)


def host_destroy(host_id):
    with facade_wrapper.session_for_write() as session:
        host = _host_get(session, host_id)

        if not host:
            # raise not found error
            raise db_exc.BlazarDBNotFound(id=host_id, model='Host')

        session.delete(host)


# ComputeHostExtraCapability

def _host_resource_property_query(session):
    return (
        session.query(models.ComputeHostExtraCapability)
        .join(models.ResourceProperty)
        .add_column(models.ResourceProperty.property_name))


def _host_extra_capability_get(session, host_extra_capability_id):
    query = _host_resource_property_query(session).filter(
        models.ComputeHostExtraCapability.id == host_extra_capability_id)

    return query.first()


def host_extra_capability_get(host_extra_capability_id):
    with facade_wrapper.session_for_read() as session:
        return _host_extra_capability_get(session, host_extra_capability_id)


def _host_extra_capability_get_all_per_host(session, host_id):
    query = _host_resource_property_query(session).filter(
        models.ComputeHostExtraCapability.computehost_id == host_id)

    return query


def host_extra_capability_get_all_per_host(host_id):
    with facade_wrapper.session_for_read() as session:
        return _host_extra_capability_get_all_per_host(session, host_id).all()


def host_extra_capability_create(values):
    values = values.copy()

    resource_property = resource_property_get_or_create(
        'physical:host', values.get('property_name'))

    del values['property_name']
    values['property_id'] = resource_property.id

    host_extra_capability = models.ComputeHostExtraCapability()
    host_extra_capability.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            host_extra_capability.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=host_extra_capability.__class__.__name__,
                columns=e.columns)

    return host_extra_capability_get(host_extra_capability.id)


def host_extra_capability_update(host_extra_capability_id, values):
    with facade_wrapper.session_for_write() as session:
        host_extra_capability, _ = (
            _host_extra_capability_get(session,
                                       host_extra_capability_id))
        host_extra_capability.update(values)
        host_extra_capability.save(session=session)

    return host_extra_capability_get(host_extra_capability_id)


def host_extra_capability_destroy(host_extra_capability_id):
    with facade_wrapper.session_for_write() as session:
        host_extra_capability = _host_extra_capability_get(
            session, host_extra_capability_id)

        if not host_extra_capability:
            # raise not found error
            raise db_exc.BlazarDBNotFound(
                id=host_extra_capability_id,
                model='ComputeHostExtraCapability')

        session.delete(host_extra_capability[0])


def host_extra_capability_get_all_per_name(host_id, property_name):
    with facade_wrapper.session_for_read() as session:
        query = _host_extra_capability_get_all_per_host(session, host_id)
        return query.filter(
            models.ResourceProperty.property_name == property_name).all()


# FloatingIP reservation

def fip_reservation_create(fip_reservation_values):
    values = fip_reservation_values.copy()
    fip_reservation = models.FloatingIPReservation()
    fip_reservation.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            fip_reservation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=fip_reservation.__class__.__name__, columns=e.columns)

    return fip_reservation_get(fip_reservation.id)


def _fip_reservation_get(session, fip_reservation_id):
    query = session.query(models.FloatingIPReservation)
    return query.filter_by(id=fip_reservation_id).first()


def fip_reservation_get(fip_reservation_id):
    with facade_wrapper.session_for_read() as session:
        return _fip_reservation_get(session, fip_reservation_id)


def fip_reservation_update(fip_reservation_id, fip_reservation_values):
    with facade_wrapper.session_for_write() as session:
        fip_reservation = _fip_reservation_get(session, fip_reservation_id)
        fip_reservation.update(fip_reservation_values)
        fip_reservation.save(session=session)

    return fip_reservation_get(fip_reservation_id)


def fip_reservation_destroy(fip_reservation_id):
    with facade_wrapper.session_for_write() as session:
        fip_reservation = _fip_reservation_get(session, fip_reservation_id)

        if not fip_reservation:
            # raise not found error
            raise db_exc.BlazarDBNotFound(
                id=fip_reservation_id, model='FloatingIPReservation')

        session.delete(fip_reservation)


# Required FIP

def required_fip_create(required_fip_values):
    values = required_fip_values.copy()
    required_fip = models.RequiredFloatingIP()
    required_fip.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            required_fip.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=required_fip.__class__.__name__, columns=e.columns)

    return required_fip_get(required_fip.id)


def _required_fip_get(session, required_fip_id):
    query = session.query(models.RequiredFloatingIP)
    return query.filter_by(id=required_fip_id).first()


def required_fip_get(required_fip_id):
    with facade_wrapper.session_for_read() as session:
        return _required_fip_get(session, required_fip_id)


def required_fip_update(required_fip_id, required_fip_values):
    with facade_wrapper.session_for_write() as session:
        required_fip = _required_fip_get(session, required_fip_id)
        required_fip.update(required_fip_values)
        required_fip.save(session=session)

    return required_fip_get(required_fip_id)


def required_fip_destroy(required_fip_id):
    with facade_wrapper.session_for_write() as session:
        required_fip = _required_fip_get(session, required_fip_id)

        if not required_fip:
            # raise not found error
            raise db_exc.BlazarDBNotFound(
                id=required_fip_id, model='RequiredFloatingIP')

        session.delete(required_fip)


def required_fip_destroy_by_fip_reservation_id(fip_reservation_id):
    with facade_wrapper.session_for_write() as session:
        required_fips = session.query(
            models.RequiredFloatingIP).filter_by(
            floatingip_reservation_id=fip_reservation_id)
        for required_fip in required_fips:
            required_fip_destroy(required_fip['id'])


# FloatingIP Allocation

def _fip_allocation_get(session, fip_allocation_id):
    query = session.query(models.FloatingIPAllocation)
    return query.filter_by(id=fip_allocation_id).first()


def fip_allocation_get(fip_allocation_id):
    with facade_wrapper.session_for_read() as session:
        return _fip_allocation_get(session, fip_allocation_id)


def fip_allocation_create(allocation_values):
    values = allocation_values.copy()
    fip_allocation = models.FloatingIPAllocation()
    fip_allocation.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            fip_allocation.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=fip_allocation.__class__.__name__, columns=e.columns)

    return fip_allocation_get(fip_allocation.id)


def fip_allocation_get_all_by_values(**kwargs):
    """Returns all entries filtered by col=value."""
    with facade_wrapper.session_for_read() as session:
        allocation_query = session.query(models.FloatingIPAllocation)
        for name, value in kwargs.items():
            column = getattr(models.FloatingIPAllocation, name, None)
            if column:
                allocation_query = allocation_query.filter(column == value)
        return allocation_query.all()


def fip_allocation_destroy(allocation_id):
    with facade_wrapper.session_for_write() as session:
        fip_allocation = _fip_allocation_get(session, allocation_id)

        if not fip_allocation:
            # raise not found error
            raise db_exc.BlazarDBNotFound(
                id=allocation_id, model='FloatingIPAllocation')

        session.delete(fip_allocation)


def fip_allocation_update(allocation_id, allocation_values):
    with facade_wrapper.session_for_write() as session:
        fip_allocation = _fip_allocation_get(session, allocation_id)
        fip_allocation.update(allocation_values)
        fip_allocation.save(session=session)

    return fip_allocation_get(allocation_id)


# Floating IP
def _floatingip_get(session, floatingip_id):
    query = session.query(models.FloatingIP)
    return query.filter_by(id=floatingip_id).first()


def _floatingip_get_all(session):
    query = session.query(models.FloatingIP)
    return query


def fip_get_all_by_queries(queries):
    """Returns Floating IPs filtered by an array of queries.

    :param queries: array of queries "key op value" where op can be
        http://docs.sqlalchemy.org/en/rel_0_7/core/expression_api.html
            #sqlalchemy.sql.operators.ColumnOperators

    """
    with facade_wrapper.session_for_read() as session:
        fips_query = session.query(models.FloatingIP)

    oper = {
        '<': ['lt', lambda a, b: a >= b],
        '>': ['gt', lambda a, b: a <= b],
        '<=': ['le', lambda a, b: a > b],
        '>=': ['ge', lambda a, b: a < b],
        '==': ['eq', lambda a, b: a != b],
        '!=': ['ne', lambda a, b: a == b],
    }

    for query in queries:
        try:
            key, op, value = query.split(' ', 2)
        except ValueError:
            raise db_exc.BlazarDBInvalidFilter(query_filter=query)

        column = getattr(models.FloatingIP, key, None)
        if column is not None:
            if op == 'in':
                filt = column.in_(value.split(','))
            else:
                if op in oper:
                    op = oper[op][0]
                try:
                    attr = [e for e in ['%s', '%s_', '__%s__']
                            if hasattr(column, e % op)][0] % op
                except IndexError:
                    raise db_exc.BlazarDBInvalidFilterOperator(
                        filter_operator=op)

                if value == 'null':
                    value = None

                filt = getattr(column, attr)(value)

            fips_query = fips_query.filter(filt)
        else:
            raise db_exc.BlazarDBInvalidFilter(query_filter=query)

    return fips_query.all()


def reservable_fip_get_all_by_queries(queries):
    """Returns reservable fips filtered by an array of queries.

    :param queries: array of queries "key op value" where op can be
        http://docs.sqlalchemy.org/en/rel_0_7/core/expression_api.html
            #sqlalchemy.sql.operators.ColumnOperators

    """
    queries.append('reservable == 1')
    return fip_get_all_by_queries(queries)


def floatingip_get(floatingip_id):
    with facade_wrapper.session_for_read() as session:
        return _floatingip_get(session, floatingip_id)


def floatingip_list():
    with facade_wrapper.session_for_read() as session:
        return session.query(models.FloatingIP).all()


def floatingip_create(values):
    values = values.copy()
    floatingip = models.FloatingIP()
    floatingip.update(values)

    with facade_wrapper.session_for_write() as session:
        try:
            floatingip.save(session=session)
        except common_db_exc.DBDuplicateEntry as e:
            # raise exception about duplicated columns (e.columns)
            raise db_exc.BlazarDBDuplicateEntry(
                model=floatingip.__class__.__name__, columns=e.columns)

    return floatingip_get(floatingip.id)


def floatingip_destroy(floatingip_id):
    with facade_wrapper.session_for_write() as session:
        floatingip = _floatingip_get(session, floatingip_id)

        if not floatingip:
            # raise not found error
            raise db_exc.BlazarDBNotFound(id=floatingip_id, model='FloatingIP')

        session.delete(floatingip)


# Resource Properties

def _resource_property_get(session, resource_type, property_name):
    query = (
        session.query(models.ResourceProperty)
        .filter_by(resource_type=resource_type)
        .filter_by(property_name=property_name))

    return query.first()


def resource_property_get(resource_type, property_name):
    with facade_wrapper.session_for_read() as session:
        return _resource_property_get(session, resource_type, property_name)


def resource_properties_list(resource_type):
    if resource_type not in RESOURCE_PROPERTY_MODELS:
        raise db_exc.BlazarDBResourcePropertiesNotEnabled(
            resource_type=resource_type)

    with facade_wrapper.session_for_read() as session:
        resource_model = RESOURCE_PROPERTY_MODELS[resource_type]
        query = session.query(
            models.ResourceProperty.property_name,
            models.ResourceProperty.private,
            resource_model.capability_value).join(resource_model).distinct()

        return query.all()


def _resource_property_create(session, values):
    values = values.copy()

    resource_property = models.ResourceProperty()
    resource_property.update(values)

    try:
        resource_property.save(session=session)
    except common_db_exc.DBDuplicateEntry as e:
        # raise exception about duplicated columns (e.columns)
        raise db_exc.BlazarDBDuplicateEntry(
            model=resource_property.__class__.__name__,
            columns=e.columns)

    return resource_property_get(values.get('resource_type'),
                                 values.get('property_name'))


def resource_property_create(values):
    with facade_wrapper.session_for_write() as session:
        return _resource_property_create(session, values)


def resource_property_update(resource_type, property_name, values):
    if resource_type not in RESOURCE_PROPERTY_MODELS:
        raise db_exc.BlazarDBResourcePropertiesNotEnabled(
            resource_type=resource_type)

    values = values.copy()
    with facade_wrapper.session_for_write() as session:
        resource_property = _resource_property_get(
            session, resource_type, property_name)

        if not resource_property:
            raise db_exc.BlazarDBInvalidResourceProperty(
                property_name=property_name,
                resource_type=resource_type)

        resource_property.update(values)
        resource_property.save(session=session)

    return resource_property_get(resource_type, property_name)


def _resource_property_get_or_create(session, resource_type, property_name):
    resource_property = _resource_property_get(
        session, resource_type, property_name)

    if resource_property:
        return resource_property
    else:
        rp_values = {
            'resource_type': resource_type,
            'property_name': property_name}

        return resource_property_create(rp_values)


def resource_property_get_or_create(resource_type, property_name):
    with facade_wrapper.session_for_write() as session:
        return _resource_property_get_or_create(
            session, resource_type, property_name)

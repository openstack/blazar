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

import datetime
import sys

import sqlalchemy as sa

from climate.db.sqlalchemy import models
from climate.openstack.common.db.sqlalchemy import session as db_session

get_session = db_session.get_session


def get_backend():
    """The backend is this module itself."""
    return sys.modules[__name__]


def _get_leases_from_resource_id(resource_id, start_date, end_date):
    session = get_session()
    for lease in session.query(models.Lease).\
        join(models.Reservation,
             models.Lease.id == models.Reservation.lease_id).\
        filter(models.Reservation.resource_id == resource_id).\
        filter(~sa.or_(sa.and_(models.Lease.start_date < start_date,
                               models.Lease.end_date < start_date),
                       sa.and_(models.Lease.start_date > end_date,
                               models.Lease.end_date > end_date))):
        yield lease


def _get_leases_from_host_id(host_id, start_date, end_date):
    session = get_session()
    for lease in session.query(models.Lease).\
        join(models.Reservation,
             models.Lease.id == models.Reservation.lease_id).\
        join(models.ComputeHostAllocation,
             models.Reservation.id ==
             models.ComputeHostAllocation.reservation_id).\
        filter(models.ComputeHostAllocation.compute_host_id == host_id).\
        filter(~sa.or_(sa.and_(models.Lease.start_date < start_date,
                               models.Lease.end_date < start_date),
                       sa.and_(models.Lease.start_date > end_date,
                               models.Lease.end_date > end_date))):
        yield lease


def get_free_periods(resource_id, start_date, end_date, duration):
    """Returns a list of free periods."""
    full_periods = get_full_periods(resource_id,
                                    start_date,
                                    end_date,
                                    duration)
    free_periods = []
    previous = (start_date, start_date)
    if len(full_periods) >= 1:
        for period in full_periods:
            free_periods.append((previous[1], period[0]))
            previous = period
        free_periods.append((previous[1], end_date))
        if free_periods[0][0] == free_periods[0][1]:
            del free_periods[0]
        if free_periods[-1][0] == free_periods[-1][1]:
            del free_periods[-1]
    elif start_date != end_date and start_date + duration <= end_date:
        free_periods.append((start_date, end_date))
    return free_periods


def _get_events(host_id, start_date, end_date):
    """Create a list of events."""
    events = {}
    for lease in _get_leases_from_host_id(host_id, start_date, end_date):
        if lease.start_date < start_date:
            min_date = start_date
        else:
            min_date = lease.start_date
        if lease.end_date > end_date:
            max_date = end_date
        else:
            max_date = lease.end_date
        if min_date in events.keys():
            events[min_date]['quantity'] += 1
        else:
            events[min_date] = {'quantity': 1}
        if max_date in events.keys():
            events[max_date]['quantity'] -= 1
        else:
            events[max_date] = {'quantity': -1}
    return events


def _find_full_periods(events, quantity, capacity):
    """Find the full periods."""
    full_periods = []
    used = 0
    full_start = None
    for event_date in sorted(events):
        used += events[event_date]['quantity']
        if not full_start and used + quantity > capacity:
            full_start = event_date
        elif full_start and used + quantity <= capacity:
            full_periods.append((full_start, event_date))
            full_start = None
    return full_periods


def _merge_periods(full_periods, start_date, end_date, duration):
    """Merge periods if the interval is too narrow."""
    full_start = None
    full_end = None
    previous = None
    merged_full_periods = []
    for period in full_periods:
        if not full_start:
            full_start = period[0]
        # Enough time between the two full periods
        if previous and period[0] - previous[1] >= duration:
            full_end = previous[1]
            merged_full_periods.append((full_start, full_end))
            full_start = period[0]
        full_end = period[1]
        previous = period
    if previous and end_date - previous[1] < duration:
        merged_full_periods.append((full_start, end_date))
    elif previous:
        merged_full_periods.append((full_start, previous[1]))
    if (len(merged_full_periods) >= 1 and
            merged_full_periods[0][0] - start_date < duration):
        merged_full_periods[0] = (start_date, merged_full_periods[0][1])
    return merged_full_periods


def get_full_periods(host_id, start_date, end_date, duration):
    """Returns a list of full periods."""
    capacity = 1  # The resource status is binary (empty or full)
    quantity = 1  # One reservation per host at the same time
    if end_date - start_date < duration:
        return [(start_date, end_date)]
    events = _get_events(host_id, start_date, end_date)
    full_periods = _find_full_periods(events, quantity, capacity)
    return _merge_periods(full_periods, start_date, end_date, duration)


def reservation_ratio(host_id, start_date, end_date):
    res_time = reservation_time(host_id, start_date, end_date).seconds
    return float(res_time) / (end_date - start_date).seconds


def availability_time(host_id, start_date, end_date):
    res_time = reservation_time(host_id, start_date, end_date)
    return end_date - start_date - res_time


def reservation_time(host_id, start_date, end_date):
    res_time = datetime.timedelta(0)
    for lease in _get_leases_from_host_id(host_id, start_date, end_date):
        res_time += lease.end_date - lease.start_date
        if lease.start_date < start_date:
            res_time -= start_date - lease.start_date
        if lease.end_date > end_date:
            res_time -= lease.end_date - end_date
    return res_time


def number_of_reservations(host_id, start_date, end_date):
    return sum(1 for x in
               _get_leases_from_host_id(host_id, start_date, end_date))


def longest_lease(host_id, start_date, end_date):
    max_duration = datetime.timedelta(0)
    longest_lease = None
    session = get_session()
    for lease in session.query(models.Lease).\
        join(models.Reservation,
             models.Lease.id == models.Reservation.lease_id).\
        join(models.ComputeHostAllocation,
             models.Reservation.id ==
             models.ComputeHostAllocation.reservation_id).\
            filter(models.ComputeHostAllocation.compute_host_id == host_id).\
            filter(models.Lease.start_date >= start_date).\
            filter(models.Lease.end_date <= end_date):
        duration = lease.end_date - lease.start_date
        if max_duration < duration:
            max_duration = duration
            longest_lease = lease.id
    return longest_lease


def shortest_lease(host_id, start_date, end_date):
    # TODO(frossigneux) Fix max timedelta
    min_duration = datetime.timedelta(365 * 1000)
    longest_lease = None
    session = get_session()
    for lease in session.query(models.Lease).\
        join(models.Reservation,
             models.Lease.id == models.Reservation.lease_id).\
        join(models.ComputeHostAllocation,
             models.Reservation.id ==
             models.ComputeHostAllocation.reservation_id).\
            filter(models.ComputeHostAllocation.compute_host_id == host_id).\
            filter(models.Lease.start_date >= start_date).\
            filter(models.Lease.end_date <= end_date):
        duration = lease.end_date - lease.start_date
        if min_duration > duration:
            min_duration = duration
            longest_lease = lease.id
    return longest_lease

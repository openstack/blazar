# Copyright (c) 2018 University of Chicago
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

import datetime

from oslo_config import cfg
from oslo_log import log as logging
import redis

from blazar import exceptions as common_ex
from blazar.manager import exceptions
from blazar.plugins.networks import billrate as network_billrate
from blazar.plugins.oshosts import billrate
from blazar.utils.openstack import keystone

enforcement_opts = [
    cfg.IntOpt('default_max_lease_duration',
               default=-1,
               help='Maximum lease duration in seconds. If this is set to -1, '
                    'there is not limit. For active leases being updated, the '
                    'limit applies between now and the new end date.'),
    cfg.ListOpt('project_max_lease_durations',
                default=[],
                help='Maximum lease durations overriding the default for '
                     'specific projects. Syntax is a comma-separated list of '
                     '<project_name>:<seconds> pairs.'),
    cfg.IntOpt('prolong_seconds_before_lease_end',
               default=48 * 3600,
               help='Number of seconds prior to lease end in which a user can '
                    'request to prolong their lease beyond the maximum lease '
                    'duration. If this is set to 0, then prolonging a lease '
                    'beyond the maximum lease duration is not allowed.'),
    cfg.BoolOpt('usage_enforcement',
                default=False,
                help='When enabled, Blazar enforces usage limits based on '
                     'allocations stored in a Redis database.'),
    cfg.StrOpt('usage_db_host',
               default='127.0.0.1',
               help='Hostname of the server hosting the usage DB. '
                    'It must be a hostname, FQDN, or IP address.'),
    cfg.FloatOpt('usage_default_allocated',
                 default=20000.0,
                 help='Default allocation if project is missing from usage '
                      'DB.')
]

CONF = cfg.CONF
CONF.register_opts(enforcement_opts, 'enforcement')
LOG = logging.getLogger(__name__)

BillingError = common_ex.NotAuthorized


def dt_hours(dt):
    return dt.total_seconds() / 3600.0


def isclose(a, b, rel_tol=1e-09, abs_tol=0.0):
    # math.isclose in Python 3.5+
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


class UsageEnforcer(object):
    def __init__(self):
        self.project_max_lease_durations = self._project_max_lease_durations()

        if CONF.enforcement.usage_enforcement:
            if not CONF.enforcement.usage_db_host:
                raise common_ex.ConfigurationError(
                    'usage_db_host must be set when using usage_enforcement')
        self.redis = redis.StrictRedis(host=CONF.enforcement.usage_db_host,
                                       port=6379, db=0)

    def _project_max_lease_durations(self):
        """Parses per-project maximum lease duration

        Parses the list of project:max_duration pairs provided for
        configuration parameter [enforcement]/project_max_lease_durations.
        """
        max_durations = {}
        max_durations_config = CONF.enforcement.project_max_lease_durations
        for kv in max_durations_config:
            try:
                project_name, seconds = kv.split(':')
                max_durations[project_name] = int(seconds)
            except ValueError:
                msg = "%s is not a valid project:max_duration pair" % kv
                raise exceptions.ConfigurationError(error=msg)
        return max_durations

    def initialize_project_allocation(self, project_name):
        try:
            allocated = self.redis.hget('allocated', project_name)
            if allocated is None:
                LOG.info('Setting project %s allocated to %f',
                         CONF.enforcement.usage_default_allocated)
                self.redis.hset('allocated', project_name,
                                CONF.enforcement.usage_default_allocated)
            balance = self.redis.hget('balance', project_name)
            if balance is None:
                LOG.info('Setting project %s balance to %f', project_name,
                         CONF.enforcement.usage_default_allocated)
                self.redis.hset('balance', project_name,
                                CONF.enforcement.usage_default_allocated)
            used = self.redis.hget('used', project_name)
            if used is None:
                self.redis.hset('used', project_name, 0.0)
            encumbered = self.redis.hget('encumbered', project_name)
            if encumbered is None:
                self.redis.hset('encumbered', project_name, 0.0)
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def get_lease_exception(self, user_name):
        try:
            lease_exception = self.redis.hget('user_exceptions', user_name)
            return lease_exception
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            return None

    def remove_lease_exception(self, user_name):
        LOG.info('Removing lease exception for user {}'.format(user_name))
        try:
            self.redis.hdel('user_exceptions', user_name)
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def setup_usage_enforcement(self, project_name):
        self.initialize_project_allocation(project_name)

    def check_lease_duration(self, lease_values, lease=None):
        """Verifies that lease duration is within enforcement limits

           This function checks:
           * one-time exception for user
           * project limit
           * default limit

           It takes into account the prolongation window set via
           [enforcement]/prolong_seconds_before_lease_end.

           Raises a NotAuthorized exception if lease duration is too long.
        """
        start_date = lease_values['start_date']
        end_date = lease_values['end_date']
        now = datetime.datetime.utcnow()
        now = datetime.datetime(now.year, now.month, now.day, now.hour,
                                now.minute)
        lease_duration = end_date - start_date

        user_name = self._get_user_name(lease_values['user_id'])
        project_name = self._get_project_name(lease_values['project_id'])

        if lease is not None:
            if lease['start_date'] < now and now < lease['end_date']:
                # Note: an updated end date doesn't necessarily mean that the
                # lease has been prolonged:
                # 1) the end date can be brought closer to now (reduced lease
                #    time)
                # 2) the end date can be moved together with the start date
                #    (lease is advanced/deferred)
                # If a lease has already started, the start date cannot be
                # moved, so 2) is not a problem.
                prolong_window = datetime.timedelta(
                    0, CONF.enforcement.prolong_seconds_before_lease_end, 0)
                prolong_allowed_from = lease['end_date'] - prolong_window
                if (now >= prolong_allowed_from):
                    lease_duration = end_date - now

        lease_duration = lease_duration.total_seconds()

        lease_exception = self.get_lease_exception(user_name)
        # A one-time lease exception can be set for the user
        if lease_exception is not None:
            lease_exception = int(lease_exception)
            if lease_duration > lease_exception:
                raise common_ex.NotAuthorized(
                    'Requested lease to last %d seconds, which is longer than '
                    'maximum allowed of %d seconds for user %s' %
                    (lease_exception, user_name))
        elif project_name in self.project_max_lease_durations:
            project_max_lease_duration = self.project_max_lease_durations.get(
                project_name)
            if project_max_lease_duration != -1:
                if (lease_duration) > project_max_lease_duration:
                    raise common_ex.NotAuthorized(
                        'Requested lease to last %d seconds, which is longer '
                        'than maximum allowed of %d seconds for project %s' %
                        (lease_duration, project_max_lease_duration,
                         project_name))
        elif CONF.enforcement.default_max_lease_duration != -1:
            if (lease_duration) > CONF.enforcement.default_max_lease_duration:
                raise common_ex.NotAuthorized(
                    'Lease is longer than maximum allowed of %d seconds' %
                    CONF.enforcement.default_max_lease_duration)

        return True

    def _get_user_name(self, user_id):
        """Get user name from Keystone"""
        self.keystone_client = keystone.BlazarKeystoneClient(
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            tenant_name=CONF.os_admin_project_name)
        user = self.keystone_client.users.get(user_id)
        return user.name

    def _get_project_name(self, project_id):
        """Get project name from Keystone"""
        self.keystone_client = keystone.BlazarKeystoneClient(
            username=CONF.os_admin_username,
            password=CONF.os_admin_password,
            tenant_name=CONF.os_admin_project_name)
        project = self.keystone_client.projects.get(project_id)
        return project.name

    def get_balance(self, project_name):
        try:
            return float(self.redis.hget('balance', project_name))
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def get_encumbered(self, project_name):
        try:
            return float(self.redis.hget('encumbered', project_name))
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def increase_encumbered(self, project_name, amount):
        try:
            self.redis.hincrbyfloat('encumbered', project_name, str(amount))
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def check_usage_against_allocation(self, lease_values,
                                       allocated_host_ids=None,
                                       allocated_network_ids=None):
        """Check if we have enough available SUs for this reservation

        Raises a BillingError if we don't have enough available SUs. If
        allocated_host_ids or allocated_network_ids is set and there are enough
        SUs, it increases the encumbered value in Redis.
        """
        if not CONF.enforcement.usage_enforcement:
            pass

        user_name = self._get_user_name(lease_values['user_id'])
        project_name = self._get_project_name(lease_values['project_id'])
        self.setup_usage_enforcement(project_name)

        if allocated_host_ids is not None:
            total_su_factor = sum(
                billrate.computehost_billrate(host_id)
                for host_id in allocated_host_ids)
        elif allocated_network_ids is not None:
            total_su_factor = sum(
                network_billrate.network_billrate(network_id)
                for network_id in allocated_network_ids)
        else:
            total_su_factor = lease_values['max']
        try:
            balance = self.get_balance(project_name)
            encumbered = self.get_encumbered(project_name)
            duration = lease_values['end_date'] - lease_values['start_date']
            requested = dt_hours(duration) * total_su_factor
            left = balance - encumbered
            if left - requested < 0:
                raise BillingError(
                    'Reservation for project {} would spend {:.2f} SUs, '
                    'only {:.2f} left'.format(project_name, requested, left))
            if allocated_host_ids or allocated_network_ids:
                LOG.info('Increasing encumbered for project {} by {:.2f} '
                         '({:.2f} hours @ {:.2f} SU/hr)'.format(
                             project_name, requested, dt_hours(duration),
                             total_su_factor))
                self.increase_encumbered(project_name, requested)
                LOG.info('Encumbered usage for project {} now {:.2f}'
                         .format(project_name,
                                 self.get_encumbered(project_name)))
                if self.get_lease_exception(user_name):
                    self.remove_lease_exception(user_name)
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def check_usage_against_allocation_pre_update(self, reservation_values,
                                                  lease, allocations):
        """Check if we have enough available SUs for update"""
        if not CONF.enforcement.usage_enforcement:
            pass

        project_name = self._get_project_name(lease['project_id'])
        self.setup_usage_enforcement(project_name)

        old_su_factor = self._total_billrate(allocations)
        try:
            balance = self.get_balance(project_name)
            encumbered = self.get_encumbered(project_name)
            old_duration = lease['end_date'] - lease['start_date']
            new_duration = (reservation_values['end_date'] -
                            reservation_values['start_date'])
            change = new_duration - old_duration
            estimated_requested = dt_hours(change) * old_su_factor
            left = balance - encumbered
            if left - estimated_requested < 0:
                raise BillingError(
                    'Reservation update would spend {:.2f} more SUs, only '
                    '{:.2f} left'.format(estimated_requested, left))
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)

    def check_usage_against_allocation_post_update(self, reservation_values,
                                                   lease, old_allocations,
                                                   new_allocations):
        """Check if we have enough available SUs for update"""
        if not CONF.enforcement.usage_enforcement:
            pass

        user_name = self._get_user_name(lease['user_id'])
        project_name = self._get_project_name(lease['project_id'])
        self.setup_usage_enforcement(project_name)

        old_su_factor = self._total_billrate(old_allocations)
        new_su_factor = self._total_billrate(new_allocations)

        balance = self.get_balance(project_name)
        encumbered = self.get_encumbered(project_name)
        left = balance - encumbered

        old_hours = dt_hours(lease['end_date'] - lease['start_date'])
        new_hours = dt_hours(
            reservation_values['end_date'] - reservation_values['start_date'])
        change_hours = new_hours - old_hours
        change_encumbered = (new_hours * new_su_factor -
                             old_hours * old_su_factor)
        if change_encumbered > left:
            raise BillingError('Reservation update would spend {:.2f} '
                               'more SUs, only {:.2f} left'.format(
                                   change_encumbered, left))
        LOG.info('Increasing encumbered for project {} by {:.2f} ({:.2f} '
                 'hours @ {:.2f} SU/hr)'.format(
                     project_name, change_encumbered, change_hours,
                     new_su_factor))

        try:
            self.redis.hincrbyfloat(
                'encumbered', project_name, str(change_encumbered))
            if self.get_lease_exception(user_name):
                self.remove_lease_exception(user_name)
        except redis.exceptions.ConnectionError:
            LOG.exception('Cannot connect to Redis host %s',
                          CONF.enforcement.usage_db_host)
            raise exceptions.RedisConnectionError(
                host=CONF.enforcement.usage_db_host)
        LOG.info('Encumbered usage for project {} now {:.2f}'
                 .format(project_name, self.get_encumbered(project_name)))

    def check_su_factor_identical(self, allocs, allocs_to_remove,
                                  ids_to_add):
        old_su_factor = self._total_billrate(allocs)

        new_su_factor = old_su_factor
        new_su_factor -= self._total_billrate(allocs_to_remove)
        new_su_factor += self._total_billrate(ids_to_add)

        if not isclose(new_su_factor, old_su_factor, rel_tol=1e-5):
            LOG.warning("SU factor changing from {} to {}"
                        .format(old_su_factor, new_su_factor))
            LOG.warning("Refusing factor change!")
            # TODO(priteau): easier for usage-reporting, but could probably
            # allow not-yet-started reservations to be modified without much
            # trouble.
            raise BillingError('Modifying a reservation that changes the SU '
                               'cost is prohibited')

    def release_encumbered(self, lease, reservation, allocations):
        if not CONF.enforcement.usage_enforcement:
            pass

        project_name = self._get_project_name(lease['project_id'])
        self.setup_usage_enforcement(project_name)

        total_su_factor = self._total_billrate(allocations)
        status = reservation['status']
        if status in ['pending', 'active']:
            old_duration = lease['end_date'] - lease['start_date']
            if status == 'pending':
                new_duration = datetime.timedelta(seconds=0)
            elif reservation['status'] == 'active':
                new_duration = (
                    datetime.datetime.utcnow() - lease['start_date'])
            change = new_duration - old_duration
            change_encumbered = dt_hours(change) * total_su_factor
            LOG.info('Decreasing encumbered for project {} by {:.2f} '
                     '({:.2f} hours @ {:.2f} SU/hr)'.format(
                         project_name, -change_encumbered,
                         dt_hours(change), total_su_factor))
            self.increase_encumbered(project_name, change_encumbered)
            LOG.info('Encumbered usage for project {} now {:.2f}'
                     .format(project_name,
                             self.get_encumbered(project_name)))

    def _total_billrate(self, allocations):
        if not allocations:
            return 0

        if 'compute_host_id' in allocations[0]:
            return sum(
                billrate.computehost_billrate(a['compute_host_id'])
                for a in allocations
            )
        elif 'network_id' in allocations[0]:
            return sum(
                network_billrate.network_billrate(a['network_id'])
                for a in allocations
            )
        else:
            raise Exception("Allocation list not in an expected format: %s",
                            allocations)

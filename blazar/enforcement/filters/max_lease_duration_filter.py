# Copyright (c) 2020 University of Chicago.
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

from blazar.enforcement import exceptions
from blazar.enforcement.filters import base_filter

from oslo_config import cfg
from oslo_log import log as logging


DEFAULT_MAX_LEASE_DURATION = -1


LOG = logging.getLogger(__name__)


class MaxLeaseDurationFilter(base_filter.BaseFilter):

    enforcement_opts = [
        cfg.IntOpt(
            'max_lease_duration',
            default=DEFAULT_MAX_LEASE_DURATION,
            help='Maximum lease duration in seconds. If this is set to -1, '
                 'there is not limit.'),
        cfg.ListOpt(
            'max_lease_duration_exempt_project_ids',
            default=[],
            help='Allow list of project ids exempt from filter constraints.'),
    ]

    def __init__(self, conf=None):
        super(MaxLeaseDurationFilter, self).__init__(conf=conf)

    def _exempt(self, context):
        return (context['project_id'] in
                self.conf.enforcement.max_lease_duration_exempt_project_ids)

    def check_for_duration_violation(self, start_date, end_date):
        if self.conf.enforcement.max_lease_duration == -1:
            return

        lease_duration = (end_date - start_date).total_seconds()

        if lease_duration > self.conf.enforcement.max_lease_duration:
            raise exceptions.MaxLeaseDurationException(
                lease_duration=int(lease_duration),
                max_duration=self.conf.enforcement.max_lease_duration)

    def check_create(self, context, lease_values):
        if self._exempt(context):
            return

        start_date = lease_values['start_date']
        end_date = lease_values['end_date']

        self.check_for_duration_violation(start_date, end_date)

    def check_update(self, context, current_lease_values, new_lease_values):
        if self._exempt(context):
            return

        start_date = new_lease_values['start_date']
        end_date = new_lease_values['end_date']

        self.check_for_duration_violation(start_date, end_date)

    def on_end(self, context, lease_values):
        pass

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

from blazar.enforcement import filters
from blazar.utils.openstack import base

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF

enforcement_opts = [
    cfg.ListOpt('enabled_filters',
                default=[],
                help='List of enabled usage enforcement filters.'),
]

CONF.register_opts(enforcement_opts, group='enforcement')
LOG = logging.getLogger(__name__)


class UsageEnforcement:

    def __init__(self):
        self.load_filters()

    def load_filters(self):
        self.enabled_filters = set()
        for filter_name in CONF.enforcement.enabled_filters:
            _filter = getattr(filters, filter_name)

            if filter_name in filters.all_filters:
                self.enabled_filters.add(_filter(conf=CONF))
            else:
                LOG.error("{} not in filters module.".format(filter_name))

        self.enabled_filters = list(self.enabled_filters)

    def format_context(self, context, lease_values):
        ctx = context.to_dict()
        region_name = CONF.os_region_name
        auth_url = base.url_for(
            ctx['service_catalog'], CONF.identity_service,
            os_region_name=region_name)

        return dict(user_id=lease_values['user_id'],
                    project_id=lease_values['project_id'],
                    auth_url=auth_url, region_name=region_name)

    def format_lease(self, lease_values, reservations, allocations):
        lease = lease_values.copy()
        lease['reservations'] = []

        for reservation in reservations:
            res = reservation.copy()
            resource_type = res['resource_type']
            res['allocations'] = allocations[resource_type]
            lease['reservations'].append(res)

        return lease

    def check_create(self, context, lease_values, reservations, allocations):
        context = self.format_context(context, lease_values)
        lease = self.format_lease(lease_values, reservations, allocations)

        for _filter in self.enabled_filters:
            _filter.check_create(context, lease)

    def check_update(self, context, current_lease, new_lease,
                     current_allocations, new_allocations,
                     current_reservations, new_reservations):
        context = self.format_context(context, current_lease)
        current_lease = self.format_lease(current_lease, current_reservations,
                                          current_allocations)
        new_lease = self.format_lease(new_lease, new_reservations,
                                      new_allocations)

        for _filter in self.enabled_filters:
            _filter.check_update(context, current_lease, new_lease)

    def on_end(self, context, lease, allocations):
        context = self.format_context(context, lease)
        lease_values = self.format_lease(lease, lease['reservations'],
                                         allocations)

        for _filter in self.enabled_filters:
            _filter.on_end(context, lease_values)

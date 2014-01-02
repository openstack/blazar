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

import abc

from oslo.config import cfg

from climate.db import api as db_api
from climate.openstack.common import log as logging

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class BasePlugin(object):
    __metaclass__ = abc.ABCMeta

    resource_type = 'none'
    title = None
    description = None

    def get_plugin_opts(self):
        """Plugin can expose some options that should be specified in conf file

        For example:

            def get_plugin_opts(self):
            return [
                cfg.StrOpt('mandatory-conf', required=True),
                cfg.StrOpt('optional_conf', default="42"),
            ]
        """
        return []

    def setup(self, conf):
        """Plugin initialization

        :param conf: plugin-specific configurations
        """
        pass

    def to_dict(self):
        return {
            'resource_type': self.resource_type,
            'title': self.title,
            'description': self.description,
        }

    def create_reservation(self, values):
        """Create reservation."""
        reservation_values = {
            'lease_id': values['lease_id'],
            'resource_id': values['resource_id'],
            'resource_type': values['resource_type'],
            'status': 'pending'
        }
        db_api.reservation_create(reservation_values)

    @abc.abstractmethod
    def on_end(self, resource_id):
        """Delete resource."""
        pass

    @abc.abstractmethod
    def on_start(self, resource_id):
        """Wake up resource."""
        pass

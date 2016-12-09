# Copyright 2014 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg
from tempest import config


service_available_group = cfg.OptGroup(name="service_available",
                                       title="Available OpenStack Services")

ServiceAvailableGroup = [
    cfg.BoolOpt("climate",
                default=True,
                help="Whether or not climate is expected to be available. "
                     "This config remains for backward compatibility."),
    cfg.BoolOpt("blazar",
                default=True,
                help="Whether or not blazar is expected to be available"),
]

resource_reservation_group = cfg.OptGroup(name='resource_reservation',
                                          title='Resource reservation service '
                                                'options')

ResourceReservationGroup = [
    cfg.StrOpt('endpoint_type',
               default='publicURL',
               choices=['public', 'admin', 'internal',
                        'publicURL', 'adminURL', 'internalURL'],
               help="The endpoint type to use for the resource_reservation "
                    "service."),
    cfg.IntOpt('lease_interval',
               default=10,
               help="Time in seconds between lease status checks."),
    cfg.IntOpt('lease_end_timeout',
               default=300,
               help="Timeout in seconds to wait for a lease to finish.")
]


class TempestConfigPrivateClimate(config.TempestConfigPrivate):
    """Climate's config wrap over standard config."""

    def __init__(self, parse_conf=True):
        config.register_opt_group(cfg.CONF, service_available_group,
                                  ServiceAvailableGroup)
        config.register_opt_group(cfg.CONF, resource_reservation_group,
                                  ResourceReservationGroup)
        self.resource_reservation = cfg.CONF.resource_reservation


class TempestClimateLazyConfig(object):
    _config = None

    def __getattr__(self, attr):
        if not self._config:
            self._config = TempestConfigPrivateClimate()

        return getattr(self._config, attr)


CONF = TempestClimateLazyConfig()

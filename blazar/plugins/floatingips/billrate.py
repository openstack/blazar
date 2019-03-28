# Copyright (c) 2019 StackHPC
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

from oslo_config import cfg

from blazar.plugins import floatingips as plugin

CONF = cfg.CONF


def floatingip_billrate(floatingip_id):
    """Return bill rate for a floating IP.

    All floating IPs have a common billrate since they do not have extra
    capabilities. If needed, we could make the billrate different based on the
    network_id.
    """
    return float(CONF[plugin.RESOURCE_TYPE].billrate)

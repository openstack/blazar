# Copyright (c) 2014 Bull.
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

from oslo_config import cfg
from oslo_log import log as logging
from pecan import rest

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class BaseController(rest.RestController, metaclass=abc.ABCMeta):

    """Mandatory API method name."""
    name = None

    """Optional extra routes to add.
    Dict of key/value pairs, where :
        key : API method name redirect (public URL)
        value : redirect target (can be None for routing to HTTP 404)
    """
    extra_routes = {}

    @abc.abstractmethod
    def get_one(self, resource_id):
        """Get a single resource."""
        pass

    @abc.abstractmethod
    def get_all(self):
        """Get all resources."""
        pass

    @abc.abstractmethod
    def post(self, resource):
        """Create a resource."""
        pass

    @abc.abstractmethod
    def put(self, resource):
        """Update a resource."""
        pass

    @abc.abstractmethod
    def delete(self, resource_id):
        """Delete a single resource."""
        pass

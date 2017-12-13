# Copyright 2017 NTT
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

import json

from tempest.lib.common import rest_client


class ResourceReservationV1Client(rest_client.RestClient):
    """Client class for accessing the resource reservation API."""
    CLIMATECLIENT_VERSION = '1'

    lease = '/leases'
    lease_path = '/leases/%s'
    host = '/os-hosts'
    host_path = '/os-hosts/%s'

    def _response_helper(self, resp, body=None):
        if body:
            body = json.loads(body)
        return rest_client.ResponseBody(resp, body)

    def list_lease(self):
        resp, body = self.get(self.lease)
        return self._response_helper(resp, body)

    def get_lease(self, lease):
        resp, body = self.get(self.lease_path % lease)
        return self._response_helper(resp, body)

    def create_lease(self, body):
        body = json.dumps(body)
        resp, body = self.post(self.lease, body=body)
        return self._response_helper(resp, body)

    def update_lease(self, lease, body):
        body = json.dumps(body)
        resp, body = self.put(self.lease_path % lease, body=body)
        return self._response_helper(resp, body)

    def delete_lease(self, lease):
        resp, body = self.delete(self.lease_path % lease)
        return self._response_helper(resp, body)

    def list_host(self):
        resp, body = self.get(self.host)
        return self._response_helper(resp, body)

    def get_host(self, host):
        resp, body = self.get(self.host_path % host)
        return self._response_helper(resp, body)

    def create_host(self, body):
        body = json.dumps(body)
        resp, body = self.post(self.host, body=body)
        return self._response_helper(resp, body)

    def update_host(self, host, body):
        body = json.dumps(body)
        resp, body = self.put(self.host_path % host, body=body)
        return self._response_helper(resp, body)

    def delete_host(self, host):
        resp, body = self.delete(self.host_path % host)
        return self._response_helper(resp, body)

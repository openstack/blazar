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

from keystoneauth1 import adapter
from keystoneauth1.identity import v3
from keystoneauth1 import session

from oslo_config import cfg
from oslo_log import log as logging

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

PLACEMENT_MICROVERSION = 1.29


class BlazarPlacementClient(object):
    """Client class for updating placement."""

    def __init__(self, **kwargs):
        """Initialize the report client.

        If a prepared keystoneauth1 adapter for API communication is
        specified, it is used.

        Otherwise creates it via _create_client() function.
        """
        adapter = kwargs.pop('adapter', None)
        self._client = adapter or self._create_client(**kwargs)

    def _create_client(self, **kwargs):
        """Create the HTTP session accessing the placement service."""
        username = kwargs.pop('username',
                              CONF.os_admin_username)
        user_domain_name = kwargs.pop('user_domain_name',
                                      CONF.os_admin_user_domain_name)
        project_name = kwargs.pop('project_name',
                                  CONF.os_admin_project_name)
        password = kwargs.pop('password',
                              CONF.os_admin_password)

        project_domain_name = kwargs.pop('project_domain_name',
                                         CONF.os_admin_project_domain_name)
        auth_url = kwargs.pop('auth_url', None)

        if auth_url is None:
            auth_url = "%s://%s:%s/%s/%s" % (CONF.os_auth_protocol,
                                             CONF.os_auth_host,
                                             CONF.os_auth_port,
                                             CONF.os_auth_prefix,
                                             CONF.os_auth_version)

        auth = v3.Password(auth_url=auth_url,
                           username=username,
                           password=password,
                           project_name=project_name,
                           user_domain_name=user_domain_name,
                           project_domain_name=project_domain_name)
        sess = session.Session(auth=auth)
        # Set accept header on every request to ensure we notify placement
        # service of our response body media type preferences.
        headers = {'accept': 'application/json'}
        client = adapter.Adapter(session=sess,
                                 service_type='placement',
                                 interface='public',
                                 additional_headers=headers)
        return client

    def get(self, url, microversion=PLACEMENT_MICROVERSION):
        return self._client.get(url, raise_exc=False,
                                microversion=microversion)

    def post(self, url, data, microversion=PLACEMENT_MICROVERSION):
        return self._client.post(url, json=data, raise_exc=False,
                                 microversion=microversion)

    def put(self, url, data, microversion=PLACEMENT_MICROVERSION):
        return self._client.put(url, json=data, raise_exc=False,
                                microversion=microversion)

    def delete(self, url, microversion=PLACEMENT_MICROVERSION):
        return self._client.delete(url, raise_exc=False,
                                   microversion=microversion)

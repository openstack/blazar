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

from blazar.utils.openstack import exceptions

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

    def get_resource_provider(self, rp_name):
        """Calls the placement API for a resource provider record.

        :param rp_name: Name of the resource provider
        :return: A dict of resource provider information.
        :raise: ResourceProviderRetrievalFailed on error.
        """
        url = "/resource_providers?name=%s" % rp_name
        resp = self.get(url)
        if resp:
            json_resp = resp.json()
            return json_resp['resource_providers'][0]

        msg = ("Failed to get resource provider %(name)s. "
               "Got %(status_code)d: %(err_text)s.")
        args = {
            'name': rp_name,
            'status_code': resp.status_code,
            'err_text': resp.text,
        }
        LOG.error(msg, args)
        raise exceptions.ResourceProviderRetrievalFailed(name=rp_name)

    def create_resource_provider(self, rp_name, rp_uuid=None,
                                 parent_uuid=None):
        """Calls the placement API to create a new resource provider record.

        :param rp_name: Name of the resource provider
        :param rp_uuid: Optional UUID of the new resource provider
        :param parent_uuid: Optional UUID of the parent resource provider
        :return: A dict of resource provider information object representing
                 the newly-created resource provider.
        :raise: ResourceProviderCreationFailed error.
        """
        url = "/resource_providers"
        payload = {'name': rp_name}
        if rp_uuid is not None:
            payload['uuid'] = rp_uuid
        if parent_uuid is not None:
            payload['parent_provider_uuid'] = parent_uuid

        resp = self.post(url, payload)

        if resp:
            msg = ("Created resource provider record via placement API for "
                   "resource provider %(name)s.")
            args = {'name': rp_name}
            LOG.info(msg, args)
            return resp.json()

        msg = ("Failed to create resource provider record in placement API "
               "for resource provider %(name)s. "
               "Got %(status_code)d: %(err_text)s.")
        args = {
            'name': rp_name,
            'status_code': resp.status_code,
            'err_text': resp.text,
        }
        LOG.error(msg, args)
        raise exceptions.ResourceProviderCreationFailed(name=rp_name)

    def delete_resource_provider(self, rp_uuid):
        """Calls the placement API to delete a resource provider.

        :param rp_uuid: UUID of the resource provider to delete
        :raise: ResourceProviderDeletionFailed error
        """
        url = '/resource_providers/%s' % rp_uuid
        resp = self.delete(url)

        if resp:
            LOG.info("Deleted resource provider %s", rp_uuid)
            return

        msg = ("Failed to delete resource provider with UUID %(uuid)s from "
               "the placement API. Got %(status_code)d: %(err_text)s.")
        args = {
            'uuid': rp_uuid,
            'status_code': resp.status_code,
            'err_text': resp.text
        }
        LOG.error(msg, args)
        raise exceptions.ResourceProviderDeletionFailed(uuid=rp_uuid)

    def create_reservation_provider(self, host_name):
        """Create a reservation provider as a child of the given host"""
        host_rp = self.get_resource_provider(host_name)
        host_uuid = host_rp['uuid']
        rp_name = "blazar_" + host_name

        reservation_rp = self.create_resource_provider(
            rp_name, parent_uuid=host_uuid)
        return reservation_rp

    def delete_reservation_provider(self, host_name):
        """Delete the reservation provider, the child of the given host"""
        rp_name = "blazar_" + host_name
        rp = self.get_resource_provider(rp_name)
        rp_uuid = rp['uuid']
        self.delete_resource_provider(rp_uuid)

    def create_resource_class(self, rc_name):
        """Calls the placement API to create a resource class.

        :param rc_name: string name of the resource class to create. This
                        shall be something like "CUSTOM_RESERVATION_{uuid}".
        :raises: ResourceClassCreationFailed error.
        """
        url = '/resource_classes'
        payload = {'name': rc_name}
        resp = self.post(url, payload)
        if resp:
            LOG.info("Created resource class %s", rc_name)
            return
        msg = ("Failed to create resource class with placement API for "
               "%(rc_name)s. Got %(status_code)d: %(err_text)s.")
        args = {
            'rc_name': rc_name,
            'status_code': resp.status_code,
            'err_text': resp.text,
        }
        LOG.error(msg, args)
        raise exceptions.ResourceClassCreationFailed(resource_class=rc_name)

    def delete_resource_class(self, rc_name):
        """Calls the placement API to delete a resource class.

        :param rc_name: string name of the resource class to delete. This
                        shall be something like "CUSTOM_RESERVATION_{uuid}"
        :raises: ResourceClassDeletionFailed error.
        """
        url = '/resource_classes/%s' % rc_name
        resp = self.delete(url)
        if resp:
            LOG.info("Deleted resource class %s", rc_name)
            return
        msg = ("Failed to delete resource class with placement API for "
               "%(rc_name)s. Got %(status_code)d: %(err_text)s.")
        args = {
            'rc_name': rc_name,
            'status_code': resp.status_code,
            'err_text': resp.text,
        }
        LOG.error(msg, args)
        raise exceptions.ResourceClassDeletionFailed(resource_class=rc_name)

    def create_reservation_class(self, reservation_uuid):
        """Create the reservation class from the given reservation uuid"""
        # Placement API doesn't accept resource classes with lower characters
        # and "-"(hyphen) in its name. We should translate the uuid here.
        reservation_uuid = reservation_uuid.upper().replace("-", "_")
        rc_name = 'CUSTOM_RESERVATION_' + reservation_uuid
        self.create_resource_class(rc_name)

    def delete_reservation_class(self, reservation_uuid):
        """Delete the reservation class from the given reservation uuid"""
        # Placement API doesn't accept resource classes with lower characters
        # and "-"(hyphen) in its name. We should translate the uuid here.
        reservation_uuid = reservation_uuid.upper().replace("-", "_")
        rc_name = 'CUSTOM_RESERVATION_' + reservation_uuid
        self.delete_resource_class(rc_name)

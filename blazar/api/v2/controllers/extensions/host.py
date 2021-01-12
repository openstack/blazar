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

from oslo_log import log as logging
import pecan
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from blazar.api.v2.controllers import base
from blazar.api.v2.controllers import extensions
from blazar.api.v2.controllers import types
from blazar import exceptions
from blazar.i18n import _
from blazar import policy
from blazar.utils import trusts

LOG = logging.getLogger(__name__)


class Host(base._Base):

    id = types.IntegerType()
    "The ID of the host"

    hypervisor_hostname = wtypes.text
    "The hostname of the host"

    # FIXME(sbauza): API V1 provides 'name', so mapping is necessary until we
    #                patch the client
    name = hypervisor_hostname

    hypervisor_type = wtypes.text
    "The type of the hypervisor"

    vcpus = types.IntegerType()
    "The number of VCPUs of the host"

    hypervisor_version = types.IntegerType()
    "The version of the hypervisor"

    memory_mb = types.IntegerType()
    "The memory size (in Mb) of the host"

    local_gb = types.IntegerType()
    "The disk size (in Gb) of the host"

    cpu_info = types.CPUInfo()
    "The CPU info JSON data given by the hypervisor"

    trust_id = types.UuidType()
    "The ID of the trust created for delegating the rights of the user"

    extra_capas = wtypes.DictType(wtypes.text, types.TextOrInteger())
    "Extra capabilities for the host"

    @classmethod
    def convert(cls, rpc_obj):
        extra_keys = [key for key in rpc_obj
                      if key not in
                      [i.key for i in wtypes.list_attributes(Host)]]
        extra_capas = dict((capa, rpc_obj[capa])
                           for capa in extra_keys if capa not in ['status'])
        rpc_obj['extra_capas'] = extra_capas
        obj = cls(**rpc_obj)
        return obj

    def as_dict(self):
        dct = super(Host, self).as_dict()
        extra_capas = dct.pop('extra_capas', None)
        if extra_capas is not None:
            dct.update(extra_capas)
        return dct

    @classmethod
    def sample(cls):
        return cls(id='1',
                   hypervisor_hostname='host01',
                   hypervisor_type='QEMU',
                   vcpus=1,
                   hypervisor_version=1000000,
                   memory_mb=8192,
                   local_gb=50,
                   cpu_info="{\"vendor\": \"Intel\", \"model\": \"qemu32\", "
                            "\"arch\": \"x86_64\", \"features\": [],"
                            " \"topology\": {\"cores\": 1}}",
                   extra_capas={'vgpus': 2, 'fruits': 'bananas'},
                   )


class HostsController(extensions.BaseController):
    """Manages operations on hosts."""

    name = 'oshosts'
    extra_routes = {'os-hosts': 'oshosts',
                    'oshosts': None}

    @policy.authorize('oshosts', 'get')
    @wsme_pecan.wsexpose(Host, types.IntegerType())
    def get_one(self, id):
        """Returns the host having this specific uuid

        :param id: ID of host
        """
        host_dct = pecan.request.hosts_rpcapi.get_computehost(id)
        if host_dct is None:
            raise exceptions.NotFound(object={'host_id': id})
        return Host.convert(host_dct)

    @policy.authorize('oshosts', 'get')
    @wsme_pecan.wsexpose([Host], q=[])
    def get_all(self):
        """Returns all hosts."""
        return [Host.convert(host)
                for host in
                pecan.request.hosts_rpcapi.list_computehosts()]

    @policy.authorize('oshosts', 'post')
    @wsme_pecan.wsexpose(Host, body=Host, status_code=201)
    @trusts.use_trust_auth()
    def post(self, host):
        """Creates a new host.

        :param host: a host within the request body.
        """
        # here API should go to Keystone API v3 and create trust
        host_dct = host.as_dict()
        # FIXME(sbauza): DB exceptions are currently catched and return a lease
        #                equal to None instead of being sent to the API
        host = pecan.request.hosts_rpcapi.create_computehost(host_dct)
        if host is not None:
            return Host.convert(host)
        else:
            raise exceptions.BlazarException(_("Host can't be created"))

    @policy.authorize('oshosts', 'put')
    @wsme_pecan.wsexpose(Host, types.IntegerType(), body=Host)
    def put(self, id, host):
        """Update an existing host.

        :param id: ID of a host.
        :param host: a subset of a Host containing values to update.
        """
        host_dct = host.as_dict()
        host = pecan.request.hosts_rpcapi.update_computehost(id, host_dct)

        if host is None:
            raise exceptions.NotFound(object={'host_id': id})
        return Host.convert(host)

    @policy.authorize('oshosts', 'delete')
    # NOTE(sbauza): We need to expose text for parameter type as Manager is
    #               expecting it and int raises an AttributeError
    @wsme_pecan.wsexpose(None, wtypes.text,
                         status_code=204)
    def delete(self, id):
        """Delete an existing host.

        :param id: UUID of a host.
        """
        try:
            pecan.request.hosts_rpcapi.delete_computehost(id)
        except TypeError:
            # The host was not existing when asking to delete it
            raise exceptions.NotFound(object={'host_id': id})

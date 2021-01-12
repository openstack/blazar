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

import pecan
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from blazar.api.v2.controllers import base
from blazar.api.v2.controllers import extensions
from blazar.api.v2.controllers import types
from blazar import exceptions
from blazar.i18n import _
from blazar.manager import service
from blazar import policy
from blazar.utils import trusts


class Lease(base._Base):

    id = types.UuidType()
    "The UUID of the lease"

    name = wtypes.text
    "The name of the lease"

    start_date = types.Datetime(service.LEASE_DATE_FORMAT)
    "Datetime when the lease should start"

    end_date = types.Datetime(service.LEASE_DATE_FORMAT)
    "Datetime when the lease should end"

    user_id = types.UuidType(without_dashes=True)
    "The ID of the user who creates the lease"

    project_id = types.UuidType(without_dashes=True)
    "The ID of the project or tenant the lease belongs to"

    trust_id = types.UuidType(without_dashes=True)
    "The ID of the trust created for delegating the rights of the user"

    reservations = wtypes.ArrayType(wtypes.DictType(wtypes.text, wtypes.text))
    "The list of reservations belonging to the lease"

    events = wtypes.ArrayType(wtypes.DictType(wtypes.text, wtypes.text))
    "The list of events attached to the lease"

    before_end_date = types.Datetime(service.LEASE_DATE_FORMAT)
    "Datetime when some actions will be taken before lease ending"

    status = wtypes.text
    "The status of the lease"

    @classmethod
    def sample(cls):
        return cls(id='2bb8720a-0873-4d97-babf-0d906851a1eb',
                   name='lease_test',
                   start_date='2014-01-01 01:23',
                   end_date='2014-02-01 13:37',
                   user_id='efd8780712d24b389c705f5c2ac427ff',
                   project_id='bd9431c18d694ad3803a8d4a6b89fd36',
                   trust_id='35b17138b3644e6aa1318f3099c5be68',
                   reservations=[{'resource_id': '1234',
                                  'resource_type': 'physical:host'}],
                   events=[],
                   before_end_date='2014-02-01 10:37',
                   status='ACTIVE',
                   )


class LeasesController(extensions.BaseController):
    """Manages operations on leases."""

    name = 'leases'

    @policy.authorize('leases', 'get')
    @wsme_pecan.wsexpose(Lease, types.UuidType())
    def get_one(self, id):
        """Returns the lease having this specific uuid

        :param id: ID of lease
        """
        lease = pecan.request.rpcapi.get_lease(id)
        if lease is None:
            raise exceptions.NotFound(object={'lease_id': id})
        return Lease.convert(lease)

    @policy.authorize('leases', 'get')
    @wsme_pecan.wsexpose([Lease], q=[])
    def get_all(self):
        """Returns all leases."""
        return [Lease.convert(lease)
                for lease in pecan.request.rpcapi.list_leases()]

    @policy.authorize('leases', 'post')
    @wsme_pecan.wsexpose(Lease, body=Lease, status_code=201)
    @trusts.use_trust_auth()
    def post(self, lease):
        """Creates a new lease.

        :param lease: a lease within the request body.
        """
        # FIXME(sbauza): DB exceptions are currently catched and return a lease
        #                equal to None instead of being sent to the API
        lease_dct = lease.as_dict()
        lease = pecan.request.rpcapi.create_lease(lease_dct)
        if lease is not None:
            return Lease.convert(lease)
        else:
            raise exceptions.BlazarException(_("Lease can't be created"))

    @policy.authorize('leases', 'put')
    @wsme_pecan.wsexpose(Lease, types.UuidType(), body=Lease)
    def put(self, id, sublease):
        """Update an existing lease.

        :param id: UUID of a lease.
        :param lease: a subset of a Lease containing values to update.
        """
        sublease_dct = sublease.as_dict()
        new_name = sublease_dct.pop('name', None)
        end_date = sublease_dct.pop('end_date', None)
        start_date = sublease_dct.pop('start_date', None)
        before_end_date = sublease_dct.pop('before_end_date',
                                           None)

        if sublease_dct != {}:
            raise exceptions.BlazarException('Only name changing, '
                                             'dates and before end '
                                             'notifications may be '
                                             'proceeded.')
        if new_name:
            sublease_dct['name'] = new_name
        if end_date:
            sublease_dct['end_date'] = end_date
        if start_date:
            sublease_dct['start_date'] = start_date
        if before_end_date:
            sublease_dct['before_end_date'] = before_end_date

        lease = pecan.request.rpcapi.update_lease(id, sublease_dct)

        if lease is None:
            raise exceptions.NotFound(object={'lease_id': id})
        return Lease.convert(lease)

    @policy.authorize('leases', 'delete')
    @wsme_pecan.wsexpose(None, types.UuidType(), status_code=204)
    def delete(self, id):
        """Delete an existing lease.

        :param id: UUID of a lease.
        """
        try:
            pecan.request.rpcapi.delete_lease(id)
        except TypeError:
            # The lease was not existing when asking to delete it
            raise exceptions.NotFound(object={'lease_id': id})

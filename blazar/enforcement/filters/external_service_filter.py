# Copyright (c) 2022 University of Chicago.
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

import datetime
import json
import requests

from blazar.enforcement.filters import base_filter
from blazar import exceptions
from blazar.i18n import _
from blazar.utils.openstack.keystone import BlazarKeystoneClient

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return str(o)

        return json.JSONEncoder.default(self, o)


class ExternalServiceUnsupportedHTTPResponse(exceptions.BlazarException):
    code = 400
    msg_fmt = _('External service enforcement filter returned a %(status)s '
                'HTTP response. Only 204 and 403 responses are supported.')


class ExternalServiceUnsupportedDeniedResponse(exceptions.BlazarException):
    code = 400
    msg_fmt = _('External service enforcement filter returned a 403 HTTP '
                'response %(response)s without a valid JSON dictionary '
                'containing a "message" key.')


class ExternalServiceFilterException(exceptions.NotAuthorized):
    code = 400
    msg_fmt = _('%(message)s')


class ExternalServiceFilter(base_filter.BaseFilter):

    enforcement_opts = [
        cfg.StrOpt(
            'external_service_endpoint',
            default=None,
            help='The URL of the external service API.'),
        cfg.StrOpt(
            'external_service_check_create',
            default=None,
            help='Overwrite check-create endpoint with absolute URL.'),
        cfg.StrOpt(
            'external_service_check_update',
            default=None,
            help='Overwrite check-update endpoint with absolute URL.'),
        cfg.StrOpt(
            'external_service_on_end',
            default=None,
            help='Overwrite on-end endpoint with absolute URL.'),
        cfg.StrOpt(
            'external_service_token',
            default="",
            help='Token used for authentication with the external service.')
    ]

    def __init__(self, conf=None):
        super(ExternalServiceFilter, self).__init__(conf=conf)

    def get_headers(self):
        headers = {'Content-Type': 'application/json'}

        if self.external_service_token:
            headers['X-Auth-Token'] = (self.external_service_token)
        else:
            client = BlazarKeystoneClient()
            headers['X-Auth-Token'] = client.session.get_token()

        return headers

    def _get_absolute_url(self, path):
        url = self.external_service_endpoint

        if url[-1] == '/':
            url += path[1:]
        else:
            url += path

        return url

    def post(self, url, body):
        body = json.dumps(body, cls=DateTimeEncoder)
        req = requests.post(url, headers=self.get_headers(), data=body)

        if req.status_code == 204:
            return True
        elif req.status_code == 403:
            try:
                message = req.json()['message']
            except (requests.JSONDecodeError, KeyError):
                raise ExternalServiceUnsupportedDeniedResponse(
                    response=req.content)

            raise ExternalServiceFilterException(message=message)
        else:
            raise ExternalServiceUnsupportedHTTPResponse(
                status=req.status_code)

    def check_create(self, context, lease_values):
        body = dict(context=context, lease=lease_values)
        if self.external_service_check_create:
            self.post(self.external_service_check_create, body)
            return

        if self.external_service_endpoint:
            path = '/check-create'
            self.post(self._get_absolute_url(path), body)
            return

    def check_update(self, context, current_lease_values, new_lease_values):
        body = dict(context=context, current_lease=current_lease_values,
                    lease=new_lease_values)
        if self.external_service_check_update:
            self.post(self.external_service_check_update, body)
            return

        if self.external_service_endpoint:
            path = '/check-update'
            self.post(self._get_absolute_url(path), body)
            return

    def on_end(self, context, lease_values):
        body = dict(context=context, lease=lease_values)
        if self.external_service_on_end:
            self.post(self.external_service_on_end, body)
            return

        if self.external_service_endpoint:
            path = '/on-end'
            self.post(self._get_absolute_url(path), body)
            return

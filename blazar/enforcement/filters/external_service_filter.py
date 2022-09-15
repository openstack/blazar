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

from datetime import datetime
import json
import requests
from urllib.parse import urljoin
from urllib.parse import urlparse

from blazar.enforcement.exceptions import ExternalServiceFilterException
from blazar.enforcement.filters import base_filter
from blazar.exceptions import BlazarException
from blazar.i18n import _

from oslo_config import cfg
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class ISODateTimeEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


GENERIC_DENY_MSG = 'External service enforcement filter denied the request.'


class ExternalServiceMisconfigured(BlazarException):
    msg_fmt = _('%(message)s')


class ExternalServiceFilter(base_filter.BaseFilter):

    enforcement_opts = [
        cfg.StrOpt(
            'external_service_base_endpoint',
            default=None,
            help='The URL of the external service API.'),
        cfg.StrOpt(
            'external_service_check_create_endpoint',
            default=None,
            help='Overrides check-create endpoint with another URL.'),
        cfg.StrOpt(
            'external_service_check_update_endpoint',
            default=None,
            help='Overrides check-update endpoint with another URL.'),
        cfg.StrOpt(
            'external_service_on_end_endpoint',
            default=None,
            help='Overrides on-end endpoint with another URL.'),
        cfg.StrOpt(
            'external_service_token',
            default="",
            help='Token used for authentication with the external service.')
    ]

    def __init__(self, conf=None):
        super(ExternalServiceFilter, self).__init__(conf=conf)

        self._validate_url(conf.enforcement.external_service_base_endpoint)
        self.base_endpoint = conf.enforcement.external_service_base_endpoint

        self.check_create_endpoint = self._construct_url(
            "check-create",
            conf.enforcement.external_service_check_create_endpoint)
        self.check_update_endpoint = self._construct_url(
            "check-update",
            conf.enforcement.external_service_check_update_endpoint)
        self.on_end_endpoint = self._construct_url(
            "on-end",
            conf.enforcement.external_service_on_end_endpoint)

        endpoints = (
            self.check_create_endpoint,
            self.check_update_endpoint,
            self.on_end_endpoint,
        )

        if all(x is None for x in endpoints):
            raise ExternalServiceMisconfigured(
                message=_("ExternalService has no endpoints set."))

        self.token = conf.enforcement.external_service_token

    @staticmethod
    def _validate_url(url):
        if url is None:
            return
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ("http", "https"):
            raise ExternalServiceMisconfigured(
                message=_("ExternalService URL scheme must be http(s): "
                          "%s") % url)
        if parsed_url.netloc == '':
            raise ExternalServiceMisconfigured(
                message=_("ExternalService URL must have netloc: "
                          "%s") % url)

    def _construct_url(self, method, replacement_url):
        if replacement_url is None:
            if self.base_endpoint is None:
                return None
            return urljoin(self.base_endpoint, method)

        self._validate_url(replacement_url)
        return replacement_url

    def _get_headers(self):
        headers = {'Content-Type': 'application/json'}

        if self.token:
            headers['X-Auth-Token'] = self.token

        return headers

    def _post(self, url, body):
        body = json.dumps(body, cls=ISODateTimeEncoder)
        res = requests.post(url, headers=self._get_headers(), data=body)

        if res.status_code == 204:
            return True
        elif res.status_code == 403:
            try:
                message = res.json()['message']
            except (requests.JSONDecodeError, KeyError):
                # NOTE(yoctozepto): It is more secure not to send the actual
                # response to the end user as it may leak something.
                # Instead, we log it for debugging.
                LOG.debug("The External Service API returned a malformed "
                          "response (403): %s", res.content)
                message = GENERIC_DENY_MSG
        else:
            # NOTE(yoctozepto): It is more secure not to send the actual
            # response to the end user as it may leak something.
            # Instead, we log it for debugging.
            LOG.debug("The External Service API returned a malformed "
                      "response (%d): %s", res.status_code, res.content)
            message = GENERIC_DENY_MSG
        raise ExternalServiceFilterException(message=message)

    def check_create(self, context, lease_values):
        if self.check_create_endpoint:
            self._post(self.check_create_endpoint, dict(
                context=context, lease=lease_values))

    def check_update(self, context, current_lease_values, new_lease_values):
        if self.check_update_endpoint:
            self._post(self.check_update_endpoint, dict(
                context=context, current_lease=current_lease_values,
                lease=new_lease_values))

    def on_end(self, context, lease_values):
        if self.on_end_endpoint:
            self._post(self.on_end_endpoint, dict(
                context=context, lease=lease_values))

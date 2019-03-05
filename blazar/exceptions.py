# Copyright (c) 2013 Mirantis Inc.
# Copyright (c) 2013 Bull.
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

from blazar.i18n import _


LOG = logging.getLogger(__name__)


class BlazarException(Exception):
    """Base Blazar Exception.

    To correctly use this class, inherit from it and define
    a 'msg_fmt' and 'code' properties.
    """
    msg_fmt = _("An unknown exception occurred")
    code = 500

    def __init__(self, message=None, **kwargs):
        self.kwargs = kwargs

        if 'code' not in self.kwargs:
            self.kwargs['code'] = self.code

        if not message:
            try:
                message = self.msg_fmt % kwargs
            except KeyError:
                # kwargs doesn't match a variable in the message
                # log the issue and the kwargs
                LOG.exception('Exception in string format operation')
                for name, value in kwargs.items():
                    LOG.error("%(name)s: %(value)s",
                              {'name': name, 'value': value})

                message = self.msg_fmt

        super(BlazarException, self).__init__(message)


class NotFound(BlazarException):
    """Object not found exception."""
    msg_fmt = _("Object with %(object)s not found")
    code = 404


class NotAuthorized(BlazarException):
    msg_fmt = _("Not authorized")
    code = 403


class PolicyNotAuthorized(NotAuthorized):
    msg_fmt = _("Policy doesn't allow %(action)s to be performed")


class ConfigNotFound(BlazarException):
    msg_fmt = _("Could not find config at %(path)s")


class ServiceCatalogNotFound(NotFound):
    msg_fmt = _("Could not find service catalog")


class WrongFormat(BlazarException):
    msg_fmt = _("Unenxpectable object format")


class ServiceClient(BlazarException):
    msg_fmt = _("Service %(service)s have some problems")


class TaskFailed(BlazarException):
    msg_fmt = _('Current task failed')


class Timeout(BlazarException):
    msg_fmt = _('Current task failed with timeout')


class InvalidInput(BlazarException):
    code = 400
    msg_fmt = _("Expected a %(cls)s type but received %(value)s.")


class UnsupportedAPIVersion(BlazarException):
    msg_fmt = _('API version %(version)s is not supported. Blazar only '
                'supports Keystone v3 API.')


class InvalidStatus(BlazarException):
    msg_fmt = _("Invalid lease status.")


class InvalidAPIVersionString(BlazarException):
    message = _("API Version String %(version)s is of invalid format. Must "
                "be of format MajorNum.MinorNum.")

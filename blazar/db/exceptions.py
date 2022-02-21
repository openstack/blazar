# Copyright (c) 2014 Intel Corporation
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

from blazar import exceptions
from blazar.i18n import _


LOG = logging.getLogger(__name__)


class BlazarDBException(exceptions.BlazarException):
    msg_fmt = _('An unknown database exception occurred')


class BlazarDBDuplicateEntry(BlazarDBException):
    msg_fmt = _('Duplicate entry for %(columns)s in %(model)s model was found')


class BlazarDBNotFound(BlazarDBException):
    msg_fmt = _('%(id)s %(model)s was not found')


class BlazarDBInvalidFilter(BlazarDBException):
    msg_fmt = _('%(query_filter)s is invalid')


class BlazarDBInvalidFilterOperator(BlazarDBException):
    msg_fmt = _('%(filter_operator)s is invalid')


class BlazarDBResourcePropertiesNotEnabled(BlazarDBException):
    msq_fmt = _('%(resource_type)s does not have resource properties enabled.')


class BlazarDBInvalidResourceProperty(BlazarDBException):
    msg_fmt = _('%(property_name)s does not exist for resource type '
                '%(resource_type)s.')

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

from climate import exceptions
from climate.openstack.common.gettextutils import _  # noqa
from climate.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class ClimateDBException(exceptions.ClimateException):
    msg_fmt = _('An unknown database exception occurred')


class ClimateDBDuplicateEntry(ClimateDBException):
    msg_fmt = _('Duplicate entry for %(columns)s in %(model)s model was found')


class ClimateDBNotFound(ClimateDBException):
    msg_fmt = _('%(id)s %(model)s was not found')


class ClimateDBInvalidFilter(ClimateDBException):
    msg_fmt = _('%(query_filter)s is invalid')


class ClimateDBInvalidFilterOperator(ClimateDBException):
    msg_fmt = _('%(filter_operator)s is invalid')

# Copyright (c) 2020 University of Chicago.
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
from blazar import exceptions
from blazar.i18n import _


class MaxLeaseDurationException(exceptions.NotAuthorized):
    code = 400
    msg_fmt = _('Lease duration of %(lease_duration)s seconds must be less '
                'than or equal to the maximum lease duration of '
                '%(max_duration)s seconds.')


class ExternalServiceFilterException(exceptions.BlazarException):
    code = 400
    msg_fmt = _('%(message)s')

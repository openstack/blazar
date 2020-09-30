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

import datetime
import uuid

from oslo_serialization import jsonutils
from wsme import types as wtypes
from wsme import utils as wutils

from blazar import exceptions


class UuidType(wtypes.UserType):
    """A simple UUID type."""

    basetype = wtypes.text
    name = 'uuid'
    # FIXME(sbauza): When used with wsexpose decorator WSME will try
    # to get the name of the type by accessing it's __name__ attribute.
    # Remove this __name__ attribute once it's fixed in WSME.
    # https://bugs.launchpad.net/wsme/+bug/1265590
    __name__ = name

    def __init__(self, without_dashes=False):
        self.without_dashes = without_dashes

    def validate(self, value):
        try:
            valid_uuid = str(uuid.UUID(value))
            if self.without_dashes:
                valid_uuid = valid_uuid.replace('-', '')
            return valid_uuid
        except (TypeError, ValueError, AttributeError):
            error = 'Value should be UUID format'
            raise ValueError(error)


class IntegerType(wtypes.IntegerType):
    """A simple integer type. Can validate a value range.

    :param minimum: Possible minimum value
    :param maximum: Possible maximum value

    Example::

        Price = IntegerType(minimum=1)

    """

    name = 'integer'
    # FIXME(sbauza): When used with wsexpose decorator WSME will try
    # to get the name of the type by accessing it's __name__ attribute.
    # Remove this __name__ attribute once it's fixed in WSME.
    # https://bugs.launchpad.net/wsme/+bug/1265590
    __name__ = name


class CPUInfo(wtypes.UserType):
    """A type for matching CPU info from hypervisors."""

    basetype = wtypes.text
    name = 'cpuinfo as JSON formated str'

    @staticmethod
    def validate(value):
        # NOTE(sbauza): cpu_info can be very different from one Nova driver to
        #               another. We need to keep this method as generic as
        #               possible, ie. we accept JSONified dict.
        try:
            cpu_info = jsonutils.loads(value)
        except TypeError:
            raise exceptions.InvalidInput(cls=CPUInfo.name, value=value)
        if not isinstance(cpu_info, dict):
            raise exceptions.InvalidInput(cls=CPUInfo.name, value=value)
        return value


class TextOrInteger(wtypes.UserType):
    """A type for matching either text or integer."""

    basetype = wtypes.text
    name = 'textorinteger'

    @staticmethod
    def validate(value):
        # NOTE(sbauza): We need to accept non-unicoded Python2 strings
        if (isinstance(value, str) or isinstance(value, int)):
            return value
        else:
            raise exceptions.InvalidInput(cls=TextOrInteger.name, value=value)


class Datetime(wtypes.UserType):
    """A type for matching unicoded datetime."""

    basetype = wtypes.text
    name = 'datetime'

    # Format must be ISO8601 as default
    format = '%Y-%m-%dT%H:%M:%S.%f'

    def __init__(self, format=None):
        if format:
            self.format = format

    def validate(self, value):
        try:
            datetime.datetime.strptime(value, self.format)
        except ValueError:
            # FIXME(sbauza): Start_date and end_date are given using a specific
            #                format but are shown in default ISO8601, we must
            #                fail back to it for verification
            try:
                wutils.parse_isodatetime(value)
            except ValueError:
                raise exceptions.InvalidInput(cls=Datetime.name, value=value)
        return value

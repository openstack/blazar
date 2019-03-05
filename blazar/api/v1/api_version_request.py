# Copyright 2014 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import re

from blazar import exceptions
from blazar.i18n import _


# Define the minimum and maximum version of the API across all of the
# REST API. The format of the version is:
# X.Y where:
#
# - X will only be changed if a significant backwards incompatible API
# change is made which affects the API as whole. That is, something
# that is only very very rarely incremented.
#
# - Y when you make any change to the API. Note that this includes
# semantic changes which may not affect the input or output formats or
# even originate in the API code layer. We are not distinguishing
# between backwards compatible and backwards incompatible changes in
# the versioning system. It must be made clear in the documentation as
# to what is a backwards compatible change and what is a backwards
# incompatible one.

#
# You must update the API version history string below with a one or
# two line description as well as update rest_api_version_history.rst
REST_API_VERSION_HISTORY = """
       REST API Version History:
       * 1.0 - Includes all V1 APIs and extensions. V2 API is deprecated.
"""

# The minimum and maximum versions of the API supported
# The default api version request is defined to be the
# minimum version of the API supported.
MIN_API_VERSION = "1.0"
MAX_API_VERSION = "1.0"
DEFAULT_API_VERSION = MIN_API_VERSION

# Name of header used by clients to request a specific version
# of the REST API
API_VERSION_REQUEST_HEADER = 'OpenStack-API-Version'
VARY_HEADER = "Vary"

LATEST = "latest"
RESERVATION_SERVICE_TYPE = 'reservation'
BAD_REQUEST_STATUS_CODE = 400
BAD_REQUEST_STATUS_NAME = "BAD_REQUEST"
NOT_ACCEPTABLE_STATUS_CODE = 406
NOT_ACCEPTABLE_STATUS_NAME = "NOT_ACCEPTABLE"


def min_api_version():
    return APIVersionRequest(MIN_API_VERSION)


def max_api_version():
    return APIVersionRequest(MAX_API_VERSION)


class APIVersionRequest(object):
    """This class represents an API Version Request.

    This class includes convenience methods for manipulation
    and comparison of version numbers as needed to implement
    API microversions.
    """

    def __init__(self, api_version_request=None):
        """Create an API version request object."""

        self._ver_major = 0
        self._ver_minor = 0

        if api_version_request is not None:
            match = re.match(r"^([1-9]\d*)\.([1-9]\d*|0)$",
                             api_version_request)
            if match:
                self._ver_major = int(match.group(1))
                self._ver_minor = int(match.group(2))
            else:
                raise exceptions.InvalidAPIVersionString(
                    version=api_version_request)

    def __str__(self):
        """Debug/Logging representation of object."""
        return ("API Version Request Major: %(major)s, Minor: %(minor)s"
                % {'major': self._ver_major, 'minor': self._ver_minor})

    def _format_type_error(self, other):
        return TypeError(_("'%(other)s' should be an instance of '%(cls)s'") %
                         {"other": other, "cls": self.__class__})

    def __lt__(self, other):
        if not isinstance(other, APIVersionRequest):
            raise self._format_type_error(other)

        return ((self._ver_major, self._ver_minor) <
                (other._ver_major, other._ver_minor))

    def __eq__(self, other):
        if not isinstance(other, APIVersionRequest):
            raise self._format_type_error(other)

        return ((self._ver_major, self._ver_minor) ==
                (other._ver_major, other._ver_minor))

    def __gt__(self, other):
        if not isinstance(other, APIVersionRequest):
            raise self._format_type_error(other)

        return ((self._ver_major, self._ver_minor) >
                (other._ver_major, other._ver_minor))

    def __le__(self, other):
        return self < other or self == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __ge__(self, other):
        return self > other or self == other

    def matches(self, min_version, max_version=None):
        """Compares this version to the specified min/max range.

        Returns whether the version object represents a version
        greater than or equal to the minimum version and less than
        or equal to the maximum version.

        If min_version is null then there is no minimum limit.
        If max_version is null then there is no maximum limit.
        If self is null then raise ValueError.

        :param min_version: Minimum acceptable version.
        :param max_version: Maximum acceptable version.
        :param experimental: Whether to match experimental APIs.
        :returns: boolean
        """

        if self.is_null():
            raise ValueError
        if max_version.is_null() and min_version.is_null():
            return True
        elif max_version.is_null():
            return min_version <= self
        elif min_version.is_null():
            return self <= max_version
        else:
            return min_version <= self <= max_version

    def is_null(self):
        return self._ver_major == 0 and self._ver_minor == 0

    def get_string(self):
        """Returns a string representation of this object.

        If this method is used to create an APIVersionRequest,
        the resulting object will be an equivalent request.
        """
        if self.is_null():
            raise ValueError
        return ("%(major)s.%(minor)s" %
                {'major': self._ver_major, 'minor': self._ver_minor})

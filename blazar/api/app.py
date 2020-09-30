# Copyright (c) 2017 NTT Inc.
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

from oslo_serialization import jsonutils

from blazar.api.v1 import app as v1_app
from blazar.api.v2 import app as v2_app


class VersionSelectorApplication(object):
    """Maps WSGI versioned apps and defines default WSGI app."""

    def __init__(self):
        self._status = ''
        self._response_headers = []
        self.v1 = v1_app.make_app()
        self.v2 = v2_app.make_app()

    def _append_versions_from_app(self, versions, app, environ):
        tmp_versions = app(environ, self.internal_start_response)
        if self._status.startswith("300"):
            # In case of v1, app returns ClosingIterator generator object,
            # whereas in case of v2, it returns list.
            # So convert it to iterator to get the versions.
            app_iter = iter(tmp_versions)
            tmp_versions = jsonutils.loads(next(app_iter))
            versions['versions'].extend(tmp_versions['versions'])
        return tmp_versions

    def internal_start_response(self, status, response_headers, exc_info=None):
        self._status = status
        self._response_headers = response_headers

    def __call__(self, environ, start_response):
        self._status = ''
        self._response_headers = []

        if environ['PATH_INFO'] == '/' or environ['PATH_INFO'] == '/versions':
            versions = {'versions': []}
            tmp_versions = self._append_versions_from_app(versions, self.v1,
                                                          environ)
            # Both v1 and v2 apps run auth_token middleware. So simply
            # validate token for v1. If it fails no need to call v2 app.
            if self._status.startswith("401"):
                start_response(self._status,
                               [("Content-Type", "application/json")])
                return tmp_versions
            self._append_versions_from_app(versions, self.v2,
                                           environ)
            if len(versions['versions']):
                start_response("300 Multiple Choices",
                               [("Content-Type", "application/json")])
                return [jsonutils.dump_as_bytes(versions)]
            else:
                start_response("204 No Content", [])
                return []
        else:
            if environ['PATH_INFO'].startswith('/v1'):
                return self.v1(environ, start_response)
            return self.v2(environ, start_response)

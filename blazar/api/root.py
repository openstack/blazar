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

from oslo_serialization import jsonutils
import pecan

from blazar.api.v2 import controllers


class RootController(object):

    v2 = controllers.V2Controller()

    def _append_versions_from_controller(self, versions, controller, path):
        for version in getattr(controller, 'versions', None):
            version['links'] = [{
                "href": "{0}/{1}".format(pecan.request.host_url, path),
                "rel": "self"}]
            versions.append(version)

    @pecan.expose(content_type='application/json')
    def index(self):
        pecan.response.status_code = 300
        pecan.response.content_type = 'application/json'
        versions = {"versions": []}
        self._append_versions_from_controller(versions['versions'],
                                              self.v2, 'v2')
        return jsonutils.dump_as_bytes(versions)

    @pecan.expose(content_type='application/json')
    def versions(self):
        return self.index()

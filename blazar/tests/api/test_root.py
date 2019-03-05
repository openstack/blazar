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

from blazar.tests import api


class TestRoot(api.APITest):
    def setUp(self):
        super(TestRoot, self).setUp()
        self.versions = {
            "versions":
            [{"status": "DEPRECATED",
              "id": "v2.0",
              "links": [{"href": "http://localhost/v2", "rel": "self"}]}]}

    def test_version_discovery_root(self):
        response = self.get_json('/',
                                 expect_errors=True,
                                 path_prefix='')
        self.assertEqual(300, response.status_int)
        self.assertEqual("application/json", response.content_type)
        self.assertEqual(self.versions, response.json)

    def test_version_discovery_versions(self):
        response = self.get_json('/versions',
                                 expect_errors=True,
                                 path_prefix='')
        self.assertEqual(300, response.status_int)
        self.assertEqual("application/json", response.content_type)
        self.assertEqual(self.versions, response.json)

    def test_bad_uri(self):
        response = self.get_json('/bad/path',
                                 expect_errors=True,
                                 path_prefix='')
        self.assertEqual(404, response.status_int)
        self.assertEqual("text/plain", response.content_type)

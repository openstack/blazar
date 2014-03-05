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

from climate.tests import api


class TestRoot(api.APITest):

    def test_root(self):
        response = self.get_json('/',
                                 expect_errors=True,
                                 path_prefix='')
        self.assertEqual(response.status_int, 200)
        self.assertEqual(response.content_type, "text/html")
        self.assertEqual(response.body, '')

    def test_bad_uri(self):
        response = self.get_json('/bad/path',
                                 expect_errors=True,
                                 path_prefix='')
        self.assertEqual(response.status_int, 404)
        self.assertEqual(response.content_type, "text/plain")

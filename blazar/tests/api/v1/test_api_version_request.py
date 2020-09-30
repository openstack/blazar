# Copyright (c) 2019 NTT DATA
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

import ddt

from blazar.api.v1 import api_version_request
from blazar import exceptions
from blazar import tests


@ddt.ddt
class APIVersionRequestTests(tests.TestCase):
    def test_valid_version_strings(self):
        def _test_string(version, exp_major, exp_minor):
            v = api_version_request.APIVersionRequest(version)
            self.assertEqual(v._ver_major, exp_major)
            self.assertEqual(v._ver_minor, exp_minor)

        _test_string("1.1", 1, 1)
        _test_string("2.10", 2, 10)
        _test_string("5.234", 5, 234)
        _test_string("12.5", 12, 5)
        _test_string("2.0", 2, 0)
        _test_string("2.200", 2, 200)

    def test_min_version(self):
        self.assertEqual(
            api_version_request.APIVersionRequest(
                api_version_request.MIN_API_VERSION),
            api_version_request.min_api_version())

    def test_max_api_version(self):
        self.assertEqual(
            api_version_request.APIVersionRequest(
                api_version_request.MAX_API_VERSION),
            api_version_request.max_api_version())

    def test_null_version(self):
        v = api_version_request.APIVersionRequest()
        self.assertTrue(v.is_null())

    def test_not_null_version(self):
        v = api_version_request.APIVersionRequest('1.1')
        self.assertTrue(bool(v))

    @ddt.data("1", "100", "1.1.4", "100.23.66.3", "1 .1", "1. 1",
              "1.03", "01.1", "1.001", "", " 1.1", "1.1 ")
    def test_invalid_version_strings(self, version_string):
        self.assertRaises(exceptions.InvalidAPIVersionString,
                          api_version_request.APIVersionRequest,
                          version_string)

    def test_version_comparisons(self):
        vers1 = api_version_request.APIVersionRequest("1.0")
        vers2 = api_version_request.APIVersionRequest("1.5")
        vers3 = api_version_request.APIVersionRequest("2.23")
        vers4 = api_version_request.APIVersionRequest("2.0")
        v_null = api_version_request.APIVersionRequest()

        self.assertLess(v_null, vers2)
        self.assertLess(vers1, vers2)
        self.assertLessEqual(vers1, vers2)
        self.assertLessEqual(vers1, vers4)
        self.assertGreater(vers2, v_null)
        self.assertGreater(vers3, vers2)
        self.assertGreaterEqual(vers4, vers1)
        self.assertGreaterEqual(vers3, vers2)
        self.assertNotEqual(vers1, vers2)
        self.assertNotEqual(vers1, vers4)
        self.assertNotEqual(vers1, v_null)
        self.assertEqual(v_null, v_null)
        self.assertRaises(TypeError, vers1.__lt__, "2.1")
        self.assertRaises(TypeError, vers1.__gt__, "2.1")
        self.assertRaises(TypeError, vers1.__eq__, "1.0")

    def test_version_matches(self):
        vers1 = api_version_request.APIVersionRequest("1.0")
        vers2 = api_version_request.APIVersionRequest("1.1")
        vers3 = api_version_request.APIVersionRequest("1.2")
        vers4 = api_version_request.APIVersionRequest("2.0")
        vers5 = api_version_request.APIVersionRequest("1.1")
        v_null = api_version_request.APIVersionRequest()

        self.assertTrue(vers2.matches(vers1, vers3))
        self.assertTrue(vers2.matches(v_null, vers5))
        self.assertTrue(vers2.matches(vers1, v_null))
        self.assertTrue(vers1.matches(v_null, v_null))
        self.assertFalse(vers2.matches(vers3, vers4))
        self.assertRaises(ValueError, v_null.matches, vers1, vers3)

    def test_get_string(self):
        vers1_string = "1.13"
        vers1 = api_version_request.APIVersionRequest(vers1_string)
        self.assertEqual(vers1_string, vers1.get_string())

        self.assertRaises(ValueError,
                          api_version_request.APIVersionRequest().get_string)

    @ddt.data(('1', '0'), ('1', '1'))
    @ddt.unpack
    def test_str(self, major, minor):
        request_input = '%s.%s' % (major, minor)
        request = api_version_request.APIVersionRequest(request_input)
        request_string = str(request)

        self.assertEqual('API Version Request '
                         'Major: %s, Minor: %s' % (major, minor),
                         request_string)

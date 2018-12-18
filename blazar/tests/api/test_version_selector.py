# Copyright 2014 Intel Corporation
# All Rights Reserved.
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

from oslo_serialization import jsonutils

from blazar.api import app as api
from blazar.api.v1 import app as v1_app
from blazar.api.v2 import app as v2_app
from blazar import tests


class FakeWSGIApp(object):
    def __init__(self, id, status_code="300 Multiple Choices"):
        self.id_version = id
        self.status_code = status_code
        self.versions = {
            "versions":
            [{"status": "CURRENT",
              "id": "v{0}".format(self.id_version),
              "links": [{
                  "href": "http://localhost/v{0}".format(self.id_version),
                  "rel": "self"}]}]}

    def __call__(self, environ, start_response):
        start_response(self.status_code, [])
        if self.status_code == "300 Multiple Choices":
            return [jsonutils.dump_as_bytes(self.versions)]
        elif self.status_code == "401 Unauthorized":
            return ['{"error": '
                    '{"message": "The request you have '
                    'made requires authentication.",'
                    '"code": 401, "title": "Unauthorized"}}']


class TestVersionDiscovery(tests.TestCase):
    scenarios = [('path_root',
                  dict(path='/')),
                 ('path_versions',
                  dict(path='/versions'))]

    def start_response(self, status, response_headers):
        pass

    def setUp(self):
        super(TestVersionDiscovery, self).setUp()
        self.start_response_mock = self.patch(self, 'start_response')
        self.v1_app = v1_app
        self.v2_app = v2_app
        self.v1_make_app = self.patch(self.v1_app, 'make_app')
        self.v1_make_app.return_value = FakeWSGIApp(1)
        self.v2_make_app = self.patch(self.v2_app, 'make_app')
        self.v2_make_app.return_value = FakeWSGIApp(2)

    def test_get_versions(self):
        version_selector = api.VersionSelectorApplication()
        environ = {'PATH_INFO': self.path}

        versions_raw = version_selector(environ, self.start_response)
        versions = jsonutils.loads(versions_raw.pop())

        self.assertEqual(2, len(versions['versions']))
        self.assertEqual("v{0}".format(self.v1_make_app().id_version),
                         versions['versions'][0]['id'])
        self.assertEqual("v{0}".format(self.v2_make_app().id_version),
                         versions['versions'][1]['id'])
        self.start_response_mock.assert_called_with(
            "300 Multiple Choices",
            [("Content-Type", "application/json")])

    def test_get_versions_only_from_one_api(self):
        self.v2_make_app.return_value = FakeWSGIApp(2, "404 Not Found")
        version_selector = api.VersionSelectorApplication()
        environ = {'PATH_INFO': self.path}

        versions_raw = version_selector(environ, self.start_response)
        versions = jsonutils.loads(versions_raw.pop())

        self.assertEqual(1, len(versions['versions']))
        self.assertEqual("v{0}".format(self.v1_make_app().id_version),
                         versions['versions'][0]['id'])
        self.start_response_mock.assert_called_with(
            "300 Multiple Choices",
            [("Content-Type", "application/json")])

    def test_no_versions_at_all(self):
        self.v1_make_app.return_value = FakeWSGIApp(1, "404 Not Found")
        self.v2_make_app.return_value = FakeWSGIApp(2, "404 Not Found")
        version_selector = api.VersionSelectorApplication()
        environ = {'PATH_INFO': self.path}

        versions_raw = version_selector(environ, self.start_response)
        self.assertEqual([], versions_raw)
        self.start_response_mock.assert_called_with("204 No Content", [])

    def test_unauthorized_token(self):
        self.v1_make_app.return_value = FakeWSGIApp(1, "401 Unauthorized")
        version_selector = api.VersionSelectorApplication()
        environ = {'PATH_INFO': self.path}

        versions_raw = version_selector(environ, self.start_response)
        self.assertEqual(['{"error": '
                          '{"message": "The request you have '
                          'made requires authentication.",'
                          '"code": 401, "title": "Unauthorized"}}'],
                         versions_raw)

        self.start_response_mock.assert_called_with(
            "401 Unauthorized",
            [("Content-Type", "application/json")])


class TestVersionSelectorApplication(tests.TestCase):
    def start_response(self, status, response_headers):
        pass

    def setUp(self):
        super(TestVersionSelectorApplication, self).setUp()
        self.v1_app = v1_app
        self.v2_app = v2_app
        self.v1_make_app = self.patch(self.v1_app, 'make_app')
        self.v1_make_app.return_value = FakeWSGIApp(1)
        self.v2_make_app = self.patch(self.v2_app, 'make_app')
        self.v2_make_app.return_value = FakeWSGIApp(2)

    def test_get_v1_app(self):
        version_selector = api.VersionSelectorApplication()
        environ = {'PATH_INFO': "/v1"}

        versions_raw = version_selector(environ, self.start_response)
        versions = jsonutils.loads(versions_raw.pop())
        self.assertEqual(self.v1_make_app().versions, versions)

    def test_get_v2_app(self):
        version_selector = api.VersionSelectorApplication()
        environ = {'PATH_INFO': "/v2"}

        versions_raw = version_selector(environ, self.start_response)
        versions = jsonutils.loads(versions_raw.pop())
        self.assertEqual(self.v2_make_app().versions, versions)

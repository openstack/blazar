# Copyright (c) 2013 Mirantis Inc.
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

import flask
from keystoneclient.middleware import auth_token
from werkzeug import exceptions as werkzeug_exceptions

from climate.api import app
from climate.api import utils as api_utils
from climate import context
from climate import tests


class AppTestCase(tests.TestCase):
    def setUp(self):
        super(AppTestCase, self).setUp()

        self.app = app
        self.api_utils = api_utils
        self.context = context
        self.flask = flask
        self.auth_token = auth_token

        self.render = self.patch(self.api_utils, 'render')
        self.context_clear = self.patch(self.context.Context, 'clear')
        self.fake_app = self.patch(self.flask, 'Flask')
        self.fake_ff = self.patch(self.auth_token, 'filter_factory')

        self.ex = werkzeug_exceptions.HTTPException()
        self.ex.code = 1313
        self.ex.description = "my favourite error"

    def test_make_json_error_proper(self):
        self.app.make_json_error(self.ex)
        self.render.assert_called_once_with(
            {'error': 1313,
             'error_message': 'my favourite error'}, status=1313)

    def test_make_json_error_wrong(self):
        self.app.make_json_error('wrong')
        self.render.assert_called_once_with(
            {'error': 500,
             'error_message': 'wrong'}, status=500)

    def test_version_list(self):
        self.app.version_list()
        self.render.assert_called_once_with({
            "versions": [
                {"id": "v1.0", "status": "CURRENT"},
            ],
        })

    def test_teardown_request(self):
        self.app.teardown_request()
        self.context_clear.assert_called_once()

    def test_make_app(self):
        self.app.make_app()
        self.fake_ff.assert_called_once_with(self.fake_app().config,
                                             admin_user='admin',
                                             admin_tenant_name='admin',
                                             auth_port='35357',
                                             auth_protocol='http',
                                             auth_version='v2.0',
                                             admin_password='nova',
                                             auth_host='127.0.0.1')

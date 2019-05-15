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
from keystonemiddleware import auth_token
from oslo_config import cfg
from werkzeug import exceptions as werkzeug_exceptions

from blazar.api.v1 import app
from blazar.api.v1.leases import v1_0 as lease_api_v1_0
from blazar.api.v1.networks import v1_0 as network_api_v1_0
from blazar.api.v1.oshosts import v1_0 as host_api_v1_0
from blazar.api.v1 import utils as api_utils
from blazar import tests


class AppTestCase(tests.TestCase):
    def setUp(self):
        super(AppTestCase, self).setUp()

        self.app = app
        self.api_utils = api_utils
        self.flask = flask
        self.auth_token = auth_token

        self.render = self.patch(self.api_utils, 'render')
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
        a = flask.Flask('dummy')
        a.config['TESTING'] = True
        with a.test_request_context():
            self.app.version_list()
            self.render.assert_called_once_with({
                "versions": [
                    {"id": "v1.0",
                     "status": "CURRENT",
                     'min_version': '1.0', 'max_version': '1.0',
                     "links": [{"href": "{0}v1".format(flask.request.host_url),
                                "rel": "self"}]
                     },
                ]},
                status="300 Multiple Choices")

    def test_make_app(self):
        fake_app = self.patch(self.flask, 'Flask')
        self.app.make_app()
        self.fake_ff.assert_called_once_with(fake_app().config)


class AppTestCaseForHostsPlugin(tests.TestCase):

    def setUp(self):
        super(AppTestCaseForHostsPlugin, self).setUp()

        cfg.CONF.set_override('plugins', ['physical.host.plugin'], 'manager')
        self.app = app
        self.host_api_v1_0 = host_api_v1_0
        self.lease_api_v1_0 = lease_api_v1_0
        self.flask = flask
        self.fake_blueprint = self.patch(self.flask.Flask,
                                         'register_blueprint')

    def test_make_app_with_host_plugin(self):
        self.app.make_app()
        self.fake_blueprint.assert_any_call(self.lease_api_v1_0.rest,
                                            url_prefix='/v1')
        self.fake_blueprint.assert_any_call(self.host_api_v1_0.rest,
                                            url_prefix='/v1/os-hosts')


class AppTestCaseForNetworksPlugin(tests.TestCase):

    def setUp(self):
        super(AppTestCaseForNetworksPlugin, self).setUp()

        cfg.CONF.set_override(
            'plugins', ['network.plugin'], 'manager')
        self.app = app
        self.network_api_v1_0 = network_api_v1_0
        self.flask = flask
        self.fake_blueprint = self.patch(self.flask.Flask,
                                         'register_blueprint')

    def test_make_app_with_network_plugin(self):
        self.app.make_app()
        self.fake_blueprint.assert_any_call(self.network_api_v1_0.rest,
                                            url_prefix='/v1/networks')

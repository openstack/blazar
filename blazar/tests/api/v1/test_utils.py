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

from blazar.api.v1 import app as v1_app
from blazar.api.v1 import utils
from blazar import tests


class Error(Exception):
    def __init__(self, message=None, code=None):
        self.code = code
        super(Error, self).__init__(message)


class UtilsTestCase(tests.TestCase):
    def setUp(self):
        super(UtilsTestCase, self).setUp()
        app = v1_app.make_app()

        with app.test_request_context():
            self.utils = utils
            self.flask = flask

            self.rest = utils.Rest('v1_0', __name__)
            self.patch(self.rest, "_mroute")
            self.response = self.patch(self.flask, "Response")
            self.abort = self.patch(self.flask, "abort")
            self.request = self.patch(self.flask, "request")

            self.error = Error("message", "code")

    def test_get(self):
        self.rest.get('rule', status_code=200)
        self.rest._mroute.assert_called_once_with('GET', 'rule', 200,
                                                  query=False)

    def test_post(self):
        self.rest.post('rule', status_code=201)
        self.rest._mroute.assert_called_once_with('POST', 'rule', 201)

    def test_put(self):
        self.rest.put('rule', status_code=200)
        self.rest._mroute.assert_called_once_with('PUT', 'rule', 200)

    def test_delete(self):
        self.rest.delete('rule', status_code=204)
        self.rest._mroute.assert_called_once_with('DELETE', 'rule', 204)

    def test_route_ok(self):
        pass

    def test_route_fail(self):
        pass

    def test_render_wrong_result(self):
        self.utils.render(result=['a', 'a'], response_type='application/json',
                          status='LOL', kwargs={'a': 'b'})
        self.abort.assert_called_once_with(
            500, description="Non-dict and non-empty kwargs passed to render.")

    def test_render_wrong_resp_type(self):
        self.utils.render(result={}, response_type="not_app", status='LOL')
        self.abort.assert_called_once_with(
            400, description="Content type 'not_app' isn't supported")

    def test_render_ok(self):
        self.utils.render(result={}, response_type='application/json',
                          status='lol')
        self.response.assert_called_once_with(mimetype='application/json',
                                              status='lol', response=b'{}')

    def test_request_data_data(self):
        self.request.parsed_data = "data"
        self.assertEqual("data", self.utils.request_data())

    def test_request_data_file(self):
        self.request.file_upload = True
        self.request.data = 'foo'
        del self.request.parsed_data
        flask.request.content_length = 1
        self.assertEqual('foo', self.utils.request_data())

    def test_request_data_length(self):
        del self.request.parsed_data
        self.request.content_length = 0
        self.utils.request_data()
        self.assertEqual({}, self.utils.request_data())

    def test_get_request_args(self):
        self.flask.request.args = 'foo'
        self.assertEqual('foo', self.utils.get_request_args())

    def test_abort_and_log(self):
        self.utils.abort_and_log(400, "Funny error")
        self.abort.assert_called_once_with(400, description="Funny error")

    def test_render_error_message(self):
        render = self.patch(self.utils, 'render')
        self.utils.render_error_message(404, 'NOT FOUND', 'not_found')
        render.assert_called_once_with({'error_name': 'not_found',
                                        'error_message': 'NOT FOUND',
                                        'error_code': 404})

    def test_internal_error_501(self):
        error_message = self.patch(self.utils, 'render_error_message')
        self.utils.internal_error(501, "Funny error")
        error_message.assert_called_once_with(
            501, "Funny error", "NOT_IMPLEMENTED_ERROR")

    def test_internal_error_various(self):
        error_message = self.patch(self.utils, 'render_error_message')
        self.utils.internal_error(404, "Funny error")
        error_message.assert_called_once_with(
            404, "Funny error", "INTERNAL_SERVER_ERROR")

    def test_bad_request(self):
        error_message = self.patch(self.utils, 'render_error_message')
        self.utils.bad_request(self.error)
        error_message.assert_called_once_with('code', 'message', 'code')

    def test_bad_request_with_default_errorcode(self):
        error_message = self.patch(self.utils, 'render_error_message')
        error = Error("message")
        self.utils.bad_request(error)
        error_message.assert_called_once_with(400, 'message', 400)

    def test_not_found(self):
        error_message = self.patch(self.utils, 'render_error_message')
        self.utils.not_found(self.error)
        error_message.assert_called_once_with('code', 'message', 'code')

    def test_not_found_with_default_errorcode(self):
        error_message = self.patch(self.utils, 'render_error_message')
        error = Error("message")
        self.utils.not_found(error)
        error_message.assert_called_once_with(404, 'message', 404)

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

from climate.api import utils
from climate import tests


class Error:
    def __init__(self, message=None, code=None):
        self.message = message
        self.code = code


class UtilsTestCase(tests.TestCase):
    def setUp(self):
        super(UtilsTestCase, self).setUp()
        self.utils = utils
        self.flask = flask

        self.rest = self.patch(self.utils, "Rest")
        self.response = self.patch(self.flask, "Response")
        self.abort = self.patch(self.flask, "abort")
        self.request = self.patch(self.flask, "request")

        self.error = Error("message", "code")

    def test_get(self):
        self.rest.get('rule', status_code=200)
        self.rest._mroute.called_once_with('GET', 'rule', 200)

    def test_post(self):
        self.rest.post('rule', status_code=202)
        self.rest._mroute.called_once_with('POST', 'rule', 200)

    def test_put(self):
        self.rest.put('rule', status_code=202)
        self.rest._mroute.called_once_with('PUT', 'rule', 202)

    def test_delete(self):
        self.rest.delete('rule', status_code=204)
        self.rest._mroute.called_once_with('DELETE', 'rule', 204)

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
                                              status='lol', response='{}')

    def test_request_data_data(self):
        self.request.parsed_data = "data"
        self.utils.request_data()
        self.request.assert_called_once()

    def test_request_data_file(self):
        self.request.file_upload = True
        self.utils.request_data()
        self.request.assert_called_once()

    def test_request_data_length(self):
        self.request.content_length = 0
        self.utils.request_data()
        self.request.assert_called_once()

    def test_get_request_args(self):
        self.utils.get_request_args()
        self.request.assert_called_once()

    def test_abort_and_log(self):
        self.utils.abort_and_log(400, "Funny error")
        self.abort.called_once_with(400, description="Funny error")

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
        error_message.assert_called_once_with(
            400, 'message', 'code')

    def test_not_found(self):
        error_message = self.patch(self.utils, 'render_error_message')
        self.utils.not_found(self.error)
        error_message.assert_called_once_with(
            404, 'message', 'code')

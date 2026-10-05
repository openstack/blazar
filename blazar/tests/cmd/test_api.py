# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import socketserver
import threading
from unittest import mock
import urllib.request

from blazar.cmd import api
from blazar import tests


class ApiCmdTestCase(tests.TestCase):

    @mock.patch.object(api.v2_app, 'make_app')
    @mock.patch.object(api.service_utils, 'prepare_service')
    @mock.patch.object(api, 'cfg')
    @mock.patch.object(api, 'CONF')
    @mock.patch.object(api.simple_server, 'make_server')
    def test_main_serves_in_the_foreground(self, make_server, conf, cfg,
                                           prepare_service, make_app):
        conf.enable_v1_api = False

        api.main()

        # The server must run in the calling thread: main() returning is
        # the process exiting.
        make_server.assert_called_once_with(
            conf.host, conf.port, make_app.return_value,
            server_class=api.ThreadingWSGIServer)
        make_server.return_value.serve_forever.assert_called_once_with()

    def test_server_handles_requests_in_threads(self):
        self.assertTrue(issubclass(api.ThreadingWSGIServer,
                                   socketserver.ThreadingMixIn))
        self.assertTrue(api.ThreadingWSGIServer.daemon_threads)

        def app(environ, start_response):
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return [b'ok']

        httpd = api.simple_server.make_server(
            '127.0.0.1', 0, app, server_class=api.ThreadingWSGIServer)
        self.addCleanup(httpd.server_close)
        thread = threading.Thread(target=httpd.serve_forever)
        thread.start()
        try:
            url = 'http://127.0.0.1:%d/' % httpd.server_port
            with urllib.request.urlopen(url, timeout=5) as response:
                self.assertEqual(b'ok', response.read())
        finally:
            httpd.shutdown()
            thread.join()

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

"""Base classes for API tests."""
from keystonemiddleware import fixture
from oslo_utils import uuidutils
import pecan
import pecan.testing

from blazar.api import context as api_context
from blazar import context
from blazar.manager.leases import rpcapi as leases_api
from blazar.manager.oshosts import rpcapi as hosts_rpcapi
from blazar import tests

PATH_PREFIX = '/v2'

FAKE_PROJECT = '981b767265174c108bc5a61185b748ac'
FAKE_USER = 'b4fdb2fff13545ceb751295096cc18ee'


class APITest(tests.TestCase):
    """Used for unittests tests of Pecan controllers."""

    ADMIN_TOKEN = uuidutils.generate_uuid(dashed=False)
    MEMBER_TOKEN = uuidutils.generate_uuid(dashed=False)

    # SOURCE_DATA = {'test_source': {'somekey': '666'}}

    def setUp(self):
        def fake_ctx_from_headers(headers):
            if not headers:
                return context.BlazarContext(
                    user_id=FAKE_USER, project_id=FAKE_PROJECT,
                    roles=['member'])
            roles = headers.get('X-Roles', str('member')).split(',')
            return context.BlazarContext(
                user_id=headers.get('X-User-Id', FAKE_USER),
                project_id=headers.get('X-Project-Id', FAKE_PROJECT),
                auth_token=headers.get('X-Auth-Token', None),
                service_catalog=None,
                user_name=headers.get('X-User-Name', 'fake'),
                project_name=headers.get('X-Project-Name', 'fake'),
                roles=roles,
            )

        super(APITest, self).setUp()

        self.keystone_middleware = None
        self.app = self._make_app()

        # NOTE(sbauza): Context is taken from Keystone auth middleware, we need
        #               to simulate here
        self.api_context = api_context
        self.fake_ctx_from_headers = self.patch(self.api_context,
                                                'ctx_from_headers')
        self.fake_ctx_from_headers.side_effect = fake_ctx_from_headers

        self.rpcapi = leases_api.ManagerRPCAPI
        self.hosts_rpcapi = hosts_rpcapi.ManagerRPCAPI

        # self.patch(rpcapi.ManagerRPCAPI, 'list_leases').return_value = []

        def reset_pecan():
            pecan.set_config({}, overwrite=True)

        self.addCleanup(reset_pecan)

    def _make_app(self, enable_acl=False):
        # Determine where we are so we can set up paths in the config

        # NOTE(sbauza): Keystone middleware auth can be deactivated using
        #               enable_acl set to False

        if enable_acl:
            self.keystone_middleware = self.useFixture(
                fixture.AuthTokenFixture())

            self.keystone_middleware.add_token_data(token_id=self.ADMIN_TOKEN,
                                                    user_id='user_id1',
                                                    user_name='user_name1',
                                                    project_id='123i2910',
                                                    role_list=['admin'])
            self.keystone_middleware.add_token_data(token_id=self.MEMBER_TOKEN,
                                                    user_id='user_id2',
                                                    user_name='user-good',
                                                    project_id='project-good',
                                                    role_list=['Member'])

        self.config = {
            'app': {
                'modules': ['blazar.api.v2'],
                'root': 'blazar.api.root.RootController',
                'enable_acl': enable_acl,
            },
        }

        return pecan.testing.load_test_app(self.config)

    def _request_json(self, path, params, expect_errors=False, headers=None,
                      method="post", extra_environ=None, status=None,
                      path_prefix=PATH_PREFIX):
        """Sends simulated HTTP request to Pecan test app.

        :param path: url path of target service
        :param params: content for wsgi.input of request
        :param expect_errors: Boolean value; whether an error is expected based
                              on request
        :param headers: a dictionary of headers to send along with the request
        :param method: Request method type. Appropriate method function call
                       should be used rather than passing attribute in.
        :param extra_environ: a dictionary of environ variables to send along
                              with the request
        :param status: expected status code of response
        :param path_prefix: prefix of the url path
        """
        full_path = path_prefix + path
        print('%s: %s %s' % (method.upper(), full_path, params))
        response = getattr(self.app, "%s_json" % method)(
            str(full_path),
            params=params,
            headers=headers,
            status=status,
            extra_environ=extra_environ,
            expect_errors=expect_errors
        )
        print('GOT:%s' % response)
        return response

    def put_json(self, path, params, expect_errors=False, headers=None,
                 extra_environ=None, status=None):
        """Sends simulated HTTP PUT request to Pecan test app.

        :param path: url path of target service
        :param params: content for wsgi.input of request
        :param expect_errors: Boolean value; whether an error is expected based
                              on request
        :param headers: a dictionary of headers to send along with the request
        :param extra_environ: a dictionary of environ variables to send along
                              with the request
        :param status: expected status code of response
        """
        return self._request_json(path=path, params=params,
                                  expect_errors=expect_errors,
                                  headers=headers, extra_environ=extra_environ,
                                  status=status, method="put")

    def post_json(self, path, params, expect_errors=False, headers=None,
                  extra_environ=None, status=None):
        """Sends simulated HTTP POST request to Pecan test app.

        :param path: url path of target service
        :param params: content for wsgi.input of request
        :param expect_errors: Boolean value; whether an error is expected based
                              on request
        :param headers: a dictionary of headers to send along with the request
        :param extra_environ: a dictionary of environ variables to send along
                              with the request
        :param status: expected status code of response
        """
        return self._request_json(path=path, params=params,
                                  expect_errors=expect_errors,
                                  headers=headers, extra_environ=extra_environ,
                                  status=status, method="post")

    def delete(self, path, expect_errors=False, headers=None,
               extra_environ=None, status=None, path_prefix=PATH_PREFIX):
        """Sends simulated HTTP DELETE request to Pecan test app.

        :param path: url path of target service
        :param expect_errors: Boolean value; whether an error is expected based
                              on request
        :param headers: a dictionary of headers to send along with the request
        :param extra_environ: a dictionary of environ variables to send along
                              with the request
        :param status: expected status code of response
        :param path_prefix: prefix of the url path
        """
        full_path = path_prefix + path
        print('DELETE: %s' % (full_path))
        response = self.app.delete(str(full_path),
                                   headers=headers,
                                   status=status,
                                   extra_environ=extra_environ,
                                   expect_errors=expect_errors)
        print('GOT:%s' % response)
        return response

    def get_json(self, path, expect_errors=False, headers=None,
                 extra_environ=None, q=[], path_prefix=PATH_PREFIX, **params):
        """Sends simulated HTTP GET request to Pecan test app.

        :param path: url path of target service
        :param expect_errors: Boolean value;whether an error is expected based
                              on request
        :param headers: a dictionary of headers to send along with the request
        :param extra_environ: a dictionary of environ variables to send along
                              with the request
        :param q: list of queries consisting of: field, value, op, and type
                  keys
        :param path_prefix: prefix of the url path
        :param params: content for wsgi.input of request
        """
        full_path = path_prefix + path
        query_params = {'q.field': [],
                        'q.value': [],
                        'q.op': [],
                        }
        for query in q:
            for name in ['field', 'op', 'value']:
                query_params['q.%s' % name].append(query.get(name, ''))
        all_params = {}
        all_params.update(params)
        if q:
            all_params.update(query_params)
        print('GET: %s %r' % (full_path, all_params))
        response = self.app.get(full_path,
                                params=all_params,
                                headers=headers,
                                extra_environ=extra_environ,
                                expect_errors=expect_errors)
        if not expect_errors:
            response = response.json
        print('GOT:%s' % response)
        return response

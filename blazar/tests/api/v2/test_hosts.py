# -*- encoding: utf-8 -*-
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
"""
Tests for API /os-hosts/ methods
"""
from oslo_utils import uuidutils

from blazar.tests import api
from blazar.utils import trusts


def fake_computehost(**kw):
    return {
        'id': kw.get('id', '1'),
        'hypervisor_hostname': kw.get('hypervisor_hostname', 'host01'),
        'hypervisor_type': kw.get('hypervisor_type', 'QEMU'),
        'vcpus': kw.get('vcpus', 1),
        'hypervisor_version': kw.get('hypervisor_version', 1000000),
        'trust_id': kw.get('trust_id',
                           '35b17138-b364-4e6a-a131-8f3099c5be68'),
        'memory_mb': kw.get('memory_mb', 8192),
        'local_gb': kw.get('local_gb', 50),
        'cpu_info': kw.get('cpu_info',
                           "{\"vendor\": \"Intel\", \"model\": \"qemu32\", "
                           "\"arch\": \"x86_64\", \"features\": [],"
                           " \"topology\": {\"cores\": 1}}",
                           ),
        'extra_capas': kw.get('extra_capas',
                              {'vgpus': 2, 'fruits': 'bananas'})
    }


def fake_computehost_request_body(include=[], **kw):
    computehost_body = fake_computehost(**kw)
    computehost_body['name'] = kw.get('name',
                                      computehost_body['hypervisor_hostname'])
    include.append('name')
    include.append('extra_capas')
    return dict((key, computehost_body[key])
                for key in computehost_body if key in include)


def fake_computehost_from_rpc(**kw):
    # NOTE(sbauza): Extra capabilites are returned as extra key/value pairs
    #               from the Manager when searching from a specific node.
    computehost = fake_computehost(**kw)
    extra_capas = computehost.pop('extra_capas', None)
    if extra_capas is not None:
        computehost.update(extra_capas)
    return computehost


def fake_trust(id=fake_computehost()['trust_id']):
    return type('Trust', (), {
        'id': id,
    })


class TestIncorrectHostFromRPC(api.APITest):

    def setUp(self):
        super(TestIncorrectHostFromRPC, self).setUp()

        self.path = '/os-hosts'
        self.patch(
            self.hosts_rpcapi, 'list_computehosts').return_value = [
                fake_computehost_from_rpc(hypervisor_type=1)
            ]

        self.headers = {'X-Roles': 'admin'}

    def test_bad_list(self):
        expected = {
            'error_code': 400,
            'error_message': "Invalid input",
            'error_name': 400
        }
        response = self.get_json(self.path, expect_errors=True,
                                 headers=self.headers)
        self.assertEqual(400, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected["error_name"], response.json["error_name"])
        self.assertTrue(expected["error_message"]
                        in response.json["error_message"])
        self.assertEqual(expected["error_code"], response.json["error_code"])


class TestListHosts(api.APITest):

    def setUp(self):
        super(TestListHosts, self).setUp()

        self.path = '/os-hosts'
        self.patch(self.hosts_rpcapi, 'list_computehosts').return_value = []

        self.headers = {'X-Roles': 'admin'}

    def test_empty(self):
        response = self.get_json(self.path, headers=self.headers)
        self.assertEqual([], response)

    def test_one(self):
        self.patch(
            self.hosts_rpcapi, 'list_computehosts'
        ).return_value = [fake_computehost_from_rpc(id=1)]

        response = self.get_json(self.path, headers=self.headers)
        self.assertEqual([fake_computehost(id=1)], response)

    def test_multiple(self):
        id1 = str('1')
        id2 = str('2')
        self.patch(
            self.hosts_rpcapi, 'list_computehosts').return_value = [
                fake_computehost_from_rpc(id=id1),
                fake_computehost_from_rpc(id=id2)
            ]
        response = self.get_json(self.path, headers=self.headers)
        self.assertEqual([fake_computehost(id=id1), fake_computehost(id=id2)],
                         response)

    def test_rpc_exception_list(self):
        def fake_list_computehosts(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.hosts_rpcapi, 'list_computehosts'
        ).side_effect = fake_list_computehosts
        response = self.get_json(self.path, headers=self.headers,
                                 expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestShowHost(api.APITest):

    def setUp(self):
        super(TestShowHost, self).setUp()

        self.id1 = str('1')
        self.path = '/os-hosts/{0}'.format(self.id1)
        self.patch(
            self.hosts_rpcapi, 'get_computehost'
        ).return_value = fake_computehost_from_rpc(id=self.id1)

        self.headers = {'X-Roles': 'admin'}

    def test_one(self):
        response = self.get_json(self.path, headers=self.headers)
        self.assertEqual(fake_computehost(id=self.id1), response)

    def test_empty(self):
        expected = {
            'error_code': 404,
            'error_message': "Object with {{'host_id': "
                             "{0}}} not found".format(self.id1),
            'error_name': 404
        }
        self.patch(self.hosts_rpcapi, 'get_computehost').return_value = None
        response = self.get_json(self.path, expect_errors=True,
                                 headers=self.headers)
        self.assertEqual(404, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_rpc_exception_get(self):
        def fake_get_computehost(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.hosts_rpcapi, 'get_computehost'
        ).side_effect = fake_get_computehost
        response = self.get_json(self.path, expect_errors=True,
                                 headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestCreateHost(api.APITest):

    def setUp(self):
        super(TestCreateHost, self).setUp()

        self.id1 = str(uuidutils.generate_uuid())
        self.fake_computehost = fake_computehost(id=self.id1)
        self.fake_computehost_body = fake_computehost_request_body(id=self.id1)
        self.path = '/os-hosts'
        self.patch(
            self.hosts_rpcapi, 'create_computehost'
        ).return_value = fake_computehost_from_rpc(id=self.id1)

        self.headers = {'X-Roles': 'admin'}

        self.trusts = trusts
        self.patch(self.trusts, 'create_trust').return_value = fake_trust()

    def test_create_one(self):
        response = self.post_json(self.path, self.fake_computehost_body,
                                  headers=self.headers)
        self.assertEqual(201, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(self.fake_computehost, response.json)

    def test_create_wrong_attr(self):
        expected = {
            "error_name": 400,
            "error_message": "Invalid input for field/attribute name. ",
            "error_code": 400
        }

        response = self.post_json(self.path,
                                  fake_computehost_request_body(name=1),
                                  expect_errors=True, headers=self.headers)
        self.assertEqual(400, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected["error_name"], response.json["error_name"])
        self.assertTrue(expected["error_message"]
                        in response.json["error_message"])
        self.assertEqual(expected["error_code"], response.json["error_code"])

    def test_create_with_empty_body(self):
        expected = {
            "error_name": 500,
            "error_message": "'NoneType' object has no attribute 'as_dict'",
            "error_code": 500
        }

        response = self.post_json(self.path, None, expect_errors=True,
                                  headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_empty_response(self):
        expected = {
            'error_code': 500,
            'error_message': "Host can't be created",
            'error_name': 500
        }
        self.patch(self.hosts_rpcapi, 'create_computehost').return_value = None
        response = self.post_json(self.path, self.fake_computehost_body,
                                  expect_errors=True, headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_rpc_exception_create(self):
        def fake_create_computehost(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': u"Nah...",
            'error_name': 500
        }
        self.patch(
            self.hosts_rpcapi, 'create_computehost'
        ).side_effect = fake_create_computehost
        response = self.post_json(self.path, self.fake_computehost_body,
                                  expect_errors=True, headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestUpdateHost(api.APITest):

    def setUp(self):
        super(TestUpdateHost, self).setUp()

        self.id1 = str('1')
        self.fake_computehost = fake_computehost(id=self.id1, name='updated')
        self.fake_computehost_body = fake_computehost_request_body(
            exclude=['reservations', 'events'],
            id=self.id1,
            name='updated'
        )
        self.path = '/os-hosts/{0}'.format(self.id1)
        self.patch(
            self.hosts_rpcapi, 'update_computehost'
        ).return_value = fake_computehost_from_rpc(id=self.id1, name='updated')

        self.headers = {'X-Roles': 'admin'}

    def test_update_one(self):
        response = self.put_json(self.path, fake_computehost_request_body(
                                 exclude=['trust_id']),
                                 headers=self.headers)
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(self.fake_computehost, response.json)

    def test_update_with_empty_body(self):
        expected = {
            "error_name": 500,
            "error_message": "'NoneType' object has no attribute 'as_dict'",
            "error_code": 500
        }

        response = self.put_json(self.path, None, expect_errors=True,
                                 headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_empty_response(self):
        expected = {
            'error_code': 404,
            'error_message': "Object with {{'host_id': "
                             "{0}}} not found".format(self.id1),
            'error_name': 404
        }
        self.patch(self.hosts_rpcapi, 'update_computehost').return_value = None
        response = self.put_json(self.path, self.fake_computehost_body,
                                 expect_errors=True, headers=self.headers)
        self.assertEqual(404, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_rpc_exception_update(self):
        def fake_update_computehost(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': u"Nah...",
            'error_name': 500
        }
        self.patch(
            self.hosts_rpcapi, 'update_computehost'
        ).side_effect = fake_update_computehost
        response = self.put_json(self.path, self.fake_computehost_body,
                                 expect_errors=True, headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestDeleteHost(api.APITest):

    def setUp(self):
        super(TestDeleteHost, self).setUp()

        self.id1 = str('1')
        self.path = '/os-hosts/{0}'.format(self.id1)
        self.patch(self.hosts_rpcapi, 'delete_computehost')
        self.headers = {'X-Roles': 'admin'}

    def test_delete_one(self):
        response = self.delete(self.path, headers=self.headers)
        self.assertEqual(204, response.status_int)
        self.assertIsNone(response.content_type)
        self.assertEqual(b'', response.body)

    def test_delete_not_existing_computehost(self):
        def fake_delete_computehost(*args, **kwargs):
            raise TypeError("Nah...")
        expected = {
            'error_code': 404,
            'error_message': "not found",
            'error_name': 404
        }
        self.patch(
            self.hosts_rpcapi, 'delete_computehost'
        ).side_effect = fake_delete_computehost
        response = self.delete(self.path, expect_errors=True,
                               headers=self.headers)
        self.assertEqual(404, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected["error_name"], response.json["error_name"])
        self.assertTrue(expected["error_message"]
                        in response.json["error_message"])
        self.assertEqual(expected["error_code"], response.json["error_code"])

    def test_rpc_exception_delete(self):
        def fake_delete_computehost(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': u"Nah...",
            'error_name': 500
        }
        self.patch(
            self.hosts_rpcapi, 'delete_computehost'
        ).side_effect = fake_delete_computehost
        response = self.delete(self.path, expect_errors=True,
                               headers=self.headers)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

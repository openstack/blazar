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
Tests for API /leases/ methods
"""
from oslo_utils import uuidutils

from blazar.tests import api
from blazar.utils import trusts


def fake_lease(**kw):
    return {
        'id': kw.get('id', '2bb8720a-0873-4d97-babf-0d906851a1eb'),
        'name': kw.get('name', 'lease_test'),
        'start_date': kw.get('start_date', '2014-01-01 01:23'),
        'end_date': kw.get('end_date', '2014-02-01 13:37'),
        'trust_id': kw.get('trust_id',
                           '35b17138b3644e6aa1318f3099c5be68'),
        'user_id': kw.get('user_id', 'efd8780712d24b389c705f5c2ac427ff'),
        'project_id': kw.get('project_id',
                             'bd9431c18d694ad3803a8d4a6b89fd36'),
        'reservations': kw.get('reservations', [
            {
                'resource_id': '1234',
                'resource_type': 'virtual:instance'
            }
        ]),
        'events': kw.get('events', []),
        'status': kw.get('status', 'ACTIVE'),
    }


def fake_lease_request_body(exclude=[], **kw):
    exclude.append('id')
    exclude.append('trust_id')
    exclude.append('user_id')
    exclude.append('project_id')
    exclude.append('status')
    lease_body = fake_lease(**kw)
    return dict((key, lease_body[key])
                for key in lease_body if key not in exclude)


def fake_trust(id=fake_lease()['trust_id']):
    return type('Trust', (), {
        'id': id,
    })


class TestIncorrectLeaseFromRPC(api.APITest):

    def setUp(self):
        super(TestIncorrectLeaseFromRPC, self).setUp()

        self.path = '/leases'
        self.patch(
            self.rpcapi, 'list_leases').return_value = [fake_lease(id=1)]

    def test_bad_list(self):
        expected = {
            'error_code': 400,
            'error_message': "Invalid input for field/attribute id. "
                             "Value: '1'. Value should be UUID format",
            'error_name': 400
        }
        response = self.get_json(self.path, expect_errors=True)
        self.assertEqual(400, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestListLeases(api.APITest):

    def setUp(self):
        super(TestListLeases, self).setUp()

        self.fake_lease = fake_lease()
        self.path = '/leases'
        self.patch(self.rpcapi, 'list_leases').return_value = []

    def test_empty(self):
        response = self.get_json(self.path)
        self.assertEqual([], response)

    def test_one(self):
        self.patch(self.rpcapi, 'list_leases').return_value = [self.fake_lease]
        response = self.get_json(self.path)
        self.assertEqual([self.fake_lease], response)

    def test_multiple(self):
        id1 = str(uuidutils.generate_uuid())
        id2 = str(uuidutils.generate_uuid())
        self.patch(
            self.rpcapi, 'list_leases').return_value = [
                fake_lease(id=id1),
                fake_lease(id=id2)
            ]
        response = self.get_json(self.path)
        self.assertEqual([fake_lease(id=id1), fake_lease(id=id2)], response)

    def test_rpc_exception_list(self):
        def fake_list_leases(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.rpcapi, 'list_leases').side_effect = fake_list_leases
        response = self.get_json(self.path, expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestShowLease(api.APITest):

    def setUp(self):
        super(TestShowLease, self).setUp()

        self.id1 = str(uuidutils.generate_uuid())
        self.fake_lease = fake_lease(id=self.id1)
        self.path = '/leases/{0}'.format(self.id1)
        self.patch(self.rpcapi, 'get_lease').return_value = self.fake_lease

    def test_one(self):
        response = self.get_json(self.path)
        self.assertEqual(self.fake_lease, response)

    def test_empty(self):
        expected = {
            'error_code': 404,
            'error_message': "not found",
            'error_name': 404
        }
        self.patch(self.rpcapi, 'get_lease').return_value = None
        response = self.get_json(self.path, expect_errors=True)
        self.assertEqual(404, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected["error_name"], response.json["error_name"])
        self.assertTrue(expected["error_message"]
                        in response.json["error_message"])
        self.assertEqual(expected["error_code"], response.json["error_code"])

    def test_rpc_exception_get(self):
        def fake_get_lease(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.rpcapi, 'get_lease').side_effect = fake_get_lease
        response = self.get_json(self.path, expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestCreateLease(api.APITest):

    def setUp(self):
        super(TestCreateLease, self).setUp()

        self.id1 = str(uuidutils.generate_uuid())
        self.fake_lease = fake_lease(id=self.id1)
        self.fake_lease_body = fake_lease_request_body(id=self.id1)
        self.path = '/leases'
        self.patch(self.rpcapi, 'create_lease').return_value = self.fake_lease

        self.trusts = trusts
        self.patch(self.trusts, 'create_trust').return_value = fake_trust()

    def test_create_one(self):
        response = self.post_json(self.path, self.fake_lease_body)
        self.assertEqual(201, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(self.fake_lease, response.json)

    def test_create_wrong_attr(self):
        expected = {
            "error_name": 400,
            "error_message": "Invalid input for field/attribute name.",
            "error_code": 400
        }

        response = self.post_json(self.path, fake_lease_request_body(name=1),
                                  expect_errors=True)
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

        response = self.post_json(self.path, None, expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_empty_response(self):
        expected = {
            'error_code': 500,
            'error_message': "Lease can't be created",
            'error_name': 500
        }
        self.patch(self.rpcapi, 'create_lease').return_value = None
        response = self.post_json(self.path, self.fake_lease_body,
                                  expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_rpc_exception_create(self):
        def fake_create_lease(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.rpcapi, 'create_lease').side_effect = fake_create_lease
        response = self.post_json(self.path, self.fake_lease_body,
                                  expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestUpdateLease(api.APITest):

    def setUp(self):
        super(TestUpdateLease, self).setUp()

        self.id1 = str(uuidutils.generate_uuid())
        self.fake_lease = fake_lease(id=self.id1, name='updated')
        self.fake_lease_body = fake_lease_request_body(
            exclude=['reservations', 'events'],
            id=self.id1,
            name='updated'
        )
        self.path = '/leases/{0}'.format(self.id1)
        self.patch(self.rpcapi, 'update_lease').return_value = self.fake_lease

    def test_update_one(self):
        response = self.put_json(self.path, self.fake_lease_body)
        self.assertEqual(200, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(self.fake_lease, response.json)

    def test_update_one_with_extra_attrs(self):
        expected = {
            "error_name": 500,
            "error_message": "Only name changing, dates and before "
                             "end notifications may be proceeded.",
            "error_code": 500
        }

        response = self.put_json(self.path, fake_lease_request_body(name='a'),
                                 expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_update_with_empty_body(self):
        expected = {
            "error_name": 500,
            "error_message": "'NoneType' object has no attribute 'as_dict'",
            "error_code": 500
        }

        response = self.put_json(self.path, None, expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

    def test_empty_response(self):
        expected = {
            'error_code': 404,
            'error_message': "not found",
            'error_name': 404
        }
        self.patch(self.rpcapi, 'update_lease').return_value = None
        response = self.put_json(self.path, self.fake_lease_body,
                                 expect_errors=True)
        self.assertEqual(404, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected["error_name"], response.json["error_name"])
        self.assertTrue(expected["error_message"]
                        in response.json["error_message"])
        self.assertEqual(expected["error_code"], response.json["error_code"])

    def test_rpc_exception_update(self):
        def fake_update_lease(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.rpcapi, 'update_lease').side_effect = fake_update_lease
        response = self.put_json(self.path, self.fake_lease_body,
                                 expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)


class TestDeleteLease(api.APITest):

    def setUp(self):
        super(TestDeleteLease, self).setUp()

        self.id1 = str(uuidutils.generate_uuid())
        self.path = '/leases/{0}'.format(self.id1)
        self.patch(self.rpcapi, 'delete_lease')

    def test_delete_one(self):
        response = self.delete(self.path)
        self.assertEqual(204, response.status_int)
        self.assertIsNone(response.content_type)
        self.assertEqual(b'', response.body)

    def test_delete_not_existing_lease(self):
        def fake_delete_lease(*args, **kwargs):
            raise TypeError("Nah...")
        expected = {
            'error_code': 404,
            'error_message': "not found",
            'error_name': 404
        }
        self.patch(
            self.rpcapi, 'delete_lease').side_effect = fake_delete_lease
        response = self.delete(self.path, expect_errors=True)
        self.assertEqual(404, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected["error_name"], response.json["error_name"])
        self.assertTrue(expected["error_message"]
                        in response.json["error_message"])
        self.assertEqual(expected["error_code"], response.json["error_code"])

    def test_rpc_exception_delete(self):
        def fake_delete_lease(*args, **kwargs):
            raise Exception("Nah...")
        expected = {
            'error_code': 500,
            'error_message': "Nah...",
            'error_name': 500
        }
        self.patch(
            self.rpcapi, 'delete_lease').side_effect = fake_delete_lease
        response = self.delete(self.path, expect_errors=True)
        self.assertEqual(500, response.status_int)
        self.assertEqual('application/json', response.content_type)
        self.assertEqual(expected, response.json)

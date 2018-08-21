# Copyright (c) 2018 University of Chicago
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

import datetime

# import eventlet
import mock

from oslo_config import cfg
# from six.moves import reload_module
# from stevedore import enabled
# import testtools

# from blazar import context
# from blazar.db import api as db_api
# from blazar.db import exceptions as db_ex
from blazar import exceptions
# from blazar.manager import exceptions as manager_ex
from blazar.manager import enforcement
from blazar import tests
from blazar.utils.openstack import keystone as keystone_client
# from blazar.notification import api as notifier_api
# from blazar.plugins import base
# from blazar.plugins import dummy_vm_plugin
# from blazar.plugins.oshosts import host_plugin
# from blazar import status

# from blazar.utils.openstack import base as base_utils
# from blazar.utils import trusts


class UsageEnforcementTestCase(tests.TestCase):
    def setUp(self):
        super(UsageEnforcementTestCase, self).setUp()

        self.cfg = cfg
        self.enforcement = enforcement.UsageEnforcer()
        self.addCleanup(self.cfg.CONF.clear_override,
                        'default_max_lease_duration',
                        group='enforcement')

        self.keystone_client = keystone_client
        self.keystone = self.patch(
            self.keystone_client, 'BlazarKeystoneClient').return_value

        def name_from_id(id):
            if id.startswith('id_'):
                name = id[3:]
            else:
                name = id
            keystone_obj = mock.Mock()
            keystone_obj.name = name
            return keystone_obj

        self.patch(self.keystone.users, 'get')
        self.patch(self.keystone.projects, 'get')
        self.keystone.users.get.side_effect = name_from_id
        self.keystone.projects.get.side_effect = name_from_id

        self.patch(self.enforcement, 'get_lease_exception')
        self.enforcement.get_lease_exception.return_value = None

    def test_new_lease_against_default_limit(self):
        self.cfg.CONF.set_override('default_max_lease_duration', 86400,
                                   group='enforcement')

        lease_values = {
            'start_date': datetime.datetime(2015, 12, 1, 20, 0),
            'end_date': datetime.datetime(2015, 12, 2, 20, 0),
            'user_id': 'id_user_foo',
            'project_id': 'id_project_foo'
        }
        self.assertTrue(
            self.enforcement.check_lease_duration(
                lease_values, lease=None))

        lease_values = {
            'start_date': datetime.datetime(2015, 12, 1, 20, 0),
            'end_date': datetime.datetime(2015, 12, 2, 20, 1),
            'user_id': 'id_user_foo',
            'project_id': 'id_project_foo'
        }
        self.assertRaises(
            exceptions.NotAuthorized, self.enforcement.check_lease_duration,
            lease_values, lease=None)

    def test_new_lease_against_project_limits(self):
        self.cfg.CONF.set_override('default_max_lease_duration', 86400,
                                   group='enforcement')
        self.enforcement.project_max_lease_durations = {
            'project_bar': 86400 * 2,
        }

        lease_values = {
            'start_date': datetime.datetime(2015, 12, 1, 20, 0),
            'end_date': datetime.datetime(2015, 12, 3, 20, 0),
            'user_id': 'id_user_foo',
            'project_id': 'id_project_bar'
        }
        self.assertTrue(
            self.enforcement.check_lease_duration(
                lease_values, lease=None))
        lease_values = {
            'start_date': datetime.datetime(2015, 12, 1, 20, 0),
            'end_date': datetime.datetime(2015, 12, 3, 20, 1),
            'user_id': 'id_user_foo',
            'project_id': 'id_project_bar'
        }
        self.assertRaises(
            exceptions.NotAuthorized, self.enforcement.check_lease_duration,
            lease_values, lease=None)

        lease_values = {
            'start_date': datetime.datetime(2015, 12, 1, 20, 0),
            'end_date': datetime.datetime(2015, 12, 2, 20, 1),
            'user_id': 'id_user_foo',
            'project_id': 'id_project_foo'
        }
        self.assertRaises(
            exceptions.NotAuthorized, self.enforcement.check_lease_duration,
            lease_values, lease=None)

# Copyright 2014 OpenStack Foundation
# Copyright 2014 Mirantis Inc
#
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

"""
Tests for database migrations. This test case reads the configuration
file test_migrations.conf for database connection settings
to use in the tests. For each connection found in the config file,
the test case runs a series of test cases to ensure that migrations work
properly.

There are also "opportunistic" tests for both mysql and postgresql in here,
which allows testing against mysql and pg in a properly configured unit
test environment.

For the opportunistic testing you need to set up a db named 'openstack_citest'
with user 'openstack_citest' and password 'openstack_citest' on localhost.
The test will then use that db and u/p combo to run the tests.

For postgres on Ubuntu this can be done with the following commands:

sudo -u postgres psql
postgres=# create user openstack_citest with createdb login password
      'openstack_citest';
postgres=# create database openstack_citest with owner openstack_citest;

"""

from oslo_config import cfg
import sqlalchemy

from blazar.tests.db import migration

CONF = cfg.CONF


class TestMigrations(migration.BaseWalkMigrationTestCase,
                     migration.CommonTestsMixIn):
    """Test alembic migrations."""

    # This variables are used by BaseWalkMigrationTestCase in order to perform
    # the opportunistic testing
    USER = "openstack_citest"
    PASSWD = "openstack_citest"
    DATABASE = "openstack_citest"

    def get_table(self, engine, name):
        """Returns an sqlalchemy table dynamically from db.

        Needed because the models don't work for us in migrations
        as models will be far out of sync with the current data.
        """
        metadata = sqlalchemy.MetaData()
        metadata.bind = engine
        return sqlalchemy.Table(name, metadata, autoload_with=metadata.bind)

    def assertTableExists(self, engine, table):
        metadata = sqlalchemy.MetaData()
        metadata.reflect(bind=engine)
        self.assertIn(table, metadata.tables)

    def assertColumnExists(self, engine, table, column):
        t = self.get_table(engine, table)
        self.assertIn(column, t.c)

    def assertColumnsExists(self, engine, table, columns):
        for column in columns:
            self.assertColumnExists(engine, table, column)

    def assertColumnCount(self, engine, table, columns):
        t = self.get_table(engine, table)
        self.assertEqual(len(t.columns), len(columns))

    def assertColumnNotExists(self, engine, table, column):
        t = self.get_table(engine, table)
        self.assertNotIn(column, t.c)

    def assertIndexExists(self, engine, table, index):
        t = self.get_table(engine, table)
        index_names = [idx.name for idx in t.indexes]
        self.assertIn(index, index_names)

    def assertIndexMembers(self, engine, table, index, members):
        self.assertIndexExists(engine, table, index)

        t = self.get_table(engine, table)
        index_columns = None
        for idx in t.indexes:
            if idx.name == index:
                index_columns = idx.columns.keys()
                break

        self.assertEqual(sorted(members), sorted(index_columns))

    def _check_0_1(self, engine, data):
        self.assertTableExists(engine, 'computehosts')
        self.assertTableExists(engine, 'leases')
        self.assertTableExists(engine, 'reservations')
        self.assertTableExists(engine, 'computehost_extra_capabilities')
        self.assertTableExists(engine, 'events')
        self.assertTableExists(engine, 'computehost_allocations')
        self.assertTableExists(engine, 'computehost_reservations')

    def _check_10e34bba18e8(self, engine, data):
        self.assertColumnExists(engine, 'computehosts', 'service_name')

    def _check_2bcfe76b0474(self, engine, data):
        self.assertColumnExists(engine, 'leases', 'project_id')
        self.assertColumnNotExists(engine, 'leases', 'tenant_id')

    def _pre_upgrade_1fd6c2eded89(self, engine):
        data = [{
            'id': '1',
            'hypervisor_hostname': 'host01',
            'hypervisor_type': 'QEMU',
            'hypervisor_version': 1000000,
            'service_name': 'host01',
            'vcpus': 1,
            'memory_mb': 8192,
            'local_gb': 50,
            'cpu_info': "{\"vendor\": \"Intel\", \"model\": \"qemu32\", "
                        "\"arch\": \"x86_64\", \"features\": [],"
                        " \"topology\": {\"cores\": 1}}",
            'extra_capas': {'vgpus': 2}},
            {'id': '2',
             'hypervisor_hostname': 'host01',
             'hypervisor_type': 'QEMU',
             'hypervisor_version': 1000000,
             'service_name': 'host02',
             'vcpus': 1,
             'memory_mb': 8192,
             'local_gb': 50,
             'cpu_info': "{\"vendor\": \"Intel\", \"model\": \"qemu32\", "
                         "\"arch\": \"x86_64\", \"features\": [],"
                         " \"topology\": {\"cores\": 1}}",
             'extra_capas': {'vgpus': 2}}]
        computehosts_table = self.get_table(engine, 'computehosts')
        # pylint: disable=E1120
        engine.execute(computehosts_table.insert(), data)
        return data

    def _check_1fd6c2eded89(self, engine, data):
        self.assertColumnExists(engine, 'computehosts', 'trust_id')

        metadata = sqlalchemy.MetaData()
        metadata.bind = engine
        computehosts_table = self.get_table(engine, 'computehosts')

        all_computehosts = computehosts_table.select().execute()
        for computehost in all_computehosts:
            self.assertIn(computehost.trust_id, ['', None])

        data = {'id': '3',
                'hypervisor_hostname': 'host01',
                'hypervisor_type': 'QEMU',
                'hypervisor_version': 1000000,
                'service_name': 'host02',
                'vcpus': 1,
                'memory_mb': 8192,
                'local_gb': 50,
                'cpu_info': "{\"vendor\": \"Intel\", \"model\": \"qemu32\", "
                            "\"arch\": \"x86_64\", \"features\": [],"
                            " \"topology\": {\"cores\": 1}}",
                'extra_capas': {'vgpus': 2},
                'trust_id': None}

        if engine.name != 'sqlite':
            # pylint: disable=E1120
            self.assertRaises(sqlalchemy.exc.DBAPIError,
                              engine.execute,
                              computehosts_table.insert(),
                              data)

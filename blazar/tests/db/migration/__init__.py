# Copyright 2010-2011 OpenStack Foundation
# Copyright 2012-2013 IBM Corp.
# All Rights Reserved.
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
#
#
# Ripped off from Nova's test_migrations.py
# The only difference between Nova and this code is usage of alembic instead
# of sqlalchemy migrations.
#
# There is an ongoing work to extact similar code to oslo incubator. Once it is
# extracted we'll be able to remove this file and use oslo.

import configparser
import io
import os
import subprocess
from urllib import parse as urlparse

from alembic import command
from alembic import config as alembic_config
from alembic import migration
from oslo_concurrency import lockutils
from oslo_config import cfg
from oslo_log import log as logging
import sqlalchemy
import sqlalchemy.exc

import blazar.db.migration
from blazar import tests

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

synchronized = lockutils.synchronized_with_prefix('blazar-')


def _get_connect_string(backend, user, passwd, database):
    """Establish connection

    Try to get a connection with a very specific set of values, if we get
    these then we'll run the tests, otherwise they are skipped
    """
    if backend == "postgres":
        backend = "postgresql+psycopg2"
    elif backend == "mysql":
        backend = "mysql+mysqldb"
    else:
        raise Exception("Unrecognized backend: '%s'" % backend)

    return ("%s://%s:%s@localhost/%s" % (backend, user, passwd, database))


def _is_backend_avail(backend, user, passwd, database):
    try:
        connect_uri = _get_connect_string(backend, user, passwd, database)
        engine = sqlalchemy.create_engine(connect_uri)
        connection = engine.connect()
    except Exception:
        # intentionally catch all to handle exceptions even if we don't
        # have any backend code loaded.
        return False
    else:
        connection.close()
        engine.dispose()
        return True


def _have_mysql(user, passwd, database):
    present = os.environ.get('BLAZAR_MYSQL_PRESENT')
    if present is None:
        return _is_backend_avail('mysql', user, passwd, database)
    return present.lower() in ('', 'true')


def _have_postgresql(user, passwd, database):
    present = os.environ.get('BLAZAR_TEST_POSTGRESQL_PRESENT')
    if present is None:
        return _is_backend_avail('postgres', user, passwd, database)
    return present.lower() in ('', 'true')


def get_mysql_connection_info(conn_pieces):
    database = conn_pieces.path.strip('/')
    loc_pieces = conn_pieces.netloc.split('@')
    host = loc_pieces[1]
    auth_pieces = loc_pieces[0].split(':')
    user = auth_pieces[0]
    password = ""
    if len(auth_pieces) > 1:
        if auth_pieces[1].strip():
            password = "-p\"%s\"" % auth_pieces[1]

    return (user, password, database, host)


def get_pgsql_connection_info(conn_pieces):
    database = conn_pieces.path.strip('/')
    loc_pieces = conn_pieces.netloc.split('@')
    host = loc_pieces[1]

    auth_pieces = loc_pieces[0].split(':')
    user = auth_pieces[0]
    password = ""
    if len(auth_pieces) > 1:
        password = auth_pieces[1].strip()

    return (user, password, database, host)


class CommonTestsMixIn(object):
    """Reasons to create Mixin

    BaseMigrationTestCase is effectively an abstract class,
    meant to be derived from and not directly tested against; that's why these
    `test_` methods need to be on a Mixin, so that they won't be picked up
    as valid tests for BaseMigrationTestCase.
    """
    def test_walk_versions(self):
        for key, engine in self.engines.items():
            # We start each walk with a completely blank slate.
            self._reset_database(key)
            self._walk_versions(engine, self.snake_walk, self.downgrade)

    def test_mysql_opportunistically(self):
        self._test_mysql_opportunistically()

    def test_mysql_connect_fail(self):
        """MySQL graceful fail check

        Test that we can trigger a mysql connection failure and we fail
        gracefully to ensure we don't break people without mysql
        """
        if _is_backend_avail('mysql', "openstack_cifail", self.PASSWD,
                             self.DATABASE):
            self.fail("Shouldn't have connected")

    def test_postgresql_opportunistically(self):
        self._test_postgresql_opportunistically()

    def test_postgresql_connect_fail(self):
        """PostgreSQL graceful fail check

        Test that we can trigger a postgres connection failure and we fail
        gracefully to ensure we don't break people without postgres
        """
        if _is_backend_avail('postgres', "openstack_cifail", self.PASSWD,
                             self.DATABASE):
            self.fail("Shouldn't have connected")


class BaseMigrationTestCase(tests.TestCase):
    """Base class for migrations

    Base class for testing migrations and migration utils. This sets up
    and configures the databases to run tests against.
    """

    # NOTE(jhesketh): It is expected that tests clean up after themselves.
    # This is necessary for concurrency to allow multiple tests to work on
    # one database.
    # The full migration walk tests however do call the old _reset_databases()
    # to throw away whatever was there so they need to operate on their own
    # database that we know isn't accessed concurrently.
    # Hence, BaseWalkMigrationTestCase overwrites the engine list.

    USER = None
    PASSWD = None
    DATABASE = None

    TIMEOUT_SCALING_FACTOR = 2

    def __init__(self, *args, **kwargs):
        super(BaseMigrationTestCase, self).__init__(*args, **kwargs)

        self.DEFAULT_CONFIG_FILE = os.path.join(
            os.path.dirname(__file__),
            'test_migrations.conf')
        # Test machines can set the BLAZAR_TEST_MIGRATIONS_CONF variable
        # to override the location of the config file for migration testing
        self.CONFIG_FILE_PATH = os.environ.get(
            'BLAZAR_TEST_MIGRATIONS_CONF',
            self.DEFAULT_CONFIG_FILE)

        self.ALEMBIC_CONFIG = alembic_config.Config(
            os.path.join(os.path.dirname(blazar.db.migration.__file__),
                         'alembic.ini')
        )

        self.ALEMBIC_CONFIG.blazar_config = CONF

        self.snake_walk = False
        self.downgrade = False
        self.test_databases = {}
        self.migration = None
        self.migration_api = None

    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()
        self._load_config()

    def _load_config(self):
        # Load test databases from the config file. Only do this
        # once. No need to re-run this on each test...
        LOG.debug('config_path is %s', self.CONFIG_FILE_PATH)
        if os.path.exists(self.CONFIG_FILE_PATH):
            cp = configparser.RawConfigParser()
            try:
                cp.read(self.CONFIG_FILE_PATH)
                config = cp.options('unit_tests')
                for key in config:
                    self.test_databases[key] = cp.get('unit_tests', key)
                self.snake_walk = cp.getboolean('walk_style', 'snake_walk')
                self.downgrade = cp.getboolean('walk_style', 'downgrade')

            except configparser.ParsingError as e:
                self.fail("Failed to read test_migrations.conf config "
                          "file. Got error: %s" % e)
        else:
            self.fail("Failed to find test_migrations.conf config "
                      "file.")

        self.engines = {}
        for key, value in self.test_databases.items():
            self.engines[key] = sqlalchemy.create_engine(value)

        # NOTE(jhesketh): We only need to make sure the databases are created
        # not necessarily clean of tables.
        self._create_databases()

    def execute_cmd(self, cmd=None):
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        output = process.communicate()[0]
        LOG.debug(output)
        self.assertEqual(0, process.returncode,
                         "Failed to run: %s\n%s" % (cmd, output))

    @synchronized('pgadmin', external=True, lock_path='/tmp')
    def _reset_pg(self, conn_pieces):
        (user, password, database, host) = (
            get_pgsql_connection_info(conn_pieces))
        os.environ['PGPASSWORD'] = password
        os.environ['PGUSER'] = user
        # note(boris-42): We must create and drop database, we can't
        # drop database which we have connected to, so for such
        # operations there is a special database template1.
        sqlcmd = ("psql -w -U %(user)s -h %(host)s -c"
                  " '%(sql)s' -d template1")
        sqldict = {'user': user, 'host': host}

        sqldict['sql'] = ("drop database if exists %s;") % database
        droptable = sqlcmd % sqldict
        self.execute_cmd(droptable)

        sqldict['sql'] = ("create database %s;") % database
        createtable = sqlcmd % sqldict
        self.execute_cmd(createtable)

        os.unsetenv('PGPASSWORD')
        os.unsetenv('PGUSER')

    @synchronized('mysql', external=True, lock_path='/tmp')
    def _reset_mysql(self, conn_pieces):
        # We can execute the MySQL client to destroy and re-create
        # the MYSQL database, which is easier and less error-prone
        # than using SQLAlchemy to do this via MetaData...trust me.
        (user, password, database, host) = (
            get_mysql_connection_info(conn_pieces))
        sql = ("drop database if exists %(database)s; "
               "create database %(database)s;" % {'database': database})
        cmd = ("mysql -u \"%(user)s\" %(password)s -h %(host)s -e \"%(sql)s\""
               % {'user': user, 'password': password,
                  'host': host, 'sql': sql})
        self.execute_cmd(cmd)

    @synchronized('sqlite', external=True, lock_path='/tmp')
    def _reset_sqlite(self, conn_pieces):
        # We can just delete the SQLite database, which is
        # the easiest and cleanest solution
        db_path = conn_pieces.path.strip('/')
        if os.path.exists(db_path):
            os.unlink(db_path)
        # No need to recreate the SQLite DB. SQLite will
        # create it for us if it's not there...

    def _create_databases(self):
        """Create all configured databases as needed."""
        for key, engine in self.engines.items():
            self._create_database(key)

    def _create_database(self, key):
        """Create database if it doesn't exist."""
        conn_string = self.test_databases[key]
        conn_pieces = urlparse.urlparse(conn_string)

        if conn_string.startswith('mysql'):
            (user, password, database, host) = (
                get_mysql_connection_info(conn_pieces))
            sql = "create database if not exists %s;" % database
            cmd = ("mysql -u \"%(user)s\" %(password)s -h %(host)s "
                   "-e \"%(sql)s\"" % {'user': user, 'password': password,
                                       'host': host, 'sql': sql})
            self.execute_cmd(cmd)
        elif conn_string.startswith('postgresql'):
            (user, password, database, host) = (
                get_pgsql_connection_info(conn_pieces))
            os.environ['PGPASSWORD'] = password
            os.environ['PGUSER'] = user

            sqlcmd = ("psql -w -U %(user)s -h %(host)s -c"
                      " '%(sql)s' -d template1 -A -t")

            sql = (("select count(*) from pg_database WHERE datname = '%s'")
                   % database)

            check_database = sqlcmd % {'user': user, 'host': host, 'sql': sql}
            process = subprocess.Popen(check_database, shell=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            output = process.communicate()[0]
            if output == '1':
                sql = ("create database %s;") % database
                create_database = sqlcmd % {'user': user,
                                            'host': host, 'sql': sql}
                self.execute_cmd(create_database)

            os.unsetenv('PGPASSWORD')
            os.unsetenv('PGUSER')

    def _reset_databases(self):
        """Reset all configured databases."""
        for key, engine in self.engines.items():
            self._reset_database(key)

    def _reset_database(self, key):
        """Reset specific database."""
        engine = self.engines[key]
        conn_string = self.test_databases[key]
        conn_pieces = urlparse.urlparse(conn_string)
        engine.dispose()
        if conn_string.startswith('sqlite'):
            self._reset_sqlite(conn_pieces)
        elif conn_string.startswith('mysql'):
            self._reset_mysql(conn_pieces)
        elif conn_string.startswith('postgresql'):
            self._reset_pg(conn_pieces)


class BaseWalkMigrationTestCase(BaseMigrationTestCase):
    """BaseWalkMigrationTestCase description

    BaseWalkMigrationTestCase loads in an alternative set of databases for
    testing against. This is necessary as the default databases can run tests
    concurrently without interfering with itself. It is expected that
    databases listed under [migration_dbs] in the configuration are only being
    accessed by one test at a time. Currently only test_walk_versions accesses
    the databases (and is the only method that calls _reset_database() which
    is clearly problematic for concurrency).
    """

    def _load_config(self):
        # Load test databases from the config file. Only do this
        # once. No need to re-run this on each test...
        LOG.debug('config_path is %s', self.CONFIG_FILE_PATH)
        if os.path.exists(self.CONFIG_FILE_PATH):
            cp = configparser.RawConfigParser()
            try:
                cp.read(self.CONFIG_FILE_PATH)
                config = cp.options('migration_dbs')
                for key in config:
                    self.test_databases[key] = cp.get('migration_dbs', key)
                self.snake_walk = cp.getboolean('walk_style', 'snake_walk')
                self.downgrade = cp.getboolean('walk_style', 'downgrade')
            except configparser.ParsingError as e:
                self.fail("Failed to read test_migrations.conf config "
                          "file. Got error: %s" % e)
        else:
            self.fail("Failed to find test_migrations.conf config "
                      "file.")

        self.engines = {}
        for key, value in self.test_databases.items():
            self.engines[key] = sqlalchemy.create_engine(value)

        self._create_databases()

    def _configure(self, engine):
        """Configure description

        For each type of repository we should do some of configure steps.
        For migrate_repo we should set under version control our database.
        For alembic we should configure database settings. For this goal we
        should use oslo.config and openstack.commom.db.sqlalchemy.session with
        database functionality (reset default settings).
        """
        CONF.set_override('connection', str(engine.url), group='database')

    def _test_mysql_opportunistically(self):
        # Test that table creation on mysql only builds InnoDB tables
        if not _have_mysql(self.USER, self.PASSWD, self.DATABASE):
            self.skipTest("mysql not available")
        # add this to the global lists to make reset work with it, it's removed
        # automatically in tearDown so no need to clean it up here.
        connect_string = _get_connect_string(
            "mysql", self.USER, self.PASSWD, self.DATABASE)
        (user, password, database, host) = (
            get_mysql_connection_info(urlparse.urlparse(connect_string)))
        engine = sqlalchemy.create_engine(connect_string)
        self.engines[database] = engine
        self.test_databases[database] = connect_string

        # build a fully populated mysql database with all the tables
        self._reset_database(database)
        self._walk_versions(engine, self.snake_walk, self.downgrade)

        connection = engine.connect()
        # sanity check
        total = connection.execute(sqlalchemy.text(
                                   "SELECT count(*) "
                                   "from information_schema.TABLES "
                                   "where TABLE_SCHEMA='%(database)s'" %
                                   {'database': database}))
        self.assertTrue(total.scalar() > 0, "No tables found. Wrong schema?")

        connection.close()

        del self.engines[database]
        del self.test_databases[database]

    def _test_postgresql_opportunistically(self):
        # Test postgresql database migration walk
        if not _have_postgresql(self.USER, self.PASSWD, self.DATABASE):
            self.skipTest("postgresql not available")
        # add this to the global lists to make reset work with it, it's removed
        # automatically in tearDown so no need to clean it up here.
        connect_string = _get_connect_string(
            "postgres", self.USER, self.PASSWD, self.DATABASE)
        engine = sqlalchemy.create_engine(connect_string)
        (user, password, database, host) = (
            get_mysql_connection_info(urlparse.urlparse(connect_string)))
        self.engines[database] = engine
        self.test_databases[database] = connect_string

        # build a fully populated postgresql database with all the tables
        self._reset_database(database)
        self._walk_versions(engine, self.snake_walk, self.downgrade)
        del self.engines[database]
        del self.test_databases[database]

    def _alembic_command(self, alembic_command, engine, *args, **kwargs):
        """Alembic command redefine reasons

        Most of alembic command return data into output.
        We should redefine this setting for getting info.
        """
        self.ALEMBIC_CONFIG.stdout = buf = io.StringIO()
        CONF.set_override('connection', str(engine.url), group='database')
        getattr(command, alembic_command)(*args, **kwargs)
        res = buf.getvalue().strip()
        LOG.debug('Alembic command `%(command)s` returns: %(res)s',
                  {'command': alembic_command, 'res': res})
        return res

    def _get_alembic_versions(self, engine):
        """Return list of versions in historical order

        For support of full testing of migrations
        we should have an opportunity to run command step by step for each
        version in repo. This method returns list of alembic_versions by
        historical order.
        """
        full_history = self._alembic_command('history',
                                             engine, self.ALEMBIC_CONFIG)
        # The piece of output data with version can looked as:
        # 'Rev: 17738166b91 (head)' or 'Rev: 43b1a023dfaa'
        alembic_history = [r.split(' ')[1] for r in full_history.split("\n")
                           if r.startswith("Rev")]
        alembic_history.reverse()
        return alembic_history

    def _up_and_down_versions(self, engine):
        """Store versions

        Since alembic version has a random algorithm of generation
        (SA-migrate has an ordered autoincrement naming) we should store
        a tuple of versions (version for upgrade and version for downgrade)
        for successful testing of migrations in up>down>up mode.
        """
        versions = self._get_alembic_versions(engine)
        return list(zip(versions, ['-1'] + versions))

    def _walk_versions(self, engine=None, snake_walk=False,
                       downgrade=True):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        self._configure(engine)
        up_and_down_versions = self._up_and_down_versions(engine)
        for ver_up, ver_down in up_and_down_versions:
            # upgrade -> downgrade -> upgrade
            self._migrate_up(engine, ver_up, with_data=True)
            if snake_walk:
                downgraded = self._migrate_down(engine,
                                                ver_down,
                                                with_data=True,
                                                next_version=ver_up)
                if downgraded:
                    self._migrate_up(engine, ver_up)

        if downgrade:
            # Now walk it back down to 0 from the latest, testing
            # the downgrade paths.
            up_and_down_versions.reverse()
            for ver_up, ver_down in up_and_down_versions:
                # downgrade -> upgrade -> downgrade
                downgraded = self._migrate_down(engine,
                                                ver_down, next_version=ver_up)

                if snake_walk and downgraded:
                    self._migrate_up(engine, ver_up)
                    self._migrate_down(engine, ver_down, next_version=ver_up)

    def _get_version_from_db(self, engine):
        """Return latest version

        For each type of migrate repo latest version from db
        will be returned.
        """
        conn = engine.connect()
        try:
            context = migration.MigrationContext.configure(conn)
            version = context.get_current_revision() or '-1'
        finally:
            conn.close()
        return version

    def _migrate(self, engine, version, cmd):
        """Upgrad/downgrade actual database

        Base method for manipulation with migrate repo.
        It will upgrade or downgrade the actual database.
        """

        self._alembic_command(cmd, engine, self.ALEMBIC_CONFIG, version)

    def _migrate_down(self, engine, version, with_data=False,
                      next_version=None):
        try:
            self._migrate(engine, version, 'downgrade')
        except NotImplementedError:
            # NOTE(sirp): some migrations, namely release-level
            # migrations, don't support a downgrade.
            return False
        self.assertEqual(version, self._get_version_from_db(engine))

        # NOTE(sirp): `version` is what we're downgrading to (i.e. the 'target'
        # version). So if we have any downgrade checks, they need to be run for
        # the previous (higher numbered) migration.
        if with_data:
            post_downgrade = getattr(
                self, "_post_downgrade_%s" % next_version, self._do_nothing)
            if post_downgrade is not self._do_nothing:
                post_downgrade(engine)

        return True

    def _migrate_up(self, engine, version, with_data=False):
        """migrate up to a new version of the db.

        We allow for data insertion and post checks at every
        migration version with special _pre_upgrade_### and
        _check_### functions in the main test.
        """
        # NOTE(sdague): try block is here because it's impossible to debug
        # where a failed data migration happens otherwise
        check_version = version
        try:
            if with_data:
                data = None
                pre_upgrade = getattr(
                    self, "_pre_upgrade_%s" % check_version, None)
                if pre_upgrade:
                    data = pre_upgrade(engine)
            self._migrate(engine, version, 'upgrade')
            self.assertEqual(version, self._get_version_from_db(engine))
            if with_data:
                check = getattr(self, "_check_%s" % check_version, None)
                if check:
                    check(engine, data)
        except Exception:
            LOG.error("Failed to migrate to version %(version)s on engine "
                      "%(engine)s", {'version': version, 'engine': engine})
            raise

    def _do_nothing(self, *args, **kwargs):
        """Workaround for passing the pylint check.

        NOTE(hiro-kobayashi): this method is used by the _migrate_down() to
        prevent 'not-callable' error of the pylint checker.
        """
        pass

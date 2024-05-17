# Copyright 2018 OpenStack Foundation.
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

"""update lease status

Revision ID: 75a74e4539cb
Revises: e66f199a5414
Create Date: 2018-01-23 11:05:56.753579

"""

# revision identifiers, used by Alembic.
revision = '75a74e4539cb'
down_revision = 'e66f199a5414'

from alembic import op
import sqlalchemy as sa


def _get_metadata():
    connection = op.get_bind().engine
    meta = sa.MetaData()
    meta.bind = connection
    return meta


def upgrade():
    def get_query(start_status, end_status):
        start_event_query = (sess.query(event.c.lease_id, event.c.status).
                             filter(event.c.event_type == 'start_lease').
                             subquery('start_t'))
        start_table = sa.orm.aliased(start_event_query)

        end_event_query = (sess.query(event.c.lease_id, event.c.status).
                           filter(event.c.event_type == 'end_lease').
                           subquery('end_t'))
        end_table = sa.orm.aliased(end_event_query)

        query = (sess.query(lease.c.id).
                 join(start_table, lease.c.id == start_table.c.lease_id).
                 join(end_table, lease.c.id == end_table.c.lease_id).
                 filter(
                     sa.and_(start_table.c.status == start_status,
                             end_table.c.status == end_status)))

        return query

    meta = _get_metadata()
    lease = sa.Table('leases', meta, autoload_with=meta.bind)
    event = sa.Table('events', meta, autoload_with=meta.bind)

    Session = sa.orm.sessionmaker()
    sess = Session(bind=meta.bind)

    stable_lease_id = []

    # PENDING Lease
    pending_query = get_query('UNDONE', 'UNDONE')
    for l in pending_query:
        op.execute(
            lease.update().values(status='PENDING').
            where(lease.c.id == l[0]))
        stable_lease_id.append(l[0])

    # ACTIVE Lease
    active_query = get_query('DONE', 'UNDONE')

    for l in active_query:
        op.execute(
            lease.update().values(status='ACTIVE').
            where(lease.c.id == l[0]))
        stable_lease_id.append(l[0])

    # TERMINATED Lease
    terminated_query = get_query('DONE', 'DONE')

    for l in terminated_query:
        op.execute(
            lease.update().values(status='TERMINATED').
            where(lease.c.id == l[0]))
        stable_lease_id.append(l[0])

    # ERROR Lease
    all_query = sess.query(lease.c.id)

    for l in all_query:
        if l[0] not in stable_lease_id:
            op.execute(
                lease.update().values(status='ERROR').
                where(lease.c.id == l[0]))

    sess.close()


def downgrade():
    meta = _get_metadata()
    lease = sa.Table('leases', meta, autoload_with=meta.bind)

    op.execute(
        lease.update().values(status=None))

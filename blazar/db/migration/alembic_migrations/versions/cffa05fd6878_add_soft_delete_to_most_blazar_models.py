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

"""Add soft delete to most Blazar models

Revision ID: cffa05fd6878
Revises: 35b314cd39ee
Create Date: 2018-07-25 12:27:53.163504

"""

# revision identifiers, used by Alembic.
revision = 'cffa05fd6878'
down_revision = 'afd0a1c7748a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('computehost_allocations',
                  sa.Column('deleted', sa.String(length=36), nullable=True))
    op.add_column('computehost_allocations',
                  sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.drop_constraint(u'computehost_allocations_ibfk_1',
                       'computehost_allocations', type_='foreignkey')
    op.add_column('computehost_reservations',
                  sa.Column('deleted', sa.String(length=36), nullable=True))
    op.add_column('computehost_reservations',
                  sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('events',
                  sa.Column('deleted', sa.String(length=36), nullable=True))
    op.add_column('events',
                  sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('instance_reservations',
                  sa.Column('deleted', sa.String(length=36), nullable=True))
    op.add_column('instance_reservations',
                  sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('leases',
                  sa.Column('deleted', sa.String(length=36), nullable=True))
    op.add_column('leases',
                  sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.add_column('reservations',
                  sa.Column('deleted', sa.String(length=36), nullable=True))
    op.add_column('reservations',
                  sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('reservations', 'deleted_at')
    op.drop_column('reservations', 'deleted')
    op.drop_column('leases', 'deleted_at')
    op.drop_column('leases', 'deleted')
    op.drop_column('instance_reservations', 'deleted_at')
    op.drop_column('instance_reservations', 'deleted')
    op.drop_column('events', 'deleted_at')
    op.drop_column('events', 'deleted')
    op.drop_column('computehost_reservations', 'deleted_at')
    op.drop_column('computehost_reservations', 'deleted')
    op.create_foreign_key(u'computehost_allocations_ibfk_1',
                          'computehost_allocations', 'computehosts',
                          ['compute_host_id'], ['id'])
    op.drop_column('computehost_allocations', 'deleted_at')
    op.drop_column('computehost_allocations', 'deleted')

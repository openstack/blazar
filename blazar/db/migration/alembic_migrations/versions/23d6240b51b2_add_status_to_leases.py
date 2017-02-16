# Copyright 2014 OpenStack Foundation.
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

"""Add status to leases

Revision ID: 23d6240b51b2
Revises: 2bcfe76b0474
Create Date: 2014-04-25 10:41:09.183430

"""

# revision identifiers, used by Alembic.
revision = '23d6240b51b2'
down_revision = '2bcfe76b0474'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('leases', sa.Column(
        'action', sa.String(length=255), nullable=True))
    op.add_column('leases', sa.Column(
        'status', sa.String(length=255), nullable=True))
    op.add_column('leases', sa.Column(
        'status_reason', sa.String(length=255), nullable=True))


def downgrade():
    engine = op.get_bind().engine
    if engine.name == 'sqlite':
        # Only for testing purposes with sqlite
        op.execute('CREATE TABLE tmp_leases as SELECT created_at, updated_at, '
                   'id, name, user_id, project_id, start_date, '
                   'end_date, trust_id FROM leases')
        op.execute('DROP TABLE leases')
        op.execute('ALTER TABLE tmp_leases RENAME TO leases')
        return

    op.drop_column('leases', 'action')
    op.drop_column('leases', 'status')
    op.drop_column('leases', 'status_reason')

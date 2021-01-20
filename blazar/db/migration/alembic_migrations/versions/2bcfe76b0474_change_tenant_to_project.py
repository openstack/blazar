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

"""Change tenant to project

Revision ID: 2bcfe76b0474
Revises: 0_1
Create Date: 2014-03-19 18:08:50.825586

"""

# revision identifiers, used by Alembic.
revision = '2bcfe76b0474'
down_revision = '10e34bba18e8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    engine = op.get_bind().engine
    if engine.name == 'sqlite':
        # Only for testing purposes with sqlite
        op.execute('CREATE TABLE tmp_leases as SELECT created_at, updated_at, '
                   'id, name, user_id, tenant_id as project_id, start_date, '
                   'end_date, trust_id FROM leases')
        op.execute('DROP TABLE leases')
        op.execute('ALTER TABLE tmp_leases RENAME TO leases')
        return

    op.alter_column('leases', 'tenant_id', new_column_name='project_id',
                    existing_type=sa.String(length=255))


def downgrade():
    engine = op.get_bind().engine
    if engine.name == 'sqlite':
        # Only for testing purposes with sqlite
        op.execute('CREATE TABLE tmp_leases as SELECT created_at, updated_at, '
                   'id, name, user_id, project_id as tenant_id, start_date, '
                   'end_date, trust_id FROM leases')
        op.execute('DROP TABLE leases')
        op.execute('ALTER TABLE tmp_leases RENAME TO leases')
        return

    op.alter_column('leases', 'project_id', new_column_name='tenant_id',
                    existing_type=sa.String(length=255))

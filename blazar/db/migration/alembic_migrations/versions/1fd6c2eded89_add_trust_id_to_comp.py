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

"""Add trust_id to ComputeHost

Revision ID: 1fd6c2eded89
Revises: 0_1
Create Date: 2014-03-28 01:12:02.735519

"""

# revision identifiers, used by Alembic.
revision = '1fd6c2eded89'
down_revision = '23d6240b51b2'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('computehosts',
                  sa.Column('trust_id',
                            sa.String(length=36),
                            nullable=True))

    if op.get_bind().engine.name != 'sqlite':
        # I need to do it in this way because Postgress fails
        # if I use SQLAlchemy
        connection = op.get_bind()
        connection.execute(sa.text("UPDATE computehosts SET trust_id = ''"))

        op.alter_column('computehosts', 'trust_id',
                        existing_type=sa.String(length=36), nullable=False)


def downgrade():
    engine = op.get_bind().engine
    if engine.name == 'sqlite':
        # Only for testing purposes with sqlite
        op.execute('CREATE TABLE tmp_computehosts as SELECT id, '
                   'vcpus, cpu_info, hypervisor_type, '
                   'hypervisor_version, hypervisor_hostname, service_name, '
                   'memory_mb, local_gb, status '
                   'FROM computehosts')
        op.execute('DROP TABLE computehosts')
        op.execute('ALTER TABLE tmp_computehosts RENAME TO computehosts')
        return

    op.drop_column('computehosts', 'trust_id')

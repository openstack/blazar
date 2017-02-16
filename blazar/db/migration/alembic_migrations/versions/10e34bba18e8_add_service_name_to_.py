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

"""Add service name to ComputeHost

Revision ID: 10e34bba18e8
Revises: 0_1
Create Date: 2014-04-04 11:00:57.542857

"""

# revision identifiers, used by Alembic.
revision = '10e34bba18e8'
down_revision = '0_1'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('computehosts', sa.Column(
        'service_name', sa.String(length=255), nullable=True))


def downgrade():
    engine = op.get_bind().engine
    if engine.name == 'sqlite':
        # Only for testing purposes with sqlite
        op.execute('CREATE TABLE tmp_computehosts as SELECT id, '
                   'vcpus, cpu_info, hypervisor_type, '
                   'hypervisor_version, hypervisor_hostname, memory_mb, '
                   'local_gb, status '
                   'FROM computehosts')
        op.execute('DROP TABLE computehosts')
        op.execute('ALTER TABLE tmp_computehosts RENAME TO computehosts')
        return

    op.drop_column('computehosts', 'service_name')

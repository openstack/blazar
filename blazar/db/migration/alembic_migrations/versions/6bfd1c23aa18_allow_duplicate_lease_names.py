# Copyright 2017 OpenStack Foundation.
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

"""Allow duplicate lease names

Revision ID: 6bfd1c23aa18
Revises: ba75b766b64e
Create Date: 2017-08-16 08:49:15.307072

"""

# revision identifiers, used by Alembic.
revision = '6bfd1c23aa18'
down_revision = 'ba75b766b64e'

from alembic import op
from sqlalchemy.engine import reflection


def upgrade():
    inspector = reflection.Inspector.from_engine(op.get_bind())
    unique_constraints = inspector.get_unique_constraints('leases')
    for constraint in unique_constraints:
        if constraint['column_names'] == ['name']:
            op.drop_constraint(constraint['name'], 'leases', type_='unique')
            break


def downgrade():
    op.create_unique_constraint('uniq_leases0name', 'leases', ['name'])

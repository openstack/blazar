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

"""add_az_in_compute

Revision ID: 35b314cd39ee
Revises: c0ae6b08b0d7
Create Date: 2018-04-23 07:40:39.750686

"""

# revision identifiers, used by Alembic.
revision = '35b314cd39ee'
down_revision = 'c0ae6b08b0d7'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('computehosts',
                  sa.Column('availability_zone', sa.String(length=255),
                            default="", nullable=False))


def downgrade():
    op.drop_column('computehosts', 'availability_zone')

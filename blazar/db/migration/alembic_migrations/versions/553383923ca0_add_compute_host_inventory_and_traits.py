# Copyright 2024 OpenStack Foundation.
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

"""Add compute host inventory and traits

Revision ID: 553383923ca0
Revises: 02e2f2186d98
Create Date: 2024-04-29 17:40:05.148493

"""

# revision identifiers, used by Alembic.
revision = '553383923ca0'
down_revision = '02e2f2186d98'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'computehost_resource_inventory',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('computehost_id', sa.String(length=36), nullable=True),
        sa.Column('resource_class', sa.String(length=255), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('reserved', sa.Integer(), nullable=False),
        sa.Column('min_unit', sa.Integer(), nullable=False),
        sa.Column('max_unit', sa.Integer(), nullable=False),
        sa.Column('step_size', sa.Integer(), nullable=False),
        sa.Column('allocation_ratio', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['computehost_id'], ['computehosts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'computehost_trait',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('computehost_id', sa.String(length=36), nullable=True),
        sa.Column('trait', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['computehost_id'], ['computehosts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('computehost_trait')
    op.drop_table('computehost_resource_inventory')

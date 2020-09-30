# Copyright 2014 OpenStack Foundation.
# Copyright 2014 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""Icehouse Initial

Revision ID: 0_1
Revises: None
Create Date: 2014-02-19 17:23:47.705197

"""

# revision identifiers, used by Alembic.
revision = '0_1'
down_revision = None

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import MEDIUMTEXT


def _generate_unicode_uuid():
    return str(uuid.uuid4())


def MediumText():
    return sa.Text().with_variant(MEDIUMTEXT(), 'mysql')


def _id_column():
    return sa.Column('id', sa.String(36), primary_key=True,
                     default=_generate_unicode_uuid)


def upgrade():
    op.create_table(
        'computehosts',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('vcpus', sa.Integer(), nullable=False),
        sa.Column('cpu_info', MediumText(), nullable=False),
        sa.Column('hypervisor_type', MediumText(), nullable=False),
        sa.Column('hypervisor_version', sa.Integer(), nullable=False),
        sa.Column('hypervisor_hostname', sa.String(length=255), nullable=True),
        sa.Column('memory_mb', sa.Integer(), nullable=False),
        sa.Column('local_gb', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=13)),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'leases',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('trust_id', sa.String(length=36)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'))

    op.create_table(
        'reservations',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('lease_id', sa.String(length=36), nullable=False),
        sa.Column('resource_id', sa.String(length=36)),
        sa.Column('resource_type', sa.String(length=66)),
        sa.Column('status', sa.String(length=13)),
        sa.ForeignKeyConstraint(['lease_id'], ['leases.id'], ),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'computehost_extra_capabilities',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('computehost_id', sa.String(length=36), nullable=True),
        sa.Column('capability_name', sa.String(length=64), nullable=False),
        sa.Column('capability_value', MediumText(), nullable=False),
        sa.ForeignKeyConstraint(['computehost_id'], ['computehosts.id'], ),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'events',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('lease_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=66)),
        sa.Column('time', sa.DateTime()),
        sa.Column('status', sa.String(length=13)),
        sa.ForeignKeyConstraint(['lease_id'], ['leases.id'], ),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'computehost_allocations',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('compute_host_id', sa.String(length=36), nullable=True),
        sa.Column('reservation_id', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['compute_host_id'], ['computehosts.id'], ),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.PrimaryKeyConstraint('id'))

    op.create_table(
        'computehost_reservations',
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        _id_column(),
        sa.Column('reservation_id', sa.String(length=36), nullable=True),
        sa.Column('resource_properties', MediumText()),
        sa.Column('count_range', sa.String(length=36)),
        sa.Column('hypervisor_properties', MediumText()),
        sa.Column('status', sa.String(length=13)),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.PrimaryKeyConstraint('id'))


def downgrade():
    op.drop_table('computehost_extra_capabilities')
    op.drop_table('computehost_allocations')
    op.drop_table('computehost_reservations')
    op.drop_table('computehosts')
    op.drop_table('reservations')
    op.drop_table('events')
    op.drop_table('leases')

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

"""no affinity instance reservation

Revision ID: 9593f3656974
Revises: 35b314cd39ee
Create Date: 2018-12-26 15:55:29.950250

"""

# revision identifiers, used by Alembic.
revision = '9593f3656974'
down_revision = '35b314cd39ee'

from alembic import op
from sqlalchemy.dialects import mysql


def upgrade():
    op.alter_column('instance_reservations', 'affinity',
                    existing_type=mysql.TINYINT(display_width=1),
                    nullable=True)


def downgrade():
    # TODO(tetsuro): Since the Kilo release, OpenStack doesn't support
    # database downgrades, we should delete this, update the related
    # Blazar documents, and issue a reno in a followup.
    op.alter_column('instance_reservations', 'affinity',
                    existing_type=mysql.TINYINT(display_width=1),
                    nullable=False)

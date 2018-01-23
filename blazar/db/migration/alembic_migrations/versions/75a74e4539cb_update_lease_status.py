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

"""update lease status

Revision ID: 75a74e4539cb
Revises: e66f199a5414
Create Date: 2018-01-23 11:05:56.753579

"""

# revision identifiers, used by Alembic.
revision = '75a74e4539cb'
down_revision = 'e66f199a5414'

from blazar.db import api as db_api
from blazar.status import LeaseStatus as ls


def upgrade():
    leases = db_api.lease_get_all()
    for lease in leases:
        db_api.lease_update(lease['id'],
                            {'status': ls.derive_stable_status(lease['id'])})


def downgrade():
    leases = db_api.lease_get_all()
    for lease in leases:
        db_api.lease_update(lease['id'],
                            {'status': None})

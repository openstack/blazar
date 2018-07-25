# Copyright (c) 2013 Mirantis Inc.
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

from oslo_db.sqlalchemy import models
from oslo_utils import timeutils
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy.ext import declarative
from sqlalchemy.orm import attributes
from sqlalchemy import String


class SoftDeleteMixinWithUuid(object):
    """Mixin to provide soft delete capabilities.

    We cannot use oslo.db's SoftDeleteMixin as it assumes the `id` column is an
    integer, while we use a UUID string.
    """
    deleted_at = Column(DateTime)
    deleted = Column(String(36), nullable=True)

    def soft_delete(self, session):
        """Mark this object as deleted."""
        self.deleted = self.id
        self.deleted_at = timeutils.utcnow()
        self.save(session=session)


class _BlazarBase(models.ModelBase, models.TimestampMixin):
    """Base class for all Blazar SQLAlchemy DB Models."""

    def to_dict(self, include=None):
        """sqlalchemy based automatic to_dict method."""
        d = {}

        # if a column is unloaded at this point, it is
        # probably deferred. We do not want to access it
        # here and thereby cause it to load...
        unloaded = attributes.instance_state(self).unloaded

        columns = self.__table__.columns
        if include:
            columns = [col for col in columns if col.name in include]

        for col in columns:
            if col.name not in unloaded:
                d[col.name] = getattr(self, col.name)

        datetime_to_str(d, 'created_at')
        datetime_to_str(d, 'updated_at')

        # Don't show fields created by SoftDeleteMixinWithUuid
        if 'deleted' in d:
            del d['deleted']
        if 'deleted_at' in d:
            del d['deleted_at']

        return d


def datetime_to_str(dct, attr_name):
    if dct.get(attr_name) is not None:
        dct[attr_name] = dct[attr_name].isoformat(' ')

BlazarBase = declarative.declarative_base(cls=_BlazarBase)

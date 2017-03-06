# Copyright (c) 2014 Bull.
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

import wsme
from wsme import types as wtypes

from blazar.api.v2.controllers import types


class _Base(wtypes.DynamicBase):

    # NOTE(sbauza): That does respect ISO8601 but with a different sep (' ')
    created_at = types.Datetime('%Y-%m-%d %H:%M:%S.%f')
    "The time in UTC at which the object is created"

    updated_at = types.Datetime('%Y-%m-%d %H:%M:%S.%f')
    "The time in UTC at which the object is updated"

    def as_dict(self):
        cls = type(self)
        valid_keys = [item for item in dir(cls)
                      if item not in dir(_Base)
                      and wtypes.iswsattr(getattr(cls, item))]

        if 'self' in valid_keys:
            valid_keys.remove('self')
        return self.as_dict_from_keys(valid_keys)

    def as_dict_from_keys(self, keys):
        res = {}
        for key in keys:
            value = getattr(self, key, wsme.Unset)
            if value != wsme.Unset:
                res[key] = value
        return res

    @classmethod
    def convert(cls, rpc_obj):
        obj = cls(**rpc_obj)
        return obj

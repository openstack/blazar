# Copyright (c) 2018 University of Chicago
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

from blazar.db import api as db_api

BILLRATE_EXTRA_KEY = 'su_factor'


def computehost_billrate(computehost_id):
    """Looks up the SU charging rate for the specified compute host."""
    extra = db_api.host_extra_capability_get_latest_per_name(
        computehost_id, BILLRATE_EXTRA_KEY
    )
    if extra:
        return float(extra.capability_value)
    return 1.0

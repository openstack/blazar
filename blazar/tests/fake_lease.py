# Copyright (c) 2014 Red Hat.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


lease_data = {'id': '1',
              'name': 'lease_test',
              'start_date': '2014-01-01 01:23',
              'end_date': '2014-02-01 13:37',
              'user_id': 'efd8780712d24b389c705f5c2ac427ff',
              'project_id': 'bd9431c18d694ad3803a8d4a6b89fd36',
              'trust_id': '35b17138b3644e6aa1318f3099c5be68',
              'reservations': [{'resource_id': '1234',
                                'resource_type': 'virtual:instance'}],
              'events': [],
              'before_end_date': '2014-02-01 10:37',
              'action': None,
              'status': None,
              'status_reason': None}


def fake_lease(**kw):
    _fake_lease = lease_data.copy()
    _fake_lease.update(**kw)
    return _fake_lease


def fake_lease_update(id, values):
    return fake_lease(id=id, **values)

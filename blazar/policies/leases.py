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

from oslo_policy import policy

from blazar.policies import base

POLICY_ROOT = 'blazar:leases:%s'

leases_policies = [
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'get',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Policy rule for List/Show Lease(s) API.',
        operations=[
            {
                'path': '/{api_version}/leases',
                'method': 'GET'
            },
            {
                'path': '/{api_version}/leases/{lease_id}',
                'method': 'GET'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'post',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Policy rule for Create Lease API.',
        operations=[
            {
                'path': '/{api_version}/leases',
                'method': 'POST'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'put',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Policy rule for Update Lease API.',
        operations=[
            {
                'path': '/{api_version}/leases/{lease_id}',
                'method': 'PUT'
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'delete',
        check_str=base.RULE_ADMIN_OR_OWNER,
        description='Policy rule for Delete Lease API.',
        operations=[
            {
                'path': '/{api_version}/leases/{lease_id}',
                'method': 'DELETE'
            }
        ]
    )
]


def list_rules():
    return leases_policies

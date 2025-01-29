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

POLICY_ROOT = 'blazar:floatingips:%s'

floatingips_policies = [
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'get',
        check_str=base.PROJECT_READER_OR_ADMIN,
        description='Policy rule for List/Show FloatingIP(s) API.',
        operations=[
            {
                'path': '/{api_version}/floatingips',
                'method': 'GET'
            },
            {
                'path': '/{api_version}/floatingips/{floatingip_id}',
                'method': 'GET'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'post',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Create Floating IP API.',
        operations=[
            {
                'path': '/{api_version}/floatingips',
                'method': 'POST'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'delete',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Delete Floating IP API.',
        operations=[
            {
                'path': '/{api_version}/floatingips/{floatingip_id}',
                'method': 'DELETE'
            }
        ],
        scope_types=['project']
    )
]


def list_rules():
    return floatingips_policies

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

POLICY_ROOT = 'blazar:oshosts:%s'

oshosts_policies = [
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'get',
        check_str=base.RULE_ADMIN,
        description='Policy rule for List/Show Host(s) API.',
        operations=[
            {
                'path': '/{api_version}/os-hosts',
                'method': 'GET'
            },
            {
                'path': '/{api_version}/os-hosts/{host_id}',
                'method': 'GET'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'post',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Create Host API.',
        operations=[
            {
                'path': '/{api_version}/os-hosts',
                'method': 'POST'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'put',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Update Host API.',
        operations=[
            {
                'path': '/{api_version}/os-hosts/{host_id}',
                'method': 'PUT'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'delete',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Delete Host API.',
        operations=[
            {
                'path': '/{api_version}/os-hosts/{host_id}',
                'method': 'DELETE'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'get_allocations',
        check_str=base.RULE_ADMIN,
        description='Policy rule for List/Get Host(s) Allocations API.',
        operations=[
            {
                'path': '/{api_version}/os-hosts/allocations',
                'method': 'GET'
            },
            {
                'path': '/{api_version}/os-hosts/{host_id}/allocation',
                'method': 'GET'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'get_resource_properties',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Resource Properties API.',
        operations=[
            {
                'path': '/{api_version}/os-hosts/resource_properties',
                'method': 'GET'
            }
        ],
        scope_types=['project']
    ),
    policy.DocumentedRuleDefault(
        name=POLICY_ROOT % 'update_resource_properties',
        check_str=base.RULE_ADMIN,
        description='Policy rule for Resource Properties API.',
        operations=[
            {
                'path': ('/{api_version}/os-hosts/resource_properties/'
                         '{property_name}'),
                'method': 'PATCH'
            }
        ],
        scope_types=['project']
    ),
]


def list_rules():
    return oshosts_policies

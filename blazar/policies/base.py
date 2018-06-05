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

RULE_ADMIN = 'rule:admin'
RULE_ADMIN_OR_OWNER = 'rule:admin_or_owner'
RULE_ANY = '@'

rules = [
    policy.RuleDefault(
        name="admin",
        check_str="is_admin:True or role:admin",
        description="Default rule for most Admin APIs."),
    policy.RuleDefault(
        name="admin_or_owner",
        check_str="rule:admin or project_id:%(project_id)s",
        description="Default rule for most non-Admin APIs.")
]


def list_rules():
    return rules

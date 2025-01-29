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

DEPRECATED_REASON = """
Blazar API policies are introducing new default roles with scope_type
capabilities. Old policies are deprecated and silently going to be ignored
in future release.
"""

DEPRECATED_ADMIN_OR_OWNER_POLICY = policy.DeprecatedRule(
    name=RULE_ADMIN_OR_OWNER,
    check_str="rule:admin or project_id:%(project_id)s",
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since='15.0.0'
)

PROJECT_MEMBER_OR_ADMIN = 'rule:project_member_or_admin'
PROJECT_READER_OR_ADMIN = 'rule:project_reader_or_admin'

rules = [
    policy.RuleDefault(
        name="admin",
        check_str="is_admin:True or role:admin",
        description="Default rule for most Admin APIs."),
    policy.RuleDefault(
        name="admin_or_owner",
        check_str="rule:admin or project_id:%(project_id)s",
        description="Default rule for most non-Admin APIs.",
        deprecated_for_removal=True,
        deprecated_reason=DEPRECATED_REASON,
        deprecated_since='15.0.0'),
    policy.RuleDefault(
        "project_member_api",
        "role:member and project_id:%(project_id)s",
        "Default rule for Project Member (non-Admin) APIs.",
        deprecated_rule=DEPRECATED_ADMIN_OR_OWNER_POLICY),
    policy.RuleDefault(
        "project_reader_api",
        "role:reader and project_id:%(project_id)s",
        "Default rule for Project Reader (read-only) APIs.",
        deprecated_rule=DEPRECATED_ADMIN_OR_OWNER_POLICY),
    policy.RuleDefault(
        "project_member_or_admin",
        "rule:project_member_api or rule:admin",
        "Default rule for Project Member or Admin APIs.",
        deprecated_rule=DEPRECATED_ADMIN_OR_OWNER_POLICY),
    policy.RuleDefault(
        "project_reader_or_admin",
        "rule:project_reader_api or rule:admin",
        "Default rule for Project Reader or Admin APIs.",
        deprecated_rule=DEPRECATED_ADMIN_OR_OWNER_POLICY)
]


def list_rules():
    return rules

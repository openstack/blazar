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

from climate import context


def ctx_from_headers(headers):
    return context.ClimateContext(
        user_id=headers['X-User-Id'],
        tenant_id=headers['X-Tenant-Id'],
        auth_token=headers['X-Auth-Token'],
        service_catalog=headers['X-Service-Catalog'],
        user_name=headers['X-User-Name'],
        tenant_name=headers['X-Tenant-Name'],
        roles=map(unicode.strip, headers['X-Roles'].split(',')),
    )

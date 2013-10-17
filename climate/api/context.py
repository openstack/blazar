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

import json

from climate import context
from climate import exceptions
from climate import policy


def ctx_from_headers(headers):
    try:
        service_catalog = json.loads(headers['X-Service-Catalog'])
    except KeyError:
        raise exceptions.ServiceCatalogNotFound()
    except TypeError:
        raise exceptions.WrongFormat()

    ctx = context.ClimateContext(
        user_id=headers['X-User-Id'],
        tenant_id=headers['X-Tenant-Id'],
        auth_token=headers['X-Auth-Token'],
        service_catalog=service_catalog,
        user_name=headers['X-User-Name'],
        tenant_name=headers['X-Tenant-Name'],
        roles=map(unicode.strip, headers['X-Roles'].split(',')),
    )
    target = {'tenant_id': ctx.tenant_id, 'user_id': ctx.user_id}
    if policy.enforce(ctx, "admin", target, do_raise=False):
        ctx.is_admin = True
    return ctx

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

import functools

from oslo_config import cfg

from blazar import context
from blazar.utils.openstack import base
from blazar.utils.openstack import keystone

CONF = cfg.CONF


def create_trust():
    """Creates trust via Keystone API v3 to use in plugins."""
    client = keystone.BlazarKeystoneClient()

    trustee_id = keystone.BlazarKeystoneClient(
        password=CONF.os_admin_password,
        ctx=context.admin()).user_id

    ctx = context.current()
    trust = client.trusts.create(trustor_user=ctx.user_id,
                                 trustee_user=trustee_id,
                                 impersonation=False,
                                 role_names=ctx.roles,
                                 project=ctx.project_id)
    return trust


def delete_trust(lease):
    """Deletes trust for the specified lease."""
    if lease.trust_id:
        client = keystone.BlazarKeystoneClient(trust_id=lease.trust_id)
        client.trusts.delete(lease.trust_id)


def create_ctx_from_trust(trust_id):
    """Return context built from given trust."""
    ctx = context.current()

    auth_url = "%s://%s:%s" % (CONF.os_auth_protocol,
                               base.get_os_auth_host(CONF),
                               CONF.os_auth_port)
    if CONF.os_auth_prefix:
        auth_url += "/%s" % CONF.os_auth_prefix

    client = keystone.BlazarKeystoneClient(
        password=CONF.os_admin_password,
        trust_id=trust_id,
        auth_url=auth_url,
        ctx=context.admin(),
    )

    # use 'with ctx' statement in the place you need context from trust
    return context.BlazarContext(
        user_name=ctx.user_name,
        user_domain_name=ctx.user_domain_name,
        auth_token=client.auth_token,
        service_catalog=client.service_catalog.catalog['catalog'],
        project_id=client.project_id,
        request_id=ctx.request_id,
        global_request_id=ctx.global_request_id
    )


def use_trust_auth():
    """Decorator creates a keystone trust

    This decorator creates a keystone trust, and adds the trust_id to the
    parameter of the decorated method.
    """
    def decorator(func):

        @functools.wraps(func)
        def wrapped(self, to_update):
            if to_update is not None:
                trust = create_trust()
                if isinstance(to_update, dict):
                    to_update.update({'trust_id': trust.id})
                elif isinstance(to_update, object):
                    setattr(to_update, 'trust_id', trust.id)
            return func(self, to_update)

        return wrapped
    return decorator

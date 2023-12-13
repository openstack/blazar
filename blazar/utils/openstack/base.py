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

from keystoneauth1.access import create as create_access_info
from keystoneauth1.identity import access
from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient import client as keystone_client
import netaddr
from oslo_config import cfg

from blazar import context
from blazar.manager import exceptions


CONF = cfg.CONF


def get_os_auth_host(conf):
    """Description

    Returns os_auth_host from conf, surrounded by brackets if IPv6.
    """
    os_auth_host = conf.os_auth_host
    if netaddr.valid_ipv6(os_auth_host, netaddr.core.INET_PTON):
        os_auth_host = "[%s]" % os_auth_host
    return os_auth_host


def client_kwargs(**_kwargs):
    kwargs = _kwargs.copy()

    ctx = kwargs.pop('ctx', None)
    username = kwargs.pop('username',
                          CONF.os_admin_username)
    password = kwargs.pop('password',
                          CONF.os_admin_password)
    project_name = kwargs.pop('project_name',
                              CONF.os_admin_project_name)
    user_domain_name = kwargs.pop('user_domain_name',
                                  CONF.os_admin_user_domain_name)
    project_domain_name = kwargs.pop('project_domain_name',
                                     CONF.os_admin_project_domain_name)
    trust_id = kwargs.pop('trust_id', None)
    auth_url = kwargs.pop('auth_url', None)
    region_name = kwargs.pop('region_name', CONF.os_region_name)
    if ctx is None:
        try:
            ctx = context.current()
        except RuntimeError:
            pass
    if ctx is not None:
        kwargs.setdefault('global_request_id', ctx.global_request_id)

    if auth_url is None:
        auth_url = "%s://%s:%s/%s/%s" % (CONF.os_auth_protocol,
                                         get_os_auth_host(CONF),
                                         CONF.os_auth_port,
                                         CONF.os_auth_prefix,
                                         CONF.os_auth_version)

    auth_kwargs = dict(
        auth_url=auth_url,
        username=username,
        password=password,
        user_domain_name=user_domain_name,
        project_domain_name=project_domain_name
    )

    if trust_id is not None:
        auth_kwargs.update(trust_id=trust_id)
    else:
        auth_kwargs.update(project_name=project_name)

    auth = v3.Password(**auth_kwargs)

    sess_kwargs = dict(
        auth=auth
    )

    if CONF.cafile:
        sess_kwargs.update(verify=CONF.cafile)

    sess = session.Session(**sess_kwargs)

    kwargs.setdefault('session', sess)
    kwargs.setdefault('region_name', region_name)
    return kwargs


def client_user_kwargs(**_kwargs):
    kwargs = _kwargs.copy()

    auth_url = kwargs.pop('auth_url', None)
    region_name = kwargs.pop('region_name', CONF.os_region_name)

    if auth_url is None:
        auth_url = "%s://%s:%s/%s/%s" % (CONF.os_auth_protocol,
                                         get_os_auth_host(CONF),
                                         CONF.os_auth_port,
                                         CONF.os_auth_prefix,
                                         CONF.os_auth_version)

    # Pass the auth token present on the context directly on to the
    # next service; this effectively proxies the user's token they used
    # to authenticate to Blazar, and prevents having to re-authenticate
    # (which has issues for certain auth types, such as application creds)
    ctx = context.current()
    admin_ks_client = keystone_client.Client(
        version='3',
        **client_kwargs(**_kwargs)
    )
    data = admin_ks_client.tokens.get_token_data(ctx.auth_token)
    access_info = create_access_info(body=data, auth_token=ctx.auth_token)
    auth = access.AccessInfoPlugin(access_info, auth_url=auth_url)

    sess_kwargs = dict(
        auth=auth
    )

    if CONF.cafile:
        sess_kwargs.update(verify=CONF.cafile)

    sess = session.Session(**sess_kwargs)

    kwargs.setdefault('session', sess)
    kwargs.setdefault('region_name', region_name)
    return kwargs


def url_for(service_catalog, service_type, admin=False,
            endpoint_interface=None,
            os_region_name=None):
    """Description

    Gets url of the service to communicate through.
    service_catalog - dict contains info about specific OpenStack service
    service_type - OpenStack service type specification
    """
    if not endpoint_interface:
        if service_type == 'identity':
            endpoint_interface = CONF.endpoint_type
        elif service_type == 'compute':
            endpoint_interface = CONF.nova.endpoint_type
        else:
            endpoint_interface = 'public'

    if not isinstance(service_catalog, list):
        service_catalog = service_catalog.normalize_catalog()

    service = None
    for srv in service_catalog:
        if srv['type'] == service_type:
            service = srv

    if service:
        try:
            endpoints = service['endpoints']
        except KeyError:
            raise exceptions.EndpointsNotFound(
                "No endpoints for %s" % service['type'])
        if os_region_name:
            endpoints = [e for e in endpoints if e['region'] == os_region_name]
            if not endpoints:
                raise exceptions.EndpointsNotFound("No endpoints for %s in "
                                                   "region %s" %
                                                   (service['type'],
                                                    os_region_name))
        try:
            # if Keystone API v3 endpoints returned
            endpoint = [e for e in endpoints
                        if e['interface'] == endpoint_interface][0]
            return endpoint['url']
        except KeyError:
            # otherwise
            return endpoints[0]['%sURL' % endpoint_interface]
    else:
        raise exceptions.ServiceNotFound(
            'Service "%s" not found' % service_type)

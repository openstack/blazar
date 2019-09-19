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

import netaddr

from blazar.manager import exceptions


def get_os_auth_host(conf):
    """Description

    Returns os_auth_host from conf, surrounded by brackets if IPv6.
    """
    os_auth_host = conf.os_auth_host
    if netaddr.valid_ipv6(os_auth_host, netaddr.core.INET_PTON):
        os_auth_host = "[%s]" % os_auth_host
    return os_auth_host


def url_for(service_catalog, service_type, admin=False,
            endpoint_interface=None,
            os_region_name=None):
    """Description

    Gets url of the service to communicate through.
    service_catalog - dict contains info about specific OpenStack service
    service_type - OpenStack service type specification
    """
    if not endpoint_interface:
        endpoint_interface = 'public'
    if admin:
        endpoint_interface = 'admin'

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

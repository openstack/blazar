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

from oslo_serialization import jsonutils
import six

from blazar import context
from blazar import exceptions


def ctx_from_headers(headers):
    try:
        service_catalog = jsonutils.loads(headers['X-Service-Catalog'])
    except KeyError:
        raise exceptions.ServiceCatalogNotFound()
    except TypeError:
        raise exceptions.WrongFormat()

    kwargs = {"user_id": headers['X-User-Id'],
              "project_id": headers['X-Project-Id'],
              "auth_token": headers['X-Auth-Token'],
              "service_catalog": service_catalog,
              "user_name": headers['X-User-Name'],
              "project_name": headers['X-Project-Name'],
              "roles": list(
                  map(six.text_type.strip, headers['X-Roles'].split(',')))}

    # For v1 only, request_id and global_request_id will be available.
    if headers.environ['PATH_INFO'].startswith('/v1'):
        kwargs['request_id'] = headers.environ['openstack.request_id']
        kwargs['global_request_id'] = headers.environ.get(
            'openstack.global_request_id')
    return context.BlazarContext(**kwargs)

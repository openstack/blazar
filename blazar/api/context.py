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

from blazar import context
from blazar import exceptions


def ctx_from_headers(headers):
    try:
        service_catalog = jsonutils.loads(headers['X-Service-Catalog'])
    except KeyError:
        raise exceptions.ServiceCatalogNotFound()
    except TypeError:
        raise exceptions.WrongFormat()

    return context.BlazarContext.from_environ(headers.environ,
                                              service_catalog=service_catalog)

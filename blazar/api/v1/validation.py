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

from blazar.api.v1 import utils as api_utils
from blazar import exceptions


def check_exists(get_function, object_id=None, **get_args):
    """Check object exists.

    :param get_function: Method to call to get object.
    :type get_function: function
    :param object_id: ID of the object to get.
    :type object_id: str
    :param get_args: Other params to pass to the get_function method.
    :type get_args: dict
    """
    def decorator(func):
        """Decorate method to check object existing."""
        if object_id is not None:
            get_args['id'] = object_id

        @functools.wraps(func)
        def handler(*args, **kwargs):
            """Decorator handler."""

            get_kwargs = {}
            for k, v in get_args.items():
                get_kwargs[k] = kwargs[v]

            try:
                obj = get_function(**get_kwargs)
            except exceptions.NotFound:
                obj = None
            if obj is None:
                e = exceptions.NotFound(object=get_kwargs)
                return api_utils.not_found(e)

            return func(*args, **kwargs)

        return handler

    return decorator

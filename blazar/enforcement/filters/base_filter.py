# Copyright (c) 2020 University of Chicago.
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

import abc
import six


@six.add_metaclass(abc.ABCMeta)
class BaseFilter:

    enforcement_opts = []

    def __init__(self, conf=None):
        self.conf = conf

        for opt in self.enforcement_opts:
            self.conf.register_opt(opt, 'enforcement')

    def __getattr__(self, name):
        func = getattr(self.conf.enforcement, name)
        return func

    @abc.abstractmethod
    def check_create(self, context, lease_values):
        pass

    @abc.abstractmethod
    def check_update(self, context, current_lease_values, new_lease_values):
        pass

    @abc.abstractmethod
    def on_end(self, context, lease_values):
        pass

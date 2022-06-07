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

from blazar import tests


class TestCKClient(tests.TestCase):
    """TODO: Update test class.

    This test originally tested functionality implemented in the
    third-party keystoneclient library, which is redundant. It should test
    primarily the branching b/w user and non-user authentication params, as
    that is the main function this wrapper serves.
    """

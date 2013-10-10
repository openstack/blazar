#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Julien Danjou <julien@danjou.info>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from nova.tests.scheduler import fakes

from climate.nova import climate_filter
from climate import test


class ClimateSchedulerTestCase(test.TestCase):

    def test_climate_scheduler(self):
        f = climate_filter.ClimateFilter()
        host = fakes.FakeHostState('host1', 'node1', {})
        filter_properties = {"scheduler_hints": {"foo": "bar"}}
        self.assertTrue(f.host_passes(host, filter_properties))

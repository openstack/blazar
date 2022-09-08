# Copyright (c) 2022 Radosław Piliszek <radoslaw.piliszek@gmail.com>
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

import datetime
import json
from unittest import mock

from blazar.enforcement.exceptions import ExternalServiceFilterException
from blazar.enforcement.filters import external_service_filter
from blazar.tests import TestCase

from oslo_config.cfg import CONF


class FakeResponse204():
    status_code = 204


class FakeResponse403Empty():
    status_code = 403
    content = "irrelevant_but_logged"

    @staticmethod
    def json():
        return {}


class FakeJSONDecodeError(Exception):
    pass


class FakeResponse403InvalidJSON():
    status_code = 403
    content = "NOT_JSON"

    @staticmethod
    def json():
        raise FakeJSONDecodeError()


class FakeResponse403WithMessage():
    status_code = 403
    content = "irrelevant"

    @staticmethod
    def json():
        return {"message": "Hello!"}


class FakeResponse500():
    status_code = 500
    content = "ALL_YOUR_BUGS_BELONG_TO_US"


class ISODateTimeEncoderTestCase(TestCase):

    def test_json_date(self):
        dt = datetime.datetime(2022, 9, 8, 13, 31, 44, 12345)
        obj = {"datetime": dt}
        x = json.dumps(obj, cls=external_service_filter.ISODateTimeEncoder)
        self.assertEqual('{"datetime": "2022-09-08T13:31:44.012345"}', x)

    def test_json_with_tz(self):
        tz = datetime.timezone(datetime.timedelta(hours=2))
        dt = datetime.datetime(2022, 9, 8, 13, 31, 44, 12345, tz)
        obj = {"datetime": dt}
        x = json.dumps(obj, cls=external_service_filter.ISODateTimeEncoder)
        self.assertEqual('{"datetime": "2022-09-08T13:31:44.012345+02:00"}', x)


class ConfiguringExternalServiceFilterTestCase(TestCase):
    def setUp(self):
        super().setUp()

        external_service_filter.ExternalServiceFilter.register_opts(CONF)

    def test_basic_misconfiguration(self):
        self.assertRaises(external_service_filter.ExternalServiceMisconfigured,
                          external_service_filter.ExternalServiceFilter, CONF)

    def test_bad_url(self):
        CONF.set_override(
            'external_service_base_endpoint', 'this_url_cOuLDnOtBeWoRsE',
            group='enforcement')
        self.addCleanup(CONF.clear_override, 'external_service_base_endpoint',
                        group='enforcement')

        self.assertRaises(external_service_filter.ExternalServiceMisconfigured,
                          external_service_filter.ExternalServiceFilter, CONF)

    def test_check_create_endpoint_is_enough(self):
        CONF.set_override(
            'external_service_check_create_endpoint', 'http://localhost',
            group='enforcement')
        self.addCleanup(CONF.clear_override,
                        'external_service_check_create_endpoint',
                        group='enforcement')

        external_service_filter.ExternalServiceFilter(CONF)

    def test_check_updaye_endpoint_is_enough(self):
        CONF.set_override(
            'external_service_check_update_endpoint', 'http://localhost',
            group='enforcement')
        self.addCleanup(CONF.clear_override,
                        'external_service_check_update_endpoint',
                        group='enforcement')

        external_service_filter.ExternalServiceFilter(CONF)

    def test_on_end_endpoint_is_enough(self):
        CONF.set_override(
            'external_service_on_end_endpoint', 'http://localhost',
            group='enforcement')
        self.addCleanup(CONF.clear_override,
                        'external_service_on_end_endpoint',
                        group='enforcement')

        external_service_filter.ExternalServiceFilter(CONF)


class ExternalServiceFilterTestCase(TestCase):
    def setUp(self):
        super().setUp()

        external_service_filter.ExternalServiceFilter.register_opts(CONF)

        CONF.set_override(
            'external_service_base_endpoint', 'http://localhost',
            group='enforcement')
        self.addCleanup(CONF.clear_override, 'external_service_base_endpoint',
                        group='enforcement')

        self.filter = external_service_filter.ExternalServiceFilter(CONF)

        self.ctx = {
            "is_context": True
        }

        self.lease = {
            "is_lease": True
        }

        self.old_lease = {
            "is_old_lease": True
        }

    @mock.patch("requests.post")
    def test_check_create_allowed(self, post_mock):
        post_mock.return_value = FakeResponse204()
        self.filter.check_create(self.ctx, self.lease)
        post_mock.assert_called_with(
            "http://localhost/check-create",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    def test_check_create_denied(self, post_mock):
        post_mock.return_value = FakeResponse403WithMessage()
        self.assertRaises(ExternalServiceFilterException,
                          self.filter.check_create,
                          self.ctx, self.lease)
        post_mock.assert_called_with(
            "http://localhost/check-create",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    def test_check_create_failed(self, post_mock):
        post_mock.return_value = FakeResponse403Empty()
        self.assertRaises(ExternalServiceFilterException,
                          self.filter.check_create,
                          self.ctx, self.lease)
        post_mock.assert_called_with(
            "http://localhost/check-create",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    def test_check_update_allowed(self, post_mock):
        post_mock.return_value = FakeResponse204()
        self.filter.check_update(self.ctx, self.old_lease, self.lease)
        post_mock.assert_called_with(
            "http://localhost/check-update",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"current_lease": {"is_old_lease": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    def test_check_update_denied(self, post_mock):
        post_mock.return_value = FakeResponse403WithMessage()
        self.assertRaises(ExternalServiceFilterException,
                          self.filter.check_update,
                          self.ctx, self.old_lease, self.lease)
        post_mock.assert_called_with(
            "http://localhost/check-update",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"current_lease": {"is_old_lease": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    @mock.patch("requests.JSONDecodeError", FakeJSONDecodeError)
    def test_check_update_failed(self, post_mock):
        post_mock.return_value = FakeResponse403InvalidJSON()
        self.assertRaises(ExternalServiceFilterException,
                          self.filter.check_update,
                          self.ctx, self.old_lease, self.lease)
        post_mock.assert_called_with(
            "http://localhost/check-update",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"current_lease": {"is_old_lease": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    def test_on_end_success(self, post_mock):
        post_mock.return_value = FakeResponse204()
        self.filter.on_end(self.ctx, self.lease)
        post_mock.assert_called_with(
            "http://localhost/on-end",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"lease": {"is_lease": true}}')

    @mock.patch("requests.post")
    def test_on_end_failure(self, post_mock):
        post_mock.return_value = FakeResponse500()
        self.assertRaises(ExternalServiceFilterException,
                          self.filter.on_end,
                          self.ctx, self.lease)
        post_mock.assert_called_with(
            "http://localhost/on-end",
            headers={'Content-Type': 'application/json'},
            data='{"context": {"is_context": true}, '
                 '"lease": {"is_lease": true}}')

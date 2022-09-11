# Copyright 2014 Intel Corporation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg
import oslo_messaging as messaging

from blazar.notification import notifier as notification
from blazar import tests

CONF = cfg.CONF


class FakeNotifier(object):
    def info(self):
        pass


class NotifierTestCase(tests.TestCase):
    def setUp(self):
        super(NotifierTestCase, self).setUp()

        self.group = 'notifications'
        CONF.set_override('publisher_id', 'lease-service', self.group)

        # Fake Oslo notifier
        self.fake_notifier = self.patch(messaging, 'Notifier')
        self.fake_notifier.return_value = FakeNotifier()
        self.fake_transport = self.patch(
            messaging,
            'get_notification_transport')

        self.info_method = self.patch(FakeNotifier, 'info')

        self.context = {'user_id': 1, 'token': 'aabbcc'}
        self.payload = {'id': 1, 'name': 'Lease1', 'start-date': 'now'}

        notification.init()
        self.notifier = notification.Notifier()

    def test_notify_with_wrong_level(self):
        self.notifier._notify(self.context, 'wrong', 'event', self.payload)
        self.info_method.assert_called_once_with(self.context,
                                                 'event', self.payload)

    def test_send_lease_event(self):
        self.notifier.send_lease_notification(self.context, self.payload,
                                              'start')
        self.info_method.assert_called_once_with(self.context,
                                                 'start',
                                                 self.payload)

    def test_cleanup(self):
        notification.cleanup()

        self.fake_transport.return_value.cleanup.assert_called_once_with()
        self.assertIsNone(notification.NOTIFIER)
        self.assertIsNone(notification.TRANSPORT)

    def test_init(self):
        self.fake_transport.assert_called_once_with(notification.CONF)
        self.fake_notifier.assert_called_once_with(
            self.fake_transport.return_value, publisher_id='lease-service')

    def test_init_called_twice_returns_same_instance(self):
        prev_notifier = notification.NOTIFIER
        prev_transport = notification.TRANSPORT

        notification.init()
        self.assertIs(prev_notifier, notification.NOTIFIER)
        self.assertIs(prev_transport, notification.TRANSPORT)

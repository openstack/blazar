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
from oslo_log import log as logging
import oslo_messaging as messaging


notification_opts = [
    cfg.StrOpt('publisher_id',
               default="blazar.lease",
               help='Publisher ID for notifications')
]

LOG = logging.getLogger(__name__)
SERVICE = 'lease'
CONF = cfg.CONF
CONF.register_opts(notification_opts, 'notifications')
TRANSPORT = None
NOTIFIER = None


def init():
    global TRANSPORT, NOTIFIER
    TRANSPORT = messaging.get_notification_transport(CONF)
    NOTIFIER = messaging.Notifier(TRANSPORT,
                                  publisher_id=CONF.notifications.publisher_id)


def cleanup():
    global TRANSPORT, NOTIFIER
    assert TRANSPORT is not None
    assert NOTIFIER is not None
    TRANSPORT.cleanup()
    TRANSPORT = NOTIFIER = None


def get_notifier(publisher_id):
    assert NOTIFIER is not None
    return NOTIFIER


class Notifier(object):
    """Notification class for blazar

    Responsible for sending lease events notifications using oslo.nofity
    """

    def send_lease_notification(self, context, lease, notification):
        """Sends lease notification."""
        self._notify(context, 'info', notification, lease)

    def _notify(self, context, level, event_type, payload):
        notifier = get_notifier(CONF.notifications.publisher_id)
        method = getattr(notifier, level, notifier.info)
        method(context, event_type, payload)

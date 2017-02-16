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

from blazar.notification import notifier

IMPL = notifier.Notifier()


def send_lease_notification(context, lease, notification):
    IMPL.send_lease_notification(context, lease, notification)


def format_lease_payload(lease):
    return {
        'lease_id': lease['id'],
        'user_id': lease['user_id'],
        'project_id': lease['project_id'],
        'start_date': lease['start_date'],
        'end_date': lease['end_date']
    }

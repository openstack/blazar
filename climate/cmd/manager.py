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

import gettext
import sys

import eventlet
eventlet.monkey_patch()
from oslo.config import cfg

gettext.install('climate', unicode=1)

from climate.db import api as db_api
from climate.manager import service as manager_service
from climate.notification import notifier
from climate.openstack.common import service
from climate.utils import service as service_utils


def main():
    cfg.CONF(project='climate', prog='climate-manager')
    service_utils.prepare_service(sys.argv)
    db_api.setup_db()
    notifier.init()
    service.launch(
        manager_service.ManagerService()
    ).wait()


if __name__ == '__main__':
    main()

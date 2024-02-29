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
import threading

from oslo_db.sqlalchemy import enginefacade

_CONTEXT = threading.local()

_engine_facade = None


def session_for_read():
    return _get_facade().reader.using(_CONTEXT)


def session_for_write(sqlite_fk=False):
    return _get_facade(sqlite_fk=sqlite_fk).writer.using(_CONTEXT)


def _clear_engine():
    global _engine_facade
    _engine_facade = None


def _get_facade(sqlite_fk=False):
    global _engine_facade
    if not _engine_facade:
        ctx = enginefacade.transaction_context()
        ctx.configure(sqlite_fk=sqlite_fk)
        _engine_facade = ctx

    return _engine_facade

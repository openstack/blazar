# Copyright (c) 2013 Bull.
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

"""Policy Engine For Climate."""

import functools
from oslo.config import cfg

from climate import context
from climate import exceptions
from climate.openstack.common import log as logging
from climate.openstack.common import policy

CONF = cfg.CONF

LOG = logging.getLogger(__name__)

_ENFORCER = None


def reset():
    global _ENFORCER

    if _ENFORCER:
        _ENFORCER.clear()
    _ENFORCER = None


def init():
    global _ENFORCER
    if not _ENFORCER:
        LOG.debug("Enforcer not present, recreating at init stage.")
        _ENFORCER = policy.Enforcer()


def set_rules(data, default_rule=None):
    default_rule = default_rule or CONF.policy_default_rule
    if not _ENFORCER:
        LOG.debug("Enforcer not present, recreating at rules stage.")
        init()
    if default_rule:
        _ENFORCER.default_rule = default_rule
    _ENFORCER.set_rules(policy.Rules.load_json(data, default_rule))


def enforce(context, action, target, do_raise=True):
    """Verifies that the action is valid on the target in this context.

       :param context: climate context
       :param action: string representing the action to be checked
           this should be colon separated for clarity.
           i.e. ``compute:create_instance``,
           ``compute:attach_volume``,
           ``volume:attach_volume``
       :param target: dictionary representing the object of the action
           for object creation this should be a dictionary representing the
           location of the object e.g. ``{'tenant_id': context.tenant_id}``
       :param do_raise: if True (the default), raises PolicyNotAuthorized;
           if False, returns False

       :raises climate.exceptions.PolicyNotAuthorized: if verification fails
           and do_raise is True.

       :return: returns a non-False value (not necessarily "True") if
           authorized, and the exact value False if not authorized and
           do_raise is False.
    """

    init()

    credentials = context.to_dict()

    # Add the exceptions arguments if asked to do a raise
    extra = {}
    if do_raise:
        extra.update(exc=exceptions.PolicyNotAuthorized, action=action)

    return _ENFORCER.enforce(action, target, credentials, do_raise=do_raise,
                             **extra)


def authorize(extension, action=None, api='climate', ctx=None,
              target=None):
    def decorator(func):

        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            cur_ctx = ctx or context.current()
            tgt = target or {'tenant_id': cur_ctx.tenant_id,
                             'user_id': cur_ctx.user_id}
            if action is None:
                act = '%s:%s' % (api, extension)
            else:
                act = '%s:%s:%s' % (api, extension, action)
            enforce(cur_ctx, act, tgt)
            return func(self, *args, **kwargs)

        return wrapped
    return decorator

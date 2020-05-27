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

"""Policy Engine For Blazar."""

import functools

from oslo_config import cfg
from oslo_log import log as logging
from oslo_policy import opts
from oslo_policy import policy

from blazar import context
from blazar import exceptions
from blazar import policies

CONF = cfg.CONF
LOG = logging.getLogger(__name__)


# TODO(gmann): Remove setting the default value of config policy_file
# once oslo_policy change the default value to 'policy.yaml'.
# https://github.com/openstack/oslo.policy/blob/a626ad12fe5a3abd49d70e3e5b95589d279ab578/oslo_policy/opts.py#L49
DEFAULT_POLICY_FILE = 'policy.yaml'
opts.set_defaults(CONF, DEFAULT_POLICY_FILE)


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
        _ENFORCER = policy.Enforcer(CONF)
        _ENFORCER.register_defaults(policies.list_rules())


def set_rules(data, default_rule=None):
    default_rule = default_rule or CONF.policy_default_rule
    if not _ENFORCER:
        LOG.debug("Enforcer not present, recreating at rules stage.")
        init()
    if default_rule:
        _ENFORCER.default_rule = default_rule
    _ENFORCER.set_rules(policy.Rules.load(data, default_rule))


def enforce(context, action, target, do_raise=True):
    """Verifies that the action is valid on the target in this context.

       :param context: blazar context
       :param action: string representing the action to be checked
           this should be colon separated for clarity.
           i.e. ``compute:create_instance``,
           ``compute:attach_volume``,
           ``volume:attach_volume``
       :param target: dictionary representing the object of the action
           for object creation this should be a dictionary representing the
           location of the object e.g. ``{'project_id': context.project_id}``
       :param do_raise: if True (the default), raises PolicyNotAuthorized;
           if False, returns False

       :raises blazar.exceptions.PolicyNotAuthorized: if verification fails
           and do_raise is True.

       :return: returns a non-False value (not necessarily "True") if
           authorized, and the exact value False if not authorized and
           do_raise is False.
    """

    init()

    credentials = context.to_policy_values()

    # Add the exceptions arguments if asked to do a raise
    extra = {}
    if do_raise:
        extra.update(exc=exceptions.PolicyNotAuthorized, action=action)

    return _ENFORCER.enforce(action, target, credentials, do_raise=do_raise,
                             **extra)


def authorize(extension, action=None, api='blazar', ctx=None,
              target=None):
    def decorator(func):

        @functools.wraps(func)
        def wrapped(self, *args, **kwargs):
            cur_ctx = ctx or context.current()
            tgt = target or {'project_id': cur_ctx.project_id,
                             'user_id': cur_ctx.user_id}
            if action is None:
                act = '%s:%s' % (api, extension)
            else:
                act = '%s:%s:%s' % (api, extension, action)
            enforce(cur_ctx, act, tgt)
            return func(self, *args, **kwargs)

        return wrapped
    return decorator

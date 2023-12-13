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


from oslo_config import cfg
from oslo_log import log as logging
from oslo_policy import opts


cli_opts = [
    cfg.HostAddressOpt('host', default='0.0.0.0',
                       help='Name of this node. This can be an opaque '
                            'identifier. It is not necessarily a hostname, '
                            'FQDN, or IP address. However, the node name must '
                            'be valid within an AMQP key, and if using '
                            'ZeroMQ (will be removed in the Stein release), a '
                            'valid hostname, FQDN, or IP address'),
    cfg.BoolOpt('log_exchange', default=False,
                help='Log request/response exchange details: environ, '
                     'headers and bodies'),
]

os_opts = [
    cfg.StrOpt('os_auth_protocol',
               default='http',
               help='Protocol used to access OpenStack Identity service'),
    cfg.HostAddressOpt('os_auth_host',
                       default='127.0.0.1',
                       help='IP or hostname of machine on which OpenStack '
                            'Identity service is located'),
    cfg.StrOpt('os_auth_port',
               default='5000',
               help='Port of OpenStack Identity service.'),
    cfg.StrOpt('os_auth_prefix',
               default='',
               help='Prefix of URL to access OpenStack Identity service.'),
    cfg.StrOpt('os_admin_username',
               default='admin',
               help='This OpenStack user is used to treat trusts. '
                    'The user must have admin role in <os_admin_project_name> '
                    'project.'),
    cfg.StrOpt('os_admin_password',
               default='blazar',
               help='Password of the admin user to treat trusts.'),
    cfg.StrOpt('os_admin_project_name',
               default='admin',
               help='Name of project where the user is admin.'),
    cfg.StrOpt('os_auth_version',
               default='v3',
               help='Blazar uses API v3 to allow trusts using.'),
    cfg.StrOpt('os_admin_user_domain_name',
               default='Default',
               help='A domain name the os_admin_username belongs to.'),
    cfg.StrOpt('os_admin_project_domain_name',
               default='Default',
               help='A domain name the os_admin_project_name belongs to'),
    cfg.StrOpt('cafile',
               help='Path of the custom CA certificates bundle.'),
]

api_opts = [
    cfg.BoolOpt('enable_v1_api',
                default=True,
                help='Deploy the v1 API.'),
]

lease_opts = [
    cfg.IntOpt('cleaning_time',
               default=0,
               min=0,
               help='The minimum interval [minutes] between the end of a '
                    'lease and the start of the next lease for the same '
                    'resource. This interval is used for cleanup.')
]

CONF = cfg.CONF
CONF.register_cli_opts(cli_opts)
CONF.register_opts(os_opts)
CONF.register_opts(api_opts)
CONF.register_opts(lease_opts)
logging.register_options(cfg.CONF)


def set_lib_defaults():
    """Update default value for configuration options from other namespace.

    Example, oslo lib config options. This is needed for
    config generator tool to pick these default value changes.
    https://docs.openstack.org/oslo.config/latest/cli/
    generator.html#modifying-defaults-from-other-namespaces
    """

    # TODO(gmann): Remove setting the default value of config policy_file
    # once oslo_policy change the default value to 'policy.yaml'.
    # https://github.com/openstack/oslo.policy/blob/a626ad12fe5a3abd49d70e3e5b95589d279ab578/oslo_policy/opts.py#L49
    opts.set_defaults(CONF, 'policy.yaml')

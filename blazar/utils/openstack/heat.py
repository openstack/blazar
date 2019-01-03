from keystoneauth1 import session
from keystoneauth1 import token_endpoint
from heatclient import client as heat_client
from oslo_config import cfg
from oslo_log import log as logging

from blazar import context
from blazar.utils.openstack import base
from blazar.utils.trusts import create_ctx_from_trust

heat_opts = [
    cfg.StrOpt(
        'heat_client_version',
        default='1',
        deprecated_group='DEFAULT',
        help='Heatclient version'),
    cfg.StrOpt(
        'orchestration_service',
        default='orchestration',
        deprecated_group='DEFAULT',
        help='Heat name in keystone')
]

CONF = cfg.CONF
CONF.register_opts(heat_opts, group='heat')
CONF.import_opt('identity_service', 'blazar.utils.openstack.keystone')
LOG = logging.getLogger(__name__)


class BlazarHeatClient(object):

    def __init__(self, ctx=None):

        if ctx is None:
            ctx = context.current()

        endpoint_override = base.url_for(
            ctx.service_catalog,
            CONF.heat.orchestration_service,
            os_region_name=CONF.os_region_name)

        auth = token_endpoint.Token(endpoint_override, ctx.auth_token)
        sess = session.Session(auth=auth)

        self.heat = heat_client.Client(
            CONF.heat.heat_client_version, session=sess)

    def __getattr_(self, name):
        return getattr(self.heat, name)



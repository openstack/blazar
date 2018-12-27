from keystoneauth1 import session
from heatclient import client as heat_client
from heatclient import exceptions as heat_exception
from oslo_config import cfg
from oslo_log import log as logging

from blazar import context

heat_opts = [
    cfg.StrOpt(
        'heat_client_version',
        default='2',
        deprecated_group='DEFAULT',
        help='Heatclient version'),
    cfg.StrOpt(
        'orchestration_service',
        default='orchestration',
        deprecated_group='DEFAULT',
        help='Heat name in keystone')
]

CONF = cfg.CONF
CONF.register_opts(heat_opts, group='nova')
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
        self.exceptions = heat_exceptions

    def __getattr_(self, name):
        return getattr(self.heat, name)

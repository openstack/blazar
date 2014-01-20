# Copyright (c) 2013 OpenStack Foundation
#
# Author: Swann Croiset <swann.croiset@bull.net>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import uuid as uuidgen

from novaclient import client
from novaclient import exceptions as nova_exceptions
from oslo.config import cfg

from climate import context
from climate.manager import exceptions as manager_exceptions
from climate.openstack.common import log as logging


LOG = logging.getLogger(__name__)

opts = [
    cfg.StrOpt('aggregate_freepool_name',
               default='freepool',
               help='Name of the special aggregate where all hosts '
                    'are candidate for physical host reservation'),
    cfg.StrOpt('tenant_id_key',
               default='climate:tenant',
               help='Aggregate metadata value for key matching tenant_id'),
    cfg.StrOpt('climate_owner',
               default='climate:owner',
               help='Aggregate metadata key for knowing owner tenant_id'),
    cfg.StrOpt('climate_az_prefix',
               default='climate:',
               help='Prefix for Availability Zones created by Climate'),
]

cfg.CONF.register_opts(opts, 'physical:host')


class ReservationPool(object):
    def __init__(self):
        self.ctx = context.current()
        self.freepool_name = cfg.CONF['physical:host'].aggregate_freepool_name

        #TODO(scroiset): use catalog to find the url
        auth_url = "%s://%s:%s/v2.0" % (cfg.CONF.os_auth_protocol,
                                        cfg.CONF.os_auth_host,
                                        cfg.CONF.os_auth_port)
        self.nova = client.Client('2',
                                  username=cfg.CONF.os_admin_username,
                                  api_key=cfg.CONF.os_admin_password,
                                  auth_url=auth_url,
                                  project_id=cfg.CONF.os_admin_tenant_name)

    def get_aggregate_from_name_or_id(self, aggregate_obj):
        """Return an aggregate by name or an id."""

        aggregate = None
        agg_id = None
        try:
            agg_id = int(aggregate_obj)
        except (ValueError, TypeError):
            if hasattr(aggregate_obj, 'id') and aggregate_obj.id:
                # pool is an aggregate
                agg_id = aggregate_obj.id

        if agg_id is not None:
            try:
                aggregate = self.nova.aggregates.get(agg_id)
            except nova_exceptions.NotFound:
                aggregate = None
        else:
            #FIXME(scroiset): can't get an aggregate by name
            # so iter over all aggregate and check for the good one
            all_aggregates = self.nova.aggregates.list()
            for agg in all_aggregates:
                if aggregate_obj == agg.name:
                    aggregate = agg
        if aggregate:
            return aggregate
        else:
            raise manager_exceptions.AggregateNotFound(pool=aggregate_obj)

    @staticmethod
    def _generate_aggregate_name():
        return str(uuidgen.uuid4())

    def create(self, name=None, az=True):
        """Create a Pool (an Aggregate) with or without Availability Zone.

        By default expose to user the aggregate with an Availability Zone.
        Return an aggregate or raise a nova exception.

        """

        name = name or self._generate_aggregate_name()

        if az:
            az_name = "%s%s" % (cfg.CONF['physical:host'].climate_az_prefix,
                                name)
            LOG.debug('Creating pool aggregate: %s'
                      'with Availability Zone %s' % (name, az_name))
            agg = self.nova.aggregates.create(name, az_name)
        else:
            LOG.debug('Creating pool aggregate: %s'
                      'without Availability Zone' % name)
            agg = self.nova.aggregates.create(name, None)

        meta = {cfg.CONF['physical:host'].climate_owner: self.ctx.tenant_id}
        self.nova.aggregates.set_metadata(agg, meta)

        return agg

    def delete(self, pool, force=True):
        """Delete an aggregate.

        pool can be an aggregate name or an aggregate id.
        Remove all hosts before delete aggregate (default).
        If force is False, raise exception if at least one
        host is attached to.

        """

        agg = self.get_aggregate_from_name_or_id(pool)

        hosts = agg.hosts
        if len(hosts) > 0 and not force:
            raise manager_exceptions.AggregateHaveHost(name=agg.name,
                                                       hosts=agg.hosts)
        try:
            freepool_agg = self.get(self.freepool_name)
        except manager_exceptions.AggregateNotFound:
            raise manager_exceptions.NoFreePool()
        for host in hosts:
            LOG.debug("Removing host '%s' from aggregate "
                      "'%s')" % (host, agg.id))
            self.nova.aggregates.remove_host(agg.id, host)

            if freepool_agg.id != agg.id:
                self.nova.aggregates.add_host(freepool_agg.id, host)

        self.nova.aggregates.delete(agg.id)

    def get_all(self):
        """Return all aggregate."""

        return self.nova.aggregates.list()

    def get(self, pool):
        """return details for aggregate pool or raise AggregateNotFound."""

        return self.get_aggregate_from_name_or_id(pool)

    def get_computehosts(self, pool):
        """Return a list of compute host names for an aggregate."""

        try:
            agg = self.get_aggregate_from_name_or_id(pool)
            return agg.hosts
        except manager_exceptions.AggregateNotFound:
            return []

    def add_computehost(self, pool, host):
        """Add a compute host to an aggregate.

        The `host` must exist otherwise raise an error
        and the `host` must be in the freepool.

        Return the related aggregate.
        Raise an aggregate exception if something wrong.
        """

        agg = self.get_aggregate_from_name_or_id(pool)

        try:
            freepool_agg = self.get(self.freepool_name)
        except manager_exceptions.AggregateNotFound:
            raise manager_exceptions.NoFreePool()

        if freepool_agg.id != agg.id:
            if host not in freepool_agg.hosts:
                raise manager_exceptions.HostNotInFreePool(
                    host=host, freepool_name=freepool_agg.name)
            LOG.info("removing host '%s' "
                     "from aggregate freepool %s" % (host, freepool_agg.name))
            try:
                self.remove_computehost(freepool_agg.id, host)
            except nova_exceptions.NotFound:
                raise manager_exceptions.HostNotFound(host=host)

        LOG.info("adding host '%s' to aggregate %s" % (host, agg.id))
        try:
            return self.nova.aggregates.add_host(agg.id, host)
        except nova_exceptions.NotFound:
            raise manager_exceptions.HostNotFound(host=host)
        except nova_exceptions.Conflict:
            raise manager_exceptions.AggregateAlreadyHasHost(pool=pool,
                                                             host=host)

    def remove_all_computehosts(self, pool):
        """Remove all compute hosts attached to an aggregate."""

        hosts = self.get_computehosts(pool)
        self.remove_computehost(pool, hosts)

    def remove_computehost(self, pool, hosts):
        """Remove compute host(s) from an aggregate."""

        if not isinstance(hosts, list):
            hosts = [hosts]

        agg = self.get_aggregate_from_name_or_id(pool)

        try:
            freepool_agg = self.get(self.freepool_name)
        except manager_exceptions.AggregateNotFound:
            raise manager_exceptions.NoFreePool()

        hosts_failing_to_remove = []
        hosts_failing_to_add = []
        hosts_not_in_freepool = []
        for host in hosts:
            if freepool_agg.id == agg.id:
                if host not in freepool_agg.hosts:
                    hosts_not_in_freepool.append(host)
                    continue
            try:
                self.nova.aggregates.remove_host(agg.id, host)
            except nova_exceptions.ClientException:
                hosts_failing_to_remove.append(host)
            if freepool_agg.id != agg.id:
                    # NOTE(sbauza) : We don't want to put again the host in
                    # freepool if the requested pool is the freepool...
                    try:
                        self.nova.aggregates.add_host(freepool_agg.id, host)
                    except nova_exceptions.ClientException:
                        hosts_failing_to_add.append(host)

        if hosts_failing_to_remove:
            raise manager_exceptions.CantRemoveHost(
                host=hosts_failing_to_remove, pool=agg)
        if hosts_failing_to_add:
            raise manager_exceptions.CantAddHost(host=hosts_failing_to_add,
                                                 pool=freepool_agg)
        if hosts_not_in_freepool:
            raise manager_exceptions.HostNotInFreePool(
                host=hosts_not_in_freepool, freepool_name=freepool_agg.name)

    def add_project(self, pool, project_id):
        """Add a project to an aggregate."""

        metadata = {project_id: cfg.CONF['physical:host'].tenant_id_key}

        agg = self.get_aggregate_from_name_or_id(pool)

        return self.nova.aggregates.set_metadata(agg.id, metadata)

    def remove_project(self, pool, project_id):
        """Remove a project from an aggregate."""

        agg = self.get_aggregate_from_name_or_id(pool)

        metadata = {project_id: None}
        return self.nova.aggregates.set_metadata(agg.id, metadata)

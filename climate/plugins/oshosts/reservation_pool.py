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

from novaclient import exceptions as nova_exceptions
from oslo_config import cfg
from oslo_log import log as logging

from climate import context
from climate.manager import exceptions as manager_exceptions
from climate.plugins import oshosts as plugin
from climate.utils.openstack import nova


LOG = logging.getLogger(__name__)

OPTS = [
    cfg.StrOpt('aggregate_freepool_name',
               default='freepool',
               help='Name of the special aggregate where all hosts '
                    'are candidate for physical host reservation'),
    cfg.StrOpt('project_id_key',
               default='climate:project',
               help='Aggregate metadata value for key matching project_id'),
    cfg.StrOpt('climate_owner',
               default='climate:owner',
               help='Aggregate metadata key for knowing owner project_id'),
    cfg.StrOpt('climate_az_prefix',
               default='climate:',
               help='Prefix for Availability Zones created by Climate'),
]

CONF = cfg.CONF
CONF.register_opts(OPTS, group=plugin.RESOURCE_TYPE)


class ReservationPool(nova.NovaClientWrapper):
    def __init__(self):
        super(ReservationPool, self).__init__()
        self.config = CONF[plugin.RESOURCE_TYPE]
        self.freepool_name = self.config.aggregate_freepool_name

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
            # FIXME(scroiset): can't get an aggregate by name
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
            az_name = "%s%s" % (self.config.climate_az_prefix,
                                name)
            LOG.debug('Creating pool aggregate: %s '
                      'with Availability Zone %s' % (name, az_name))
            agg = self.nova.aggregates.create(name, az_name)
        else:
            LOG.debug('Creating pool aggregate: %s '
                      'without Availability Zone' % name)
            agg = self.nova.aggregates.create(name, None)

        project_id = None
        try:
            ctx = context.current()
            project_id = ctx.project_id
        except RuntimeError:
            e = manager_exceptions.ProjectIdNotFound()
            LOG.error(e.message)
            raise e

        meta = {self.config.climate_owner: project_id}
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

        :param pool: Name or UUID of the pool to rattach the host
        :param host: Name (not UUID) of the host to associate
        :type host: str

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

        metadata = {project_id: self.config.project_id_key}

        agg = self.get_aggregate_from_name_or_id(pool)

        return self.nova.aggregates.set_metadata(agg.id, metadata)

    def remove_project(self, pool, project_id):
        """Remove a project from an aggregate."""

        agg = self.get_aggregate_from_name_or_id(pool)

        metadata = {project_id: None}
        return self.nova.aggregates.set_metadata(agg.id, metadata)

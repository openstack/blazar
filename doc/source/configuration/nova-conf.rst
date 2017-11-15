=========
nova.conf
=========

Please add the following lines to the nova.conf configuration file:

.. sourcecode:: console

    [filter_scheduler]
    available_filters = nova.scheduler.filters.all_filters
    available_filters = blazarnova.scheduler.filters.blazar_filter.BlazarFilter
    enabled_filters=RetryFilter,AvailabilityZoneFilter,RamFilter,ComputeFilter,ComputeCapabilitiesFilter,ImagePropertiesFilter,AggregateInstanceExtraSpecsFilter,AggregateMultiTenancyIsolation,ServerGroupAntiAffinityFilter,BlazarFilter

..

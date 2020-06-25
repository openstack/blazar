# Install and start **blazar** reservation service

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set +o xtrace

# Support entry points installation of console scripts
if [[ -d $BLAZAR_DIR/bin ]]; then
    BLAZAR_BIN_DIR=$BLAZAR_DIR/bin
else
    BLAZAR_BIN_DIR=$(get_python_exec_prefix)
fi

# These packages should be tested under Python 3 when enabled by DevStack
enable_python3_package blazar blazar-nova python-blazarclient

# Test if any Blazar services are enabled
# is_blazar_enabled
function is_blazar_enabled {
    [[ ,${ENABLED_SERVICES} =~ ,"blazar-" ]] && return 0
    return 1
}

# configure_blazar() - Set config files, create data dirs, etc
function configure_blazar {
    if [[ ! -d $BLAZAR_CONF_DIR ]]; then
        sudo mkdir -p $BLAZAR_CONF_DIR
    fi
    sudo chown $STACK_USER $BLAZAR_CONF_DIR

    touch $BLAZAR_CONF_FILE

    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_version v3
    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_host $(ipv6_unquote $KEYSTONE_AUTH_HOST)
    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_port 80
    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_prefix identity
    iniset $BLAZAR_CONF_FILE DEFAULT os_admin_password $SERVICE_PASSWORD
    iniset $BLAZAR_CONF_FILE DEFAULT os_admin_username blazar
    iniset $BLAZAR_CONF_FILE DEFAULT os_admin_project_name $SERVICE_TENANT_NAME
    iniset $BLAZAR_CONF_FILE DEFAULT identity_service $BLAZAR_IDENTITY_SERVICE_NAME
    iniset $BLAZAR_CONF_FILE DEFAULT os_region_name $REGION_NAME

    # Keystone authtoken
    _blazar_setup_keystone $BLAZAR_CONF_FILE keystone_authtoken

    iniset $BLAZAR_CONF_FILE nova aggregate_freepool_name $BLAZAR_FREEPOOL_NAME

    iniset $BLAZAR_CONF_FILE DEFAULT host $(ipv6_unquote $SERVICE_HOST)
    iniset $BLAZAR_CONF_FILE DEFAULT debug $BLAZAR_DEBUG

    iniset $BLAZAR_CONF_FILE manager plugins physical.host.plugin,virtual.instance.plugin,virtual.floatingip.plugin

    iniset $BLAZAR_CONF_FILE api api_v2_controllers oshosts,leases

    iniset $BLAZAR_CONF_FILE database connection `database_connection_url blazar`

    iniset $BLAZAR_CONF_FILE DEFAULT use_syslog $SYSLOG

    iniset_rpc_backend blazar $BLAZAR_CONF_FILE DEFAULT

    setup_logging $BLAZAR_CONF_FILE

    ACTUAL_FILTERS=$(iniget $NOVA_CONF filter_scheduler enabled_filters)
    if [[ -z "$ACTUAL_FILTERS" ]]; then
        iniadd $NOVA_CONF filter_scheduler enabled_filters "RetryFilter, AvailabilityZoneFilter, RamFilter, ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter, AggregateInstanceExtraSpecsFilter, AggregateMultiTenancyIsolation, ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter, BlazarFilter"
    else
        if [[ $ACTUAL_FILTERS != *AggregateInstanceExtraSpecsFilter* ]];  then
	    ACTUAL_FILTERS="$ACTUAL_FILTERS,AggregateInstanceExtraSpecsFilter"
        fi
        if [[ $ACTUAL_FILTERS != *AggregateMultiTenancyIsolation* ]];  then
	    ACTUAL_FILTERS="$ACTUAL_FILTERS,AggregateMultiTenancyIsolation"
        fi
        if [[ $ACTUAL_FILTERS != *ServerGroupAntiAffinityFilter* ]];  then
	    ACTUAL_FILTERS="$ACTUAL_FILTERS,ServerGroupAntiAffinityFilter"
        fi
        if [[ $ACTUAL_FILTERS != *BlazarFilter* ]];  then
	    ACTUAL_FILTERS="$ACTUAL_FILTERS,BlazarFilter"
        fi
	iniset $NOVA_CONF filter_scheduler enabled_filters $ACTUAL_FILTERS
    fi

    ACTUAL_AVAILABLE_FILTERS=$(iniget $NOVA_CONF filter_scheduler available_filters)
    if [[ -z "$ACTUAL_AVAILABLE_FILTERS" ]]; then
        iniset $NOVA_CONF filter_scheduler available_filters "nova.scheduler.filters.all_filters"
    fi
    iniadd $NOVA_CONF filter_scheduler available_filters "blazarnova.scheduler.filters.blazar_filter.BlazarFilter"

    if [[ "$BLAZAR_USE_MOD_WSGI" == "True" ]]; then
        write_uwsgi_config "$BLAZAR_UWSGI_CONF" "$BLAZAR_UWSGI" "/reservation"
    fi

    # Database
    recreate_database blazar utf8

    # Run Blazar db migrations
    $BLAZAR_BIN_DIR/blazar-db-manage --config-file $BLAZAR_CONF_FILE upgrade head
}

# Configures Keystone integration for the Blazar service
function _blazar_setup_keystone {
    local conf_file=$1
    local section=$2

    configure_keystone_authtoken_middleware $conf_file $BLAZAR_USER_NAME $section
}

# create_blazar_aggregate_freepool() - Create a Nova aggregate to use as freepool (for host reservation)
function create_blazar_aggregate_freepool {
    openstack --os-region-name $REGION_NAME aggregate create $BLAZAR_FREEPOOL_NAME
}

# create_blazar_accounts() - Set up common required Blazar accounts
#
# Tenant               User       Roles
# ------------------------------------------------------------------
# service              blazar     admin        # if enabled
#
function create_blazar_accounts {
    SERVICE_TENANT=$(openstack project list | awk "/ $SERVICE_TENANT_NAME / { print \$2 }")
    ADMIN_ROLE=$(openstack role list | awk "/ admin / { print \$2 }")

    BLAZAR_USER_ID=$(get_or_create_user $BLAZAR_USER_NAME \
        "$SERVICE_PASSWORD" "default" "blazar@example.com")
    get_or_add_user_project_role $ADMIN_ROLE $BLAZAR_USER_ID $SERVICE_TENANT

    if [[ "$BLAZAR_USE_MOD_WSGI" == "True" ]]; then
        blazar_api_url="$BLAZAR_SERVICE_PROTOCOL://$BLAZAR_SERVICE_HOST/reservation"
    else
        blazar_api_url="$BLAZAR_SERVICE_PROTOCOL://$BLAZAR_SERVICE_HOST:$BLAZAR_SERVICE_PORT"
    fi

    BLAZAR_SERVICE=$(get_or_create_service "blazar" \
        "reservation" "Blazar Reservation Service")
    get_or_create_endpoint $BLAZAR_SERVICE \
        "$REGION_NAME" \
        "$blazar_api_url/v1"

    KEYSTONEV3_SERVICE=$(get_or_create_service "keystonev3" \
        "identityv3" "Keystone Identity Service V3")
    get_or_create_endpoint $KEYSTONEV3_SERVICE \
        "$REGION_NAME" \
        "$KEYSTONE_SERVICE_PROTOCOL://$KEYSTONE_SERVICE_HOST:$KEYSTONE_SERVICE_PORT/v3" \
        "$KEYSTONE_AUTH_PROTOCOL://$KEYSTONE_AUTH_HOST:$KEYSTONE_AUTH_PORT/v3" \
        "$KEYSTONE_SERVICE_PROTOCOL://$KEYSTONE_SERVICE_HOST:$KEYSTONE_SERVICE_PORT/v3"
}


# install_blazar() - Collect sources and install
function install_blazar {
    echo "Install"
    git_clone $BLAZAR_REPO $BLAZAR_DIR $BLAZAR_BRANCH
    git_clone $BLAZARCLIENT_REPO $BLAZARCLIENT_DIR $BLAZARCLIENT_BRANCH
    git_clone $BLAZARNOVA_REPO $BLAZARNOVA_DIR $BLAZARNOVA_BRANCH

    setup_develop $BLAZAR_DIR
    setup_develop $BLAZARCLIENT_DIR
    setup_develop $BLAZARNOVA_DIR
}


# install_blazar_dashboard() - Install Blazar dashboard for Horizon
function install_blazar_dashboard {
    git_clone $BLAZAR_DASHBOARD_REPO $BLAZAR_DASHBOARD_DIR $BLAZAR_DASHBOARD_BRANCH
    setup_develop $BLAZAR_DASHBOARD_DIR
    blazar_setup_horizon
}


# Set up Horizon integration with Blazar
function blazar_setup_horizon {
    # Link Dashboard panel to Horizon's directory
    ln -fs $BLAZAR_DASHBOARD_DIR/blazar_dashboard/enabled/_90_admin_reservation_panelgroup.py $HORIZON_DIR/openstack_dashboard/local/enabled/
    ln -fs $BLAZAR_DASHBOARD_DIR/blazar_dashboard/enabled/_90_project_reservations_panelgroup.py $HORIZON_DIR/openstack_dashboard/local/enabled/
    ln -fs $BLAZAR_DASHBOARD_DIR/blazar_dashboard/enabled/_91_admin_reservation_hosts_panel.py $HORIZON_DIR/openstack_dashboard/local/enabled/
    ln -fs $BLAZAR_DASHBOARD_DIR/blazar_dashboard/enabled/_91_project_reservations_leases_panel.py $HORIZON_DIR/openstack_dashboard/local/enabled/

    # Restart Horizon
    restart_apache_server
}


# start_blazar() - Start running processes, including screen
function start_blazar {
    if [ "$BLAZAR_USE_MOD_WSGI" == "True" ]; then
        run_process 'blazar-a' "$(which uwsgi) --ini $BLAZAR_UWSGI_CONF"
    else
        run_process blazar-a "$BLAZAR_BIN_DIR/blazar-api --debug --config-file $BLAZAR_CONF_FILE"
    fi
    run_process blazar-m "$BLAZAR_BIN_DIR/blazar-manager --debug --config-file $BLAZAR_CONF_FILE"
}


# stop_blazar() - Stop running processes
function stop_blazar {
    for serv in blazar-a blazar-m; do
        stop_process $serv
    done
}


# clean_blazar_configuration() - Cleanup blazar configurations
function clean_blazar_configuration {
    if [[ "$BLAZAR_USE_MOD_WSGI" == "True" ]]; then
        remove_uwsgi_config "$BLAZAR_UWSGI_CONF" "$BLAZAR_UWSGI"
    fi
}


if is_service_enabled blazar blazar-m blazar-a; then
    if [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing Blazar"
        # Use stack_install_service here to account for virtualenv
        stack_install_service blazar

        if is_service_enabled horizon; then
            install_blazar_dashboard
        fi

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring Blazar"
        configure_blazar
        create_blazar_accounts
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Creating Nova aggregate used as freepool for Blazar Host Reservation"
        create_blazar_aggregate_freepool
        # Start the services
        start_blazar
    fi

    if [[ "$1" == "unstack" ]]; then
        echo_summary "Shutting Down Blazar"
        stop_blazar
        clean_blazar_configuration
    fi

fi

# Restore xtrace
$XTRACE

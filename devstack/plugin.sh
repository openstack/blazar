# Install and start **blazar** reservations service

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set +o xtrace

# Support entry points installation of console scripts
if [[ -d $BLAZAR_DIR/bin ]]; then
    BLAZAR_BIN_DIR=$BLAZAR_DIR/bin
else
    BLAZAR_BIN_DIR=$(get_python_exec_prefix)
fi

# Test if any Ceilometer services are enabled
# is_ceilometer_enabled
function is_blazar_enabled {
    [[ ,${ENABLED_SERVICES} =~ ,"blazar-" ]] && return 0
    return 1
}

# Oslo.Messaging RPC iniupdate cofiguration
function iniupdate_rpc_backend {
    local file=$1
    local section=$2
    if is_service_enabled zeromq; then
        iniset $file $section rpc_backend zmq
    elif is_service_enabled qpid || [ -n "$QPID_HOST" ]; then
        iniset $file $section rpc_backend qpid
    elif is_service_enabled rabbit || { [ -n "$RABBIT_HOST" ] && [ -n "$RABBIT_PASSWORD" ]; }; then
        iniset $file $section rpc_backend rabbit
    fi
}

# configure_blazar() - Set config files, create data dirs, etc
function configure_blazar {
    if [[ ! -d $BLAZAR_CONF_DIR ]]; then
        sudo mkdir -p $BLAZAR_CONF_DIR
    fi
    sudo chown $STACK_USER $BLAZAR_CONF_DIR

    BLAZAR_POLICY_FILE=$BLAZAR_CONF_DIR/policy.json
    cp $BLAZAR_DIR/etc/policy.json $BLAZAR_POLICY_FILE

    touch $BLAZAR_CONF_FILE

    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_version v3
    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_port 80
    iniset $BLAZAR_CONF_FILE DEFAULT os_auth_prefix identity
    iniset $BLAZAR_CONF_FILE DEFAULT os_admin_password $SERVICE_PASSWORD
    iniset $BLAZAR_CONF_FILE DEFAULT os_admin_username blazar
    iniset $BLAZAR_CONF_FILE DEFAULT os_admin_project_name $SERVICE_TENANT_NAME
    iniset $BLAZAR_CONF_FILE DEFAULT identity_service $BLAZAR_IDENTITY_SERVICE_NAME

    # keystone authtoken
    _blazar_setup_keystone $BLAZAR_CONF_FILE keystone_authtoken

    iniset $BLAZAR_CONF_FILE physical:host aggregate_freepool_name $BLAZAR_FREEPOOL_NAME

    iniset $BLAZAR_CONF_FILE DEFAULT host $HOST_IP
    iniset $BLAZAR_CONF_FILE DEFAULT debug $BLAZAR_DEBUG
    iniset $BLAZAR_CONF_FILE DEFAULT verbose $BLAZAR_VERBOSE

    iniset $BLAZAR_CONF_FILE manager plugins basic.vm.plugin,physical.host.plugin

    iniset $BLAZAR_CONF_FILE api api_v2_controllers oshosts,leases

    iniset $BLAZAR_CONF_FILE database connection `database_connection_url blazar`

    iniset $BLAZAR_CONF_FILE DEFAULT use_syslog $SYSLOG

    iniset_rpc_backend blazar $BLAZAR_CONF_FILE DEFAULT
    iniupdate_rpc_backend $BLAZAR_CONF_FILE DEFAULT

    ACTUAL_FILTERS=$(iniget $NOVA_CONF filter_scheduler enabled_filters)
    if [[ -z "$ACTUAL_FILTERS" ]]; then
        iniadd $NOVA_CONF filter_scheduler enabled_filters "RetryFilter, AvailabilityZoneFilter, RamFilter, ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter, ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter, BlazarFilter"
    else
        iniset $NOVA_CONF filter_scheduler enabled_filters "$ACTUAL_FILTERS,BlazarFilter"
    fi

    ACTUAL_AVAILABLE_FILTERS=$(iniget $NOVA_CONF filter_scheduler available_filters)
    if [[ -z "$ACTUAL_AVAILABLE_FILTERS" ]]; then
        iniset $NOVA_CONF filter_scheduler available_filters "nova.scheduler.filters.all_filters"
    fi
    iniadd $NOVA_CONF filter_scheduler available_filters "blazarnova.scheduler.filters.blazar_filter.BlazarFilter"

    # TODO(hiro-kobayashi): This line should be deleted after the patch
    # https://review.openstack.org/#/c/471590/ is merged.
    iniadd $NOVA_CONF blazar:physical:host blazar_az_prefix blazar_

    # Database
    recreate_database blazar utf8

    # Run Blazar db migrations
    $BLAZAR_BIN_DIR/blazar-db-manage --config-file $BLAZAR_CONF_FILE upgrade head
}

# Configures keystone integration for blazar service
function _blazar_setup_keystone {
    local conf_file=$1
    local section=$2
    local use_auth_url=$3

    if [[ -z $skip_auth_cache ]]; then
        iniset $conf_file $section signing_dir $BLAZAR_AUTH_CACHE_DIR
        # Create cache dir
        create_blazar_cache_dir
    fi

    configure_auth_token_middleware $conf_file $BLAZAR_USER_NAME $BLAZAR_AUTH_CACHE_DIR $section
}

# create_blazar_cache_dir() - Part of the _blazar_setup_keystone process
function create_blazar_cache_dir {
    # Create cache dir
    sudo mkdir -m 700 -p $BLAZAR_AUTH_CACHE_DIR
    sudo chown $STACK_USER $BLAZAR_AUTH_CACHE_DIR
    rm -f $BLAZAR_AUTH_CACHE_DIR/*
}

# create_blazar_aggregate_freepool() - Create a Nova aggregate to use as freepool (for host reservation)
function create_blazar_aggregate_freepool {
    openstack aggregate create $BLAZAR_FREEPOOL_NAME
}

# create_blazar_accounts() - Set up common required BLAZAR accounts
#
# Tenant               User       Roles
# ------------------------------------------------------------------
# service              BLAZAR     admin        # if enabled
#
function create_blazar_accounts {
    SERVICE_TENANT=$(openstack project list | awk "/ $SERVICE_TENANT_NAME / { print \$2 }")
    ADMIN_ROLE=$(openstack role list | awk "/ admin / { print \$2 }")

    BLAZAR_USER_ID=$(get_or_create_user $BLAZAR_USER_NAME \
        "$SERVICE_PASSWORD" "default" "blazar@example.com")
    get_or_add_user_project_role $ADMIN_ROLE $BLAZAR_USER_ID $SERVICE_TENANT

    BLAZAR_SERVICE=$(get_or_create_service "blazar" \
        "reservation" "Blazar Reservations Service")
    get_or_create_endpoint $BLAZAR_SERVICE \
        "$REGION_NAME" \
        "$BLAZAR_SERVICE_PROTOCOL://$BLAZAR_SERVICE_HOST:$BLAZAR_SERVICE_PORT/v1" \
        "$BLAZAR_SERVICE_PROTOCOL://$BLAZAR_SERVICE_HOST:$BLAZAR_SERVICE_PORT/v1" \
        "$BLAZAR_SERVICE_PROTOCOL://$BLAZAR_SERVICE_HOST:$BLAZAR_SERVICE_PORT/v1"

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


# start_blazar() - Start running processes, including screen
function start_blazar {
    run_process blazar-a "$BLAZAR_BIN_DIR/blazar-api --debug --config-file $BLAZAR_CONF_FILE"
    run_process blazar-m "$BLAZAR_BIN_DIR/blazar-manager --debug --config-file $BLAZAR_CONF_FILE"
}


# stop_blazar() - Stop running processes
function stop_blazar {
    for serv in blazar-a blazar-m; do
        stop_process $serv
    done
}


if is_service_enabled blazar blazar-m blazar-a; then
    if [[ "$1" == "stack" && "$2" == "pre-config" ]]; then
        echo "Pre installation steps for Blazar"
        iniupdate_rpc_backend
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing Blazar"
        # Use stack_install_service here to account for vitualenv
        stack_install_service blazar
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
    fi

fi

# Restore xtrace
$XTRACE

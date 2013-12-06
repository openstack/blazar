if is_service_enabled climate; then
    if [[ "$1" == "source" ]]; then
        source $TOP_DIR/lib/keystone
        source $TOP_DIR/lib/nova
        source $TOP_DIR/lib/climate
    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        echo_summary "Installing Climate"
        install_climate
    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        echo_summary "Configuring Climate"
        create_climate_accounts
        configure_climate
    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        echo_summary "Starting Climate"
        start_climate
    elif [[ "$1" == "unstack" ]]; then
        stop_climate
    fi
fi

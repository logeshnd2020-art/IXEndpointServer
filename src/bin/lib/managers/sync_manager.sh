#!/bin/bash

#########################################
# IX Endpoint Services
# Sync Manager
#########################################

sync_manager() {

    log_info "Starting synchronization..."

    #################################
    # Heartbeat
    #################################

    send_payload

    #################################
    # Inventory
    #################################

    send_inventory

    #################################
    # Applications
    #################################

    send_applications

    #################################
    # Retry Failed Uploads
    #################################

    retry_upload_queue

    log_info "Synchronization completed."

}

#!/bin/bash

echo "Setting CPU frequency..."
sudo cpupower -c 0-35 frequency-set -g performance > /dev/null 2>&1
sudo cpupower -c 0-35 frequency-set -d 2.5GHz -u 2.5GHz > /dev/null 2>&1


echo "Resetting affinity for target containers..."
TARGET_POD_IDS=$(sudo crictl pods -q --name "hotel-reserv|istio-proxy")

for POD_ID in $TARGET_POD_IDS; do
    CONTAINERS=$(sudo crictl ps -q --pod "$POD_ID")
    for CID in $CONTAINERS; do
        PID=$(sudo crictl inspect "$CID" 2>/dev/null | jq -r '.info.pid')
        # PID가 비어있지 않고 null이 아닐 때만 실행
        if [ -n "$PID" ] && [ "$PID" != "null" ]; then
            sudo taskset -apc 0-35 "$PID" > /dev/null 2>&1
            for CHILD in $(pgrep -P "$PID" 2>/dev/null); do
                sudo taskset -apc 0-35 "$CHILD" > /dev/null 2>&1
            done
        fi
    done
done

pin_service_pod() {
    local POD_PATTERN=$1
    local APP_NAME=$2
    local APP_CORES=$3
    local PROXY_CORES=$4

    echo "Scanning for pods matching: '$POD_PATTERN' (excluding mongo/memcached)..."

    POD_IDS=$(sudo crictl pods --name "$POD_PATTERN" -q | grep -v -E "mongodb|memcached")

    if [ -z "$POD_IDS" ]; then
        echo " -> [Skip] No matching pods found."
        return
    fi

    for POD_ID in $POD_IDS; do
        POD_FULL_NAME=$(sudo crictl inspectp "$POD_ID" 2>/dev/null | jq -r '.status.name')
        echo " -> Processing Pod: $POD_FULL_NAME ($POD_ID)"

        APP_CID=$(sudo crictl ps --pod "$POD_ID" --name "$APP_NAME" -q | head -n 1)
        
        if [ -n "$APP_CID" ]; then
            APP_REAL_NAME=$(sudo crictl inspect "$APP_CID" 2>/dev/null | jq -r '.status.metadata.name')
            
            if [[ "$APP_REAL_NAME" == *"mongo"* ]] || [[ "$APP_REAL_NAME" == *"memcached"* ]]; then
                 echo "    [Skip] Ignored DB/Cache container: $APP_REAL_NAME"
            else
                PID=$(sudo crictl inspect "$APP_CID" 2>/dev/null | jq -r '.info.pid')
                if [ -n "$PID" ] && [ "$PID" != "null" ]; then
                    echo "    [App] $APP_REAL_NAME (PID: $PID) -> Cores $APP_CORES"
                    sudo taskset -apc "$APP_CORES" "$PID" > /dev/null
                fi
            fi
        fi

        PROXY_CID=$(sudo crictl ps --pod "$POD_ID" --name "istio-proxy" -q | head -n 1)
        if [ -n "$PROXY_CID" ]; then
            PID=$(sudo crictl inspect "$PROXY_CID" 2>/dev/null | jq -r '.info.pid')
            if [ -n "$PID" ] && [ "$PID" != "null" ]; then
                echo "    [Proxy] istio-proxy (PID: $PID) -> Cores $PROXY_CORES"
                sudo taskset -apc "$PROXY_CORES" "$PID" > /dev/null
                for CHILD in $(pgrep -P "$PID" 2>/dev/null); do
                    sudo taskset -apc "$PROXY_CORES" "$CHILD" > /dev/null
                done
            fi
        fi
    done
}

pin_infra_container() {
    local CONTAINER_NAME=$1
    local CORES=$2

    echo "Pinning infra container: '$CONTAINER_NAME' -> Cores $CORES"

    for CID in $(sudo crictl ps --name "$CONTAINER_NAME" -q 2>/dev/null); do
        PID=$(sudo crictl inspect "$CID" 2>/dev/null | jq -r '.info.pid')
        if [ -n "$PID" ] && [ "$PID" != "null" ]; then
            echo "    [Infra] $CONTAINER_NAME (PID: $PID) -> Cores $CORES"
            sudo taskset -apc "$CORES" "$PID" > /dev/null
        fi
    done
}

# # Rate Service
# pin_service_pod "rate-" "hotel-reserv-rate" "0-17" "0-17"

# # Reservation Service
# pin_service_pod "reservation-" "hotel-reserv-reservation" "0-17" "0-17"

# # Search Service
# pin_service_pod "search-" "hotel-reserv-search" "0-17" "0-17"

# # Profile Service
# pin_service_pod "profile-" "hotel-reserv-profile" "0-17" "0-17"

# # Frontend Service
# pin_service_pod "frontend-" "hotel-reserv-frontend" "0-17" "0-17"

# # Geo Service
# pin_service_pod "geo-" "hotel-reserv-geo" "0-17" "0-17"

# # Memcached
# pin_infra_container "hotel-reserv-profile-mmc" "0-17"
# pin_infra_container "hotel-reserv-rate-mmc" "0-17"
# pin_infra_container "hotel-reserv-reservation-mmc" "0-17"

# Rate Service
pin_service_pod "rate-" "hotel-reserv-rate" "0-2" "0-2"

# Reservation Service
pin_service_pod "reservation-" "hotel-reserv-reservation" "3-5" "3-5"

# Search Service
pin_service_pod "search-" "hotel-reserv-search" "6-8" "6-8"

# Profile Service
pin_service_pod "profile-" "hotel-reserv-profile" "9-11" "9-11"

# Frontend Service
pin_service_pod "frontend-" "hotel-reserv-frontend" "11-15" "11-15"

# Geo Service
pin_service_pod "geo-" "hotel-reserv-geo" "16-17" "16-17"

# Memcached
pin_infra_container "hotel-reserv-profile-mmc" "16-17"
pin_infra_container "hotel-reserv-rate-mmc" "16-17"
pin_infra_container "hotel-reserv-reservation-mmc" "16-17"

echo "Done."
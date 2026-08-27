#!/usr/bin/env bash
set -euo pipefail

############################################
# User-configurable knobs (only these)
############################################
THREADS="${THREADS:-28}"         # -t
CONNS="${CONNS:-4096}"           # -c
RATE_START="${RATE_START:-35000}" # -R start
RATE_END="${RATE_END:-53000}"   # -R end (inclusive)
RATE_STEP="${RATE_STEP:-3000}"  # -R step

############################################
# Fixed settings (do not change)
############################################
CPUSET="0-25"
DURATION="30s"
URL="${URL:-http://172.18.0.3:30080}"  # frontend NodePort on kind cluster "dsb"
SCRIPT="$HOME/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/user_only.lua"
WRK="${WRK:-$HOME/DeathStarBench/wrk2/wrk}"  # system wrk lacks -R; use the wrk2 build

# Print header (optional). Comment out if you want absolutely no header.
echo "rate,rps,p50,p99"

to_ms_or_s() {
  # Input: "6.56s" or "10.12s" or "750.5ms" or "845.3us" or "1.23m" (rare)
  # Output: only ms or s units.
  local v="$1"
  if [[ "$v" =~ ^([0-9]+(\.[0-9]+)?)us$ ]]; then
    # microseconds -> ms
    awk -v x="${BASH_REMATCH[1]}" 'BEGIN{printf "%.3fms", x/1000.0}'
  elif [[ "$v" =~ ^([0-9]+(\.[0-9]+)?)ms$ ]]; then
    printf "%sms" "${BASH_REMATCH[1]}"
  elif [[ "$v" =~ ^([0-9]+(\.[0-9]+)?)s$ ]]; then
    printf "%ss" "${BASH_REMATCH[1]}"
  elif [[ "$v" =~ ^([0-9]+(\.[0-9]+)?)m$ ]]; then
    # minutes -> seconds (keep s)
    awk -v x="${BASH_REMATCH[1]}" 'BEGIN{printf "%.3fs", x*60.0}'
  else
    # Fallback: return as-is (shouldn't happen)
    printf "%s" "$v"
  fi
}

for (( rate=RATE_START; rate<=RATE_END; rate+=RATE_STEP )); do
  # Run wrk, capture full output silently (no other prints)
  out="$(
    taskset -c "$CPUSET" "$WRK" \
      -t "$THREADS" -c "$CONNS" -d "$DURATION" -L \
      -s "$SCRIPT" "$URL" -R "$rate"
  )"

  # Extract Requests/sec
  rps="$(awk '/^Requests\/sec:/ {print $2}' <<< "$out")"
  # Extract p50 and p99 from the "Latency Distribution" block
  p50_raw="$(awk '/^ *50\.000%/ {print $2; exit}' <<< "$out")"
  p99_raw="$(awk '/^ *99\.000%/ {print $2; exit}' <<< "$out")"

  # Normalize units to ms or s only
  p50="$(to_ms_or_s "$p50_raw")"
  p99="$(to_ms_or_s "$p99_raw")"

  # Output only the record
  echo "${rate},${rps},${p50},${p99}"

  # 5-second gap between measurements
  sleep 5
done

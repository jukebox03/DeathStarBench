#!/bin/bash
# quick_test.sh - 3가지 시나리오 연속 실행

TARGET="http://localhost:31643"
WRK="./wrk"
SCRIPTS="./DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation"
DURATION="60s"
RPS=3000

mkdir -p results

for scenario in "search_only:random" "search_only_fixed:fixed" "search_only_fixed_four:distributed"; do
    SCRIPT=$(echo $scenario | cut -d: -f1)
    NAME=$(echo $scenario | cut -d: -f2)
    
    echo "=========================================="
    echo "Testing: $NAME"
    echo "=========================================="
    
    # Warmup
    echo "Warming up..."
    $WRK -t 2 -c 50 -d 30s -L -s $SCRIPTS/${SCRIPT}.lua $TARGET -R 500 > /dev/null 2>&1
    
    sleep 10
    
    # Main test
    echo "Running main test..."
    $WRK -t 4 -c 100 -d $DURATION -L -s $SCRIPTS/${SCRIPT}.lua $TARGET -R $RPS \
        | tee results/${1:-baseline}_${NAME}.log
    
    echo "Cooldown 30s..."
    sleep 30
done

echo "All tests complete!"
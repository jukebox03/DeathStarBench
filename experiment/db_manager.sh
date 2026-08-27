#!/bin/bash
# db_manager.sh - DB 상태 확인 및 초기화 스크립트

NAMESPACE="hotel-res"

# MongoDB pod 이름 동적으로 찾기
get_mongo_pod() {
    local app=$1
    kubectl get pods -n $NAMESPACE -l io.kompose.service=mongodb-$app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

# DB 상태 확인 함수
check_db() {
    echo "=== DB Status Check ==="
    echo ""
    
    local geo_pod=$(get_mongo_pod "geo")
    local rate_pod=$(get_mongo_pod "rate")
    local profile_pod=$(get_mongo_pod "profile")
    local recommendation_pod=$(get_mongo_pod "recommendation")
    local user_pod=$(get_mongo_pod "user")
    
    echo "geo-db:"
    kubectl exec -it $geo_pod -n $NAMESPACE -- mongo geo-db --quiet --eval "print('  count: ' + db.geo.count() + ', unique: ' + db.geo.distinct('hotelId').length)"
    
    echo "rate-db:"
    kubectl exec -it $rate_pod -n $NAMESPACE -- mongo rate-db --quiet --eval "print('  count: ' + db.inventory.count() + ', unique: ' + db.inventory.distinct('hotelId').length)"
    
    echo "profile-db:"
    kubectl exec -it $profile_pod -n $NAMESPACE -- mongo profile-db --quiet --eval "print('  count: ' + db.hotels.count() + ', unique: ' + db.hotels.distinct('id').length)"
    
    echo "recommendation-db:"
    kubectl exec -it $recommendation_pod -n $NAMESPACE -- mongo recommendation-db --quiet --eval "print('  count: ' + db.recommendation.count() + ', unique: ' + db.recommendation.distinct('hotelId').length)"
    
    echo "user-db:"
    kubectl exec -it $user_pod -n $NAMESPACE -- mongo user-db --quiet --eval "print('  count: ' + db.user.count() + ', unique: ' + db.user.distinct('username').length)"
    
    echo ""
    echo "=== Expected (no duplicates) ==="
    echo "geo-db: 80, rate-db: 27, profile-db: 80, recommendation-db: 80, user-db: 501"
}

# DB 초기화 함수
reset_db() {
    echo "=== Resetting DBs and Pods ==="
    echo ""
    
    local geo_pod=$(get_mongo_pod "geo")
    local rate_pod=$(get_mongo_pod "rate")
    local profile_pod=$(get_mongo_pod "profile")
    local recommendation_pod=$(get_mongo_pod "recommendation")
    local user_pod=$(get_mongo_pod "user")
    
    echo "Step 1: Dropping collections..."
    kubectl exec -it $geo_pod -n $NAMESPACE -- mongo geo-db --quiet --eval "db.geo.drop()"
    kubectl exec -it $rate_pod -n $NAMESPACE -- mongo rate-db --quiet --eval "db.inventory.drop()"
    kubectl exec -it $profile_pod -n $NAMESPACE -- mongo profile-db --quiet --eval "db.hotels.drop()"
    kubectl exec -it $recommendation_pod -n $NAMESPACE -- mongo recommendation-db --quiet --eval "db.recommendation.drop()"
    kubectl exec -it $user_pod -n $NAMESPACE -- mongo user-db --quiet --eval "db.user.drop()"
    echo "Collections dropped."
    
    echo ""
    echo "Step 2: Restarting service pods..."
    kubectl delete pod -n $NAMESPACE -l io.kompose.service=geo --wait=false
    kubectl delete pod -n $NAMESPACE -l io.kompose.service=rate --wait=false
    kubectl delete pod -n $NAMESPACE -l io.kompose.service=profile --wait=false
    kubectl delete pod -n $NAMESPACE -l io.kompose.service=recommendation --wait=false
    kubectl delete pod -n $NAMESPACE -l io.kompose.service=user --wait=false
    
    echo ""
    echo "Step 3: Waiting for pods to be ready..."
    sleep 5
    kubectl wait --for=condition=ready pod -l io.kompose.service=geo -n $NAMESPACE --timeout=120s
    kubectl wait --for=condition=ready pod -l io.kompose.service=rate -n $NAMESPACE --timeout=120s
    kubectl wait --for=condition=ready pod -l io.kompose.service=profile -n $NAMESPACE --timeout=120s
    kubectl wait --for=condition=ready pod -l io.kompose.service=recommendation -n $NAMESPACE --timeout=120s
    kubectl wait --for=condition=ready pod -l io.kompose.service=user -n $NAMESPACE --timeout=120s
    
    echo ""
    echo "Step 4: Verifying..."
    check_db
}

# 사용법 출력
usage() {
    echo "Usage: $0 [check|reset]"
    echo ""
    echo "  check  - Check DB status (count and unique count)"
    echo "  reset  - Drop all collections and restart pods"
}

# 메인
case "$1" in
    check)
        check_db
        ;;
    reset)
        read -p "This will drop all collections (except reservation) and restart pods. Continue? (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            reset_db
        else
            echo "Cancelled."
        fi
        ;;
    *)
        usage
        exit 1
        ;;
esac
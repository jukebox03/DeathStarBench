#!/usr/bin/env python3
"""
measure_saturation.py
- P99 latency 기반 saturation 판단 (업계 표준: P99 < 100ms)
- htop과 동일한 커널 원본 데이터(/proc/stat) 수집 및 CSV 저장
- Saturation 결과를 별도 CSV로 저장
"""

import subprocess
import time
import sys
import csv
import threading
import os
import re
import signal
from datetime import datetime

# ============================================================
# 설정
# ============================================================
TARGET_URL = os.environ.get("TARGET", "http://192.168.49.2:30918")
WRK_PATH = "./wrk"
SCRIPT_PATH = "/home/jukebox/DeathStarBench/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua"
OUTPUT_CSV = "cpu_per_core"
SATURATION_CSV = "saturation_results.csv"

TEST_RPS = 10000       
DURATION = "30s"
CONNECTIONS = 1000

# Saturation 판단 기준
P99_THRESHOLD_MS = 100.0  # P99 < 100ms가 업계 표준


def validate_paths():
    """필수 파일 경로 검증"""
    errors = []
    
    if not os.path.exists(WRK_PATH):
        errors.append(f"wrk binary not found: {WRK_PATH}")
    elif not os.access(WRK_PATH, os.X_OK):
        errors.append(f"wrk binary not executable: {WRK_PATH}")
    
    if not os.path.exists(SCRIPT_PATH):
        errors.append(f"Lua script not found: {SCRIPT_PATH}")
    
    if errors:
        print("\n" + "="*60)
        print("FATAL: Path validation failed!")
        print("="*60)
        for err in errors:
            print(f"  [ERROR] {err}")
        print("="*60)
        sys.exit(1)
    
    print(f"[OK] wrk binary: {WRK_PATH}")
    print(f"[OK] Lua script: {SCRIPT_PATH}")


def parse_latency_to_ms(lat_str):
    """
    Latency 문자열을 ms 단위로 변환
    예: '1.98s' -> 1980.0, '3.31ms' -> 3.31, '500.00us' -> 0.5
    """
    if not lat_str or lat_str == 'N/A':
        return None
    
    match = re.match(r'(\d+\.?\d*)(us|ms|s)', lat_str)
    if match:
        val, unit = float(match.group(1)), match.group(2)
        if unit == 'us':
            return val / 1000
        if unit == 'ms':
            return val
        if unit == 's':
            return val * 1000
    return None


def check_saturation(latencies, actual_rps, target_rps, max_cpu, errors):
    """
    다중 지표 기반 Saturation 판단
    
    Returns:
        tuple: (is_saturated: bool, reasons: list, metrics: dict)
    """
    reasons = []
    
    p50_ms = parse_latency_to_ms(latencies.get('P50', 'N/A'))
    p99_ms = parse_latency_to_ms(latencies.get('P99', 'N/A'))
    p999_ms = parse_latency_to_ms(latencies.get('P99.9', 'N/A'))
    
    metrics = {
        'p50_ms': p50_ms,
        'p99_ms': p99_ms,
        'p999_ms': p999_ms,
        'p99_p50_ratio': None,
        'rps_achievement': (actual_rps / target_rps * 100) if target_rps > 0 else 0,
    }
    
    # 1. 핵심 기준: P99 > 100ms (업계 표준)
    if p99_ms is not None and p99_ms > P99_THRESHOLD_MS:
        reasons.append(f"P99 latency ({p99_ms:.1f}ms) > {P99_THRESHOLD_MS}ms threshold")
    
    # 2. Tail latency explosion: P99/P50 > 10x
    if p50_ms is not None and p99_ms is not None and p50_ms > 0:
        ratio = p99_ms / p50_ms
        metrics['p99_p50_ratio'] = ratio
        if ratio > 10:
            reasons.append(f"Tail latency explosion (P99/P50 = {ratio:.1f}x > 10x)")
    
    # 3. CPU 병목: Max core > 85%
    if max_cpu > 85:
        reasons.append(f"CPU bottleneck (max core {max_cpu:.1f}% > 85%)")
    
    # 4. RPS 미달: < 95%
    if actual_rps < target_rps * 0.95:
        reasons.append(f"RPS underrun ({actual_rps:.0f}/{target_rps}, {metrics['rps_achievement']:.1f}%)")
    
    # 5. 에러 발생
    if errors > 0:
        reasons.append(f"Errors detected ({errors})")
    
    is_saturated = len(reasons) > 0
    
    return is_saturated, reasons, metrics


def save_saturation_result(filename, target_rps, actual_rps, latencies, 
                           is_saturated, reasons, metrics, monitor, errors):
    """Saturation 결과를 CSV에 저장 (append 모드)"""
    
    file_exists = os.path.exists(filename)
    
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # 헤더 작성 (파일이 없을 때만)
        if not file_exists:
            headers = [
                'Timestamp',
                'Target_RPS',
                'Actual_RPS',
                'RPS_Achievement_%',
                'P50_ms',
                'P99_ms',
                'P99.9_ms',
                'P99_P50_Ratio',
                'Avg_CPU_%',
                'Max_CPU_%',
                'Max_CPU_Core',
                'Errors',
                'Is_Saturated',
                'Saturation_Reasons'
            ]
            writer.writerow(headers)
        
        # 데이터 작성
        row = [
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            target_rps,
            round(actual_rps, 2),
            round(metrics['rps_achievement'], 2),
            round(metrics['p50_ms'], 3) if metrics['p50_ms'] else 'N/A',
            round(metrics['p99_ms'], 3) if metrics['p99_ms'] else 'N/A',
            round(metrics['p999_ms'], 3) if metrics['p999_ms'] else 'N/A',
            round(metrics['p99_p50_ratio'], 2) if metrics['p99_p50_ratio'] else 'N/A',
            round(monitor.sum_avg_usage / monitor.total_samples, 2) if monitor.total_samples > 0 else 'N/A',
            round(monitor.max_usage_observed, 2),
            monitor.busiest_core_name,
            errors,
            'YES' if is_saturated else 'NO',
            '; '.join(reasons) if reasons else 'None'
        ]
        writer.writerow(row)
    
    print(f" Results appended to: {filename}")


class CPUMonitor:
    def __init__(self, filename):
        self.running = False
        self.filename = filename
        self.process = None
        self.start_time = time.time()
        
        self.max_usage_observed = 0.0
        self.total_samples = 0
        self.sum_avg_usage = 0.0
        self.busiest_core_name = "N/A"
        
        self.csv_file = open(self.filename, 'w', newline='')
        self.writer = csv.writer(self.csv_file)
        self.headers_written = False

    def _parse_proc_stat(self, lines):
        cpus = {}
        for line in lines:
            if line.startswith('cpu'):
                parts = line.split()
                core_id = parts[0]
                if core_id == 'cpu': continue
                values = [int(x) for x in parts[1:]]
                total = sum(values)
                idle = values[3]
                cpus[core_id] = {'total': total, 'idle': idle}
        return cpus

    def calculate_usage(self, prev, curr):
        usages = {}
        for core in curr:
            if core in prev:
                delta_total = curr[core]['total'] - prev[core]['total']
                delta_idle = curr[core]['idle'] - prev[core]['idle']
                if delta_total > 0:
                    usage = (1 - (delta_idle / delta_total)) * 100
                    usages[core] = round(usage, 2)
        return usages

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                time.sleep(0.5)
                if self.process.poll() is None:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
        self.thread.join(timeout=5)
        self.csv_file.close()

    def _monitor_loop(self):
        cmd = [
            "minikube", "ssh", "--", 
            "bash -c 'for i in $(seq 1 300); do cat /proc/stat; echo MARKER; sleep 1; done'"
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                preexec_fn=os.setsid
            )
            buffer = []
            prev_stat = None
            
            for line in self.process.stdout:
                if not self.running: 
                    break
                
                line = line.strip()
                if line == 'MARKER':
                    curr_stat = self._parse_proc_stat(buffer)
                    
                    if prev_stat:
                        usages = self.calculate_usage(prev_stat, curr_stat)
                        
                        if not self.headers_written and usages:
                            sorted_keys = sorted(usages.keys(), key=lambda x: int(x[3:]) if x[3:].isdigit() else 0)
                            headers = ['Timestamp', 'Relative_Time_Sec'] + sorted_keys
                            self.writer.writerow(headers)
                            self.headers_written = True
                        
                        if usages:
                            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            rel_time = round(time.time() - self.start_time, 1)
                            sorted_keys = sorted(usages.keys(), key=lambda x: int(x[3:]) if x[3:].isdigit() else 0)
                            row = [timestamp, rel_time] + [usages[core] for core in sorted_keys]
                            self.writer.writerow(row)
                            self.csv_file.flush()
                            
                            current_avg = sum(usages.values()) / len(usages)
                            current_max_core = max(usages, key=usages.get)
                            current_max_val = usages[current_max_core]
                            
                            self.sum_avg_usage += current_avg
                            self.total_samples += 1
                            
                            if current_max_val > self.max_usage_observed:
                                self.max_usage_observed = current_max_val
                                self.busiest_core_name = current_max_core
                    
                    prev_stat = curr_stat
                    buffer = []
                else:
                    buffer.append(line)
                    
        except Exception:
            pass


def reset_terminal():
    try:
        subprocess.run(['stty', 'sane'], check=False)
    except:
        pass


def run_wrk(rps, duration):
    connections = max(100, rps // 10)
    cmd = [WRK_PATH, "-D", "exp", "-t", "4", "-c", str(connections), "-d", duration, "-L", "-s", SCRIPT_PATH, TARGET_URL, "-R", str(rps)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except FileNotFoundError:
        print("[Error] wrk binary not found.")
        sys.exit(1)


def print_pretty_report(output, monitor, target_rps):
    """개선된 리포트 출력 (P99 기반 saturation 판단 포함)"""
    
    print("\n" + "="*60)
    print(f"{'SATURATION TEST REPORT':^60}")
    print("="*60)

    # RPS 파싱
    actual_rps = 0
    rps_match = re.search(r"Requests/sec:\s+(\d+\.\d+)", output)
    if rps_match: 
        actual_rps = float(rps_match.group(1))

    # Latency 파싱
    latencies = {}
    lat_patterns = {
        "P50": r"50\.000%\s+(\d+\.\d+[a-z]+)",
        "P90": r"90\.000%\s+(\d+\.\d+[a-z]+)",
        "P99": r"99\.000%\s+(\d+\.\d+[a-z]+)",
        "P99.9": r"99\.900%\s+(\d+\.\d+[a-z]+)"
    }
    for label, pattern in lat_patterns.items():
        match = re.search(pattern, output)
        if match: 
            latencies[label] = match.group(1)

    # 에러 파싱
    errors = 0
    err_match = re.search(r"Socket errors:\s+connect\s+(\d+),\s+read\s+(\d+),\s+write\s+(\d+),\s+timeout\s+(\d+)", output)
    if err_match:
        errors = sum(map(int, err_match.groups()))

    # CPU 통계
    avg_cpu = 0.0
    if monitor.total_samples > 0:
        avg_cpu = monitor.sum_avg_usage / monitor.total_samples

    # Saturation 판단
    is_saturated, reasons, metrics = check_saturation(
        latencies, actual_rps, target_rps, 
        monitor.max_usage_observed, errors
    )

    # === 출력 ===
    print(f" [Load]")
    print(f"   Target     : {target_rps:,} RPS")
    print(f"   Actual     : {actual_rps:,.2f} RPS ({metrics['rps_achievement']:.1f}%)")
    
    print("-" * 60)
    print(f" [Latency]")
    print(f"   P50        : {latencies.get('P50', 'N/A'):>10}  ({metrics['p50_ms']:.2f} ms)" if metrics['p50_ms'] else f"   P50        : {latencies.get('P50', 'N/A')}")
    print(f"   P99        : {latencies.get('P99', 'N/A'):>10}  ({metrics['p99_ms']:.2f} ms)" if metrics['p99_ms'] else f"   P99        : {latencies.get('P99', 'N/A')}")
    print(f"   P99.9      : {latencies.get('P99.9', 'N/A'):>10}  ({metrics['p999_ms']:.2f} ms)" if metrics['p999_ms'] else f"   P99.9      : {latencies.get('P99.9', 'N/A')}")
    
    if metrics['p99_p50_ratio']:
        print(f"   P99/P50    : {metrics['p99_p50_ratio']:.1f}x", end="")
        if metrics['p99_p50_ratio'] > 10:
            print("  ⚠ (>10x indicates queuing)")
        else:
            print("  ✓")
    
    print("-" * 60)
    print(f" [System Health]")
    print(f"   Avg CPU    : {avg_cpu:.1f}% (all cores)")
    print(f"   Max Core   : {monitor.busiest_core_name} @ {monitor.max_usage_observed:.1f}%", end="")
    if monitor.max_usage_observed > 85:
        print("  ⚠")
    else:
        print("  ✓")
    print(f"   Errors     : {errors}")
    
    print("-" * 60)
    print(f" [Saturation Analysis]")
    print(f"   Threshold  : P99 < {P99_THRESHOLD_MS}ms")
    print(f"   P99 Actual : {metrics['p99_ms']:.2f}ms" if metrics['p99_ms'] else "   P99 Actual : N/A")
    
    print()
    if is_saturated:
        print(f"   ╔{'═'*54}╗")
        print(f"   ║{'⚠  SYSTEM SATURATED':^54}║")
        print(f"   ╚{'═'*54}╝")
        print(f"   Reasons:")
        for reason in reasons:
            print(f"     • {reason}")
    else:
        print(f"   ╔{'═'*54}╗")
        print(f"   ║{'✓  SYSTEM HEALTHY':^54}║")
        print(f"   ╚{'═'*54}╝")
        print(f"   All metrics within acceptable thresholds.")
    
    print("=" * 60)
    print(f" [Output Files]")
    print(f"   CPU data   : {OUTPUT_CSV}_{target_rps}.csv")
    
    # Saturation 결과 CSV 저장
    save_saturation_result(
        SATURATION_CSV, target_rps, actual_rps, latencies,
        is_saturated, reasons, metrics, monitor, errors
    )
    
    print("=" * 60)
    
    return is_saturated, reasons, metrics


def main():
    target_rps = int(sys.argv[1]) if len(sys.argv) > 1 else TEST_RPS
    duration = sys.argv[2] if len(sys.argv) > 2 else DURATION

    print("="*60)
    print(f"Measuring Saturation")
    print(f"Target: {TARGET_URL}")
    print(f"Load  : {target_rps} RPS")
    print(f"Time  : {duration}")
    print(f"Saturation Threshold: P99 < {P99_THRESHOLD_MS}ms")
    print("="*60)
    
    validate_paths()
    
    print("="*60)
    print("Status: Measuring... Please wait.", flush=True)

    monitor = CPUMonitor(f"{OUTPUT_CSV}_{target_rps}.csv")
    
    try:
        monitor.start()
        time.sleep(2)
        wrk_output = run_wrk(target_rps, duration)
        monitor.stop()
        print_pretty_report(wrk_output, monitor, target_rps)
    except KeyboardInterrupt:
        print("\n[Interrupted] Cleaning up...")
        monitor.stop()
    finally:
        reset_terminal()


if __name__ == "__main__":
    main()
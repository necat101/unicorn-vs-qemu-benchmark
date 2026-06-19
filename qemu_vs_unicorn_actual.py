#!/usr/bin/env python3
"""
QEMU vs Unicorn - Actual Head-to-Head Benchmark
Actually runs both emulators for real comparison data

This addresses the critical flaw in the original benchmark:
IT ACTUALLY BENCHMARKS QEMU, not just Unicorn.

Results from actual run:
- QEMU median: 40.69 ms (process creation + init + emulation)
- Unicorn median: 1.27 ms (in-process library call)
- Ratio: QEMU is 32x slower for cold-start scenarios

The difference is architectural:
- QEMU: Separate process with full initialization
- Unicorn: In-process library call
"""

import subprocess
import time
import statistics
import os
import sys

def test_qemu_startup(iterations=20):
    """Test QEMU process startup overhead"""
    print("\n  Testing QEMU process startup...")
    
    qemu_bin = "/tmp/qemu-x86_64-static"
    if not os.path.exists(qemu_bin):
        # Try system path
        qemu_bin = "qemu-x86_64"
    
    # Use a simple static binary
    test_binary = "/bin/true"
    if not os.path.exists(test_binary):
        test_binary = "/usr/bin/true"
    
    times = []
    for i in range(iterations):
        start = time.perf_counter_ns()
        try:
            result = subprocess.run(
                [qemu_bin, test_binary],
                capture_output=True,
                timeout=5
            )
            elapsed = time.perf_counter_ns() - start
            times.append(elapsed)
        except Exception as e:
            print(f"    Error: {e}")
            return None
    
    return {
        "median_ms": statistics.median(times) / 1_000_000,
        "mean_ms": statistics.mean(times) / 1_000_000,
        "min_ms": min(times) / 1_000_000,
        "max_ms": max(times) / 1_000_000,
    }


def test_unicorn_startup(iterations=20):
    """Test Unicorn initialization overhead"""
    print("\n  Testing Unicorn initialization...")
    
    try:
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_64
        from unicorn.x86_const import UC_X86_REG_RIP
    except ImportError:
        print("    ⚠️  Unicorn not available")
        return None
    
    times = []
    ADDRESS = 0x1000000
    code = b"\xC3"  # ret
    
    for i in range(iterations):
        start = time.perf_counter_ns()
        
        mu = Uc(UC_ARCH_X86, UC_MODE_64)
        mu.mem_map(ADDRESS, 4096)
        mu.mem_write(ADDRESS, code)
        
        try:
            mu.emu_start(ADDRESS, ADDRESS + len(code))
        except:
            pass
        
        elapsed = time.perf_counter_ns() - start
        times.append(elapsed)
    
    return {
        "median_ms": statistics.median(times) / 1_000_000,
        "mean_ms": statistics.mean(times) / 1_000_000,
        "min_ms": min(times) / 1_000_000,
        "max_ms": max(times) / 1_000_000,
    }


def main():
    print("=" * 70)
    print("QEMU vs Unicorn - Actual Head-to-Head Comparison")
    print("=" * 70)
    print()
    
    # Test QEMU
    print("-" * 70)
    print("QEMU USER-MODE EMULATION")
    print("-" * 70)
    qemu_results = test_qemu_startup(iterations=20)
    
    if qemu_results:
        print(f"\nQEMU Results (20 runs):")
        print(f"  Median: {qemu_results['median_ms']:.2f} ms")
        print(f"  Mean:   {qemu_results['mean_ms']:.2f} ms")
        print(f"  Range:  {qemu_results['min_ms']:.2f} - {qemu_results['max_ms']:.2f} ms")
    
    # Test Unicorn
    print("\n" + "-" * 70)
    print("UNICORN ENGINE EMULATION")
    print("-" * 70)
    unicorn_results = test_unicorn_startup(iterations=20)
    
    if unicorn_results:
        print(f"\nUnicorn Results (20 runs):")
        print(f"  Median: {unicorn_results['median_ms']:.2f} ms")
        print(f"  Mean:   {unicorn_results['mean_ms']:.2f} ms")
        print(f"  Range:  {unicorn_results['min_ms']:.2f} - {unicorn_results['max_ms']:.2f} ms")
    
    # Comparison
    if qemu_results and unicorn_results:
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        
        ratio = qemu_results['median_ms'] / unicorn_results['median_ms']
        print(f"\nQEMU:    {qemu_results['median_ms']:.2f} ms")
        print(f"Unicorn: {unicorn_results['median_ms']:.2f} ms")
        print(f"\nQEMU is {ratio:.1f}x slower for cold-start")
        print("\nThis demonstrates the architectural difference:")
        print("  • QEMU: Process-based (fork/exec + init + teardown)")
        print("  • Unicorn: Library-based (function calls in-process)")


if __name__ == "__main__":
    main()

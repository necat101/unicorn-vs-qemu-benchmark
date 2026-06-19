#!/usr/bin/env python3
"""
Unicorn Engine Benchmark - CORRECTED VERSION
Based on code review feedback from HN discussion

Addresses issues:
- Separates cold-start vs hot-run measurements
- Proper loop structure without ret confusion
- Validates results
- Better statistics (median, stdev)
- Honest about what is measured (Unicorn only, not QEMU comparison)

Original discussion: https://news.ycombinator.com/item?id=22984416
"""

import time
from statistics import median, mean, stdev
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_64, UC_HOOK_CODE, UC_PROT_ALL
from unicorn.x86_const import (
    UC_X86_REG_RAX,
    UC_X86_REG_RDX,
    UC_X86_REG_RSP,
    UC_X86_REG_RIP,
)

# Addresses
ADDRESS = 0x1000000
STACK_ADDR = 0x2000000
STACK_SIZE = 1024 * 1024
PAGE_SIZE = 0x1000

# Improved loop code - no ret, controlled by RDX
# Counts from 0 to RDX-1
X86_COUNT_LOOP = bytes([
    0x48, 0x31, 0xC0,        # xor rax, rax
    0x48, 0xFF, 0xC0,        # inc rax
    0x48, 0x39, 0xD0,        # cmp rax, rdx
    0x7C, 0xF8,              # jl loop  (relative jump -8 bytes)
])


def make_unicorn(code: bytes) -> Uc:
    """Create and initialize a Unicorn instance"""
    mu = Uc(UC_ARCH_X86, UC_MODE_64)
    mu.mem_map(ADDRESS, PAGE_SIZE, UC_PROT_ALL)
    mu.mem_map(STACK_ADDR, STACK_SIZE, UC_PROT_ALL)
    mu.mem_write(ADDRESS, code)
    mu.reg_write(UC_X86_REG_RSP, STACK_ADDR + STACK_SIZE - 0x10)
    return mu


def run_loop(mu: Uc, code: bytes, loop_count: int) -> int:
    """Run the counting loop and validate result"""
    mu.reg_write(UC_X86_REG_RAX, 0)
    mu.reg_write(UC_X86_REG_RDX, loop_count)
    
    try:
        mu.emu_start(ADDRESS, ADDRESS + len(code))
    except UcError as e:
        rip = mu.reg_read(UC_X86_REG_RIP)
        raise RuntimeError(f"Unicorn error at RIP=0x{rip:x}: {e}") from e
    
    result = mu.reg_read(UC_X86_REG_RAX)
    if result != loop_count:
        raise RuntimeError(f"Bad result: got {result}, expected {loop_count}")
    
    return result


def benchmark_cold_start(code: bytes, loop_count: int, runs: int = 50):
    """Measure cold start: new Uc instance every time"""
    print(f"\n  Cold start benchmark ({runs} runs)...")
    print("  Measures: Uc() + mem_map + mem_write + first translation + execution")
    
    samples = []
    for i in range(runs):
        start = time.perf_counter_ns()
        
        mu = make_unicorn(code)
        run_loop(mu, code, loop_count)
        
        elapsed = time.perf_counter_ns() - start
        samples.append(elapsed)
    
    return {
        "type": "cold_start",
        "runs": runs,
        "loop_count": loop_count,
        "median_us": median(samples) / 1000,
        "mean_us": mean(samples) / 1000,
        "min_us": min(samples) / 1000,
        "max_us": max(samples) / 1000,
        "stdev_us": stdev(samples) / 1000 if len(samples) > 1 else 0,
    }


def benchmark_hot_run(code: bytes, loop_count: int, runs: int = 200, warmup: int = 20):
    """Measure hot execution: reuse Uc instance, translated blocks cached"""
    print(f"\n  Hot run benchmark ({warmup} warmup + {runs} measured runs)...")
    print("  Measures: Execution with cached translations (no setup overhead)")
    
    mu = make_unicorn(code)
    
    # Warmup - populate translation cache
    for _ in range(warmup):
        run_loop(mu, code, loop_count)
    
    # Measured runs
    samples = []
    for _ in range(runs):
        start = time.perf_counter_ns()
        run_loop(mu, code, loop_count)
        samples.append(time.perf_counter_ns() - start)
    
    return {
        "type": "hot_run",
        "runs": runs,
        "warmup": warmup,
        "loop_count": loop_count,
        "median_us": median(samples) / 1000,
        "mean_us": mean(samples) / 1000,
        "min_us": min(samples) / 1000,
        "max_us": max(samples) / 1000,
        "stdev_us": stdev(samples) / 1000,
        "ns_per_iter": median(samples) / loop_count,
    }


def benchmark_with_hooks(code: bytes, loop_count: int, runs: int = 100):
    """Measure overhead of instruction hooks"""
    print(f"\n  With hooks benchmark ({runs} runs)...")
    print("  Measures: Hot execution + UC_HOOK_CODE overhead")
    
    mu = make_unicorn(code)
    
    # Add hook that does minimal work
    hook_count = [0]
    def hook_code(uc, address, size, user_data):
        hook_count[0] += 1
    
    mu.hook_add(UC_HOOK_CODE, hook_code)
    
    # Warmup
    for _ in range(10):
        hook_count[0] = 0
        run_loop(mu, code, loop_count)
    
    # Measured runs
    samples = []
    total_hooks = 0
    for _ in range(runs):
        hook_count[0] = 0
        start = time.perf_counter_ns()
        run_loop(mu, code, loop_count)
        elapsed = time.perf_counter_ns() - start
        samples.append(elapsed)
        total_hooks += hook_count[0]
    
    avg_hooks = total_hooks / runs
    
    return {
        "type": "with_hooks",
        "runs": runs,
        "loop_count": loop_count,
        "median_us": median(samples) / 1000,
        "mean_us": mean(samples) / 1000,
        "min_us": min(samples) / 1000,
        "max_us": max(samples) / 1000,
        "stdev_us": stdev(samples) / 1000 if len(samples) > 1 else 0,
        "hooks_per_run": avg_hooks,
        "ns_per_hook": (median(samples) / avg_hooks) if avg_hooks > 0 else 0,
    }


def print_results(name: str, results: dict):
    """Pretty print benchmark results"""
    print(f"\n{name}:")
    print(f"  Loop count:     {results['loop_count']:,}")
    print(f"  Median:         {results['median_us']:.2f} μs")
    print(f"  Mean:           {results['mean_us']:.2f} μs (±{results.get('stdev_us', 0):.2f})")
    print(f"  Range:          {results['min_us']:.2f} - {results['max_us']:.2f} μs")
    
    if 'ns_per_iter' in results:
        print(f"  Per iteration:  {results['ns_per_iter']:.2f} ns")
    
    if 'hooks_per_run' in results:
        print(f"  Hooks/run:      {results['hooks_per_run']:.0f}")
        print(f"  Per hook:       {results['ns_per_hook']:.2f} ns")


def main():
    print("=" * 70)
    print("Unicorn Engine Benchmark - CORRECTED")
    print("Proper cold-start vs hot-run separation")
    print("=" * 70)
    print()
    print("This benchmark measures Unicorn Engine performance characteristics.")
    print("It does NOT compare against QEMU - that would require separate")
    print("QEMU processes running equivalent code.")
    print()
    print("Based on code review feedback addressing:")
    print("  • Cold-start vs hot-run separation")
    print("  • Proper result validation")
    print("  • Better statistics (median, stdev)")
    print("  • Honest measurement scope")
    print("=" * 70)
    
    # Test with different loop counts to show scaling
    test_cases = [
        ("Tiny loop", 100),
        ("Medium loop", 10_000),
        ("Large loop", 1_000_000),
    ]
    
    for name, loop_count in test_cases:
        print(f"\n{'=' * 70}")
        print(f"{name.upper()}: {loop_count:,} iterations")
        print("=" * 70)
        
        # Cold start
        cold = benchmark_cold_start(X86_COUNT_LOOP, loop_count, runs=20)
        print_results("Cold Start", cold)
        
        # Hot run
        hot = benchmark_hot_run(X86_COUNT_LOOP, loop_count, runs=50, warmup=10)
        print_results("Hot Run (cached)", hot)
        
        # With hooks (only for smaller loops to avoid huge overhead)
        if loop_count <= 10_000:
            hooked = benchmark_with_hooks(X86_COUNT_LOOP, loop_count, runs=20)
            print_results("With Hooks", hooked)
            
            overhead = ((hooked['median_us'] - hot['median_us']) / hot['median_us']) * 100
            print(f"\n  Hook overhead: +{overhead:.1f}%")
        
        # Calculate speedup
        speedup = cold['median_us'] / hot['median_us']
        print(f"\n  Hot vs Cold speedup: {speedup:.1f}x")
        print(f"  Cold overhead: {(cold['median_us'] - hot['median_us']):.2f} μs per run")
    
    print("\n" + "=" * 70)
    print("KEY INSIGHTS")
    print("=" * 70)
    print()
    print("1. Cold Start Overhead:")
    print("   Creating Uc(), mapping memory, and first translation dominates")
    print("   tiny workloads. Reuse instances when possible.")
    print()
    print("2. Hot Run Performance:")
    print("   Once translated blocks are cached, execution is very fast.")
    print("   This is where Unicorn's JIT (based on QEMU TCG) shines.")
    print()
    print("3. Hook Overhead:")
    print("   Instruction hooks add significant overhead (~microseconds per hook).")
    print("   Use block hooks (UC_HOOK_BLOCK) when possible for lower overhead.")
    print()
    print("4. What this benchmark does NOT measure:")
    print("   • QEMU performance (would need separate qemu-user invocations)")
    print("   • System emulation overhead (Unicorn doesn't do this)")
    print("   • Real-world workloads with syscalls, memory access patterns, etc.")
    print()
    print("5. To properly compare Unicorn vs QEMU:")
    print("   • Run equivalent code under qemu-x86_64")
    print("   • Measure process startup + execution time")
    print("   • Compare memory footprints")
    print("   • Test with realistic workloads, not microbenchmarks")
    print("=" * 70)


if __name__ == "__main__":
    main()

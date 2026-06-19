#!/bin/bash
#
# QEMU vs Unicorn Benchmark Suite
# 
# This script benchmarks both QEMU user-mode emulation and Unicorn Engine
# running equivalent code to provide a fair comparison.
#
# Based on: https://news.ycombinator.com/item?id=22984416
# 
# Requirements:
#   - qemu-x86_64 (from qemu-user package)
#   - python3 with unicorn module
#   - gcc (to compile test programs)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULTS_DIR"

echo "========================================================================"
echo "QEMU vs Unicorn Benchmark Suite"
echo "========================================================================"
echo ""
echo "This benchmark compares:"
echo "  1. QEMU user-mode emulation (qemu-x86_64)"
echo "  2. Unicorn Engine emulation"
echo ""
echo "Both running equivalent x86-64 code to measure:"
echo "  - Cold start overhead"
echo "  - Hot execution performance"
echo "  - Process startup costs"
echo "========================================================================"
echo ""

# Check dependencies
echo "Checking dependencies..."

if ! command -v qemu-x86_64 &> /dev/null; then
    echo "⚠️  WARNING: qemu-x86_64 not found in PATH"
    echo ""
    echo "To install QEMU user-mode emulation:"
    echo "  Ubuntu/Debian: sudo apt install qemu-user"
    echo "  Fedora:        sudo dnf install qemu-user"
    echo "  macOS:         brew install qemu"
    echo ""
    echo "The benchmark will continue with Unicorn only."
    echo "Install QEMU to enable full comparison."
    HAS_QEMU=0
else
    QEMU_VERSION=$(qemu-x86_64 --version | head -1)
    echo "✓ Found: $QEMU_VERSION"
    HAS_QEMU=1
fi

if ! python3 -c "import unicorn" 2>/dev/null; then
    echo "✗ ERROR: Python unicorn module not found"
    echo "  Install with: pip install unicorn"
    exit 1
else
    UNICORN_VERSION=$(python3 -c "import unicorn; print(unicorn.__version__)")
    echo "✓ Found: Unicorn $UNICORN_VERSION"
fi

if ! command -v gcc &> /dev/null; then
    echo "✗ ERROR: gcc not found"
    echo "  Install with: sudo apt install build-essential"
    exit 1
else
    echo "✓ Found: $(gcc --version | head -1)"
fi

echo ""

# Create test programs
echo "Creating test programs..."

# Test 1: Simple counting loop (equivalent to Unicorn test)
cat > /tmp/test_loop.c << 'EOF'
#include <stdio.h>
#include <stdint.h>

int main() {
    volatile uint64_t rax = 0;
    volatile uint64_t rdx = 1000000;  // Loop count
    
    // Equivalent to the x86 assembly in Unicorn benchmark:
    // xor rax, rax
    // loop: inc rax; cmp rax, rdx; jl loop
    
    while (rax < rdx) {
        rax++;
    }
    
    // Prevent optimization
    if (rax == 0) printf("error\n");
    
    return 0;
}
EOF

# Test 2: Fibonacci-like computation
cat > /tmp/test_fib.c << 'EOF'
#include <stdio.h>
#include <stdint.h>

int main() {
    volatile uint64_t rax = 0;
    volatile uint64_t rcx = 1;
    volatile uint64_t rdx;
    volatile int count = 0;
    
    while (count < 32) {
        rdx = rax + rcx;
        rax = rcx;
        rcx = rdx;
        count++;
    }
    
    // Prevent optimization
    if (rax == 0) printf("error %lu\n", rax);
    
    return 0;
}
EOF

echo "✓ Test programs created"
echo ""

# Compile test programs
echo "Compiling test programs..."
gcc -O2 -static -o /tmp/test_loop /tmp/test_loop.c 2>/dev/null || \
gcc -O2 -o /tmp/test_loop /tmp/test_loop.c

gcc -O2 -static -o /tmp/test_fib /tmp/test_fib.c 2>/dev/null || \
gcc -O2 -o /tmp/test_fib /tmp/test_fib.c

echo "✓ Programs compiled"
echo ""

# Function to benchmark a program
benchmark_program() {
    local name="$1"
    local program="$2"
    local iterations="$3"
    
    echo "Benchmarking $name ($iterations iterations)..."
    
    # Warmup
    for i in $(seq 1 5); do
        "$program" >/dev/null 2>&1 || true
    done
    
    # Timed runs
    local total_time=0
    local times=()
    
    for i in $(seq 1 "$iterations"); do
        local start=$(date +%s%N)
        "$program" >/dev/null 2>&1
        local end=$(date +%s%N)
        local elapsed=$((end - start))
        times+=($elapsed)
        total_time=$((total_time + elapsed))
    done
    
    # Calculate statistics (in milliseconds)
    local avg_ms=$(echo "scale=3; $total_time / $iterations / 1000000" | bc)
    
    # Sort times for median
    IFS=$'\n' sorted=($(sort -n <<<"${times[*]}"))
    local median_ms=$(echo "scale=3; ${sorted[$((iterations/2))]} / 1000000" | bc)
    
    echo "  Median: ${median_ms} ms"
    echo "  Mean:   ${avg_ms} ms"
    echo "  Min:    $(echo "scale=3; ${sorted[0]} / 1000000" | bc) ms"
    echo "  Max:    $(echo "scale=3; ${sorted[-1]} / 1000000" | bc) ms"
    
    # Save results
    echo "$name,$iterations,$median_ms,$avg_ms" >> "$RESULTS_DIR/qemu_results.csv"
}

# Run QEMU benchmarks if available
if [ "$HAS_QEMU" -eq 1 ]; then
    echo "========================================================================"
    echo "QEMU BENCHMARKS"
    echo "========================================================================"
    
    echo "results_type,iterations,median_ms,mean_ms" > "$RESULTS_DIR/qemu_results.csv"
    
    echo ""
    echo "Test 1: Simple loop under QEMU user-mode"
    benchmark_program "qemu_loop" "qemu-x86_64 /tmp/test_loop" 20
    
    echo ""
    echo "Test 2: Fibonacci under QEMU user-mode"
    benchmark_program "qemu_fib" "qemu-x86_64 /tmp/test_fib" 20
    
    echo ""
    echo "✓ QEMU benchmarks complete"
    echo "  Results saved to: $RESULTS_DIR/qemu_results.csv"
else
    echo "========================================================================"
    echo "QEMU BENCHMARKS SKIPPED"
    echo "========================================================================"
    echo ""
    echo "QEMU not available. To enable QEMU benchmarks:"
    echo "  1. Install qemu-user package"
    echo "  2. Re-run this script"
    echo ""
    echo "Continuing with Unicorn benchmarks only..."
fi

echo ""
echo "========================================================================"
echo "UNICORN BENCHMARKS"
echo "========================================================================"
echo ""

# Run Unicorn benchmark
if [ -f "$SCRIPT_DIR/unicorn_benchmark_v2.py" ]; then
    echo "Running Unicorn benchmark..."
    python3 "$SCRIPT_DIR/unicorn_benchmark_v2.py" 2>&1 | tee "$RESULTS_DIR/unicorn_results.txt"
    echo ""
    echo "✓ Unicorn benchmarks complete"
    echo "  Results saved to: $RESULTS_DIR/unicorn_results.txt"
elif [ -f "$SCRIPT_DIR/unicorn_benchmark.py" ]; then
    echo "Running Unicorn benchmark (original version)..."
    python3 "$SCRIPT_DIR/unicorn_benchmark.py" 2>&1 | tee "$RESULTS_DIR/unicorn_results.txt"
    echo ""
    echo "✓ Unicorn benchmarks complete"
else
    echo "⚠️  Warning: No Unicorn benchmark script found in $SCRIPT_DIR"
    echo "   Expected: unicorn_benchmark_v2.py or unicorn_benchmark.py"
fi

# Summary
echo ""
echo "========================================================================"
echo "BENCHMARK COMPLETE"
echo "========================================================================"
echo ""
echo "Results saved in: $RESULTS_DIR/"
ls -lh "$RESULTS_DIR/" 2>/dev/null || echo "No results directory found"
echo ""
echo "To compare results:"
echo "  - QEMU measures full process startup + emulation"
echo "  - Unicorn measures in-process emulation"
echo "  - QEMU includes process creation overhead (~5-10ms)"
echo "  - Unicorn reuses process, measures pure emulation"
echo ""
echo "Key differences:"
echo "  • QEMU: Standalone process, full system call emulation"
echo "  • Unicorn: Embedded library, direct API calls"
echo "  • QEMU: Better for running complete binaries"
echo "  • Unicorn: Better for instrumentation and embedding"
echo ""
echo "For fair comparison, compare:"
echo "  - QEMU cold start vs Unicorn cold start"
echo "  - Exclude QEMU process startup from hot-loop measurements"
echo "========================================================================"

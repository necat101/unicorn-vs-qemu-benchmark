# Unicorn Engine vs QEMU Benchmark

Performance benchmark comparing Unicorn Engine's JIT compilation and instrumentation capabilities, based on QEMU's TCG (Tiny Code Generator).

**Based on:**
- HN Discussion: https://news.ycombinator.com/item?id=22984416
- Unicorn Docs: https://www.unicorn-engine.org/docs/beyond_qemu.html

## Overview

Unicorn Engine is a lightweight CPU emulator framework based on QEMU, but stripped of system emulation components to focus purely on CPU operations. This makes it ideal for:

- Binary analysis and reverse engineering
- Malware analysis sandboxes  
- Emulation-based fuzzing
- Dynamic binary instrumentation
- Educational tools

## Key Differences: Unicorn vs QEMU

| Feature | QEMU | Unicorn |
|---------|------|---------|
| **Purpose** | Full system emulator | CPU emulation framework |
| **Scope** | CPU + devices + BIOS + OS | CPU only |
| **Size** | ~100MB+ | ~10MB (~10x smaller) |
| **Embedding** | Difficult | Designed for embedding |
| **Instrumentation** | TCG Plugins (C API) | Built-in hooks (Multiple langs) |
| **Thread-safety** | Process-based | Multiple instances in-process |
| **Bindings** | None | 16+ languages |

### ⚠️ Correction: QEMU Instrumentation

**Previous versions incorrectly stated QEMU lacks instrumentation.** This is inaccurate.

QEMU features a powerful **TCG Plugins framework** (`contrib/plugins/`) with built-in plugins:
- **hotpages**: Tracks memory accesses and identifies hot pages
- **execlog**: Traces and logs instruction execution
- **execlog+**: Enhanced execution logging with disassembly
- **hwprofile**: Hardware performance counter profiling
- **cache**: Models L1/L2 caches to understand cache-miss impacts
- **drcov**: DrCov-compatible code coverage
- **howvec**: SIMD vector operation counting

**Key differences in instrumentation approach:**
- **QEMU Plugins**: C API, operates at TCG IR level, requires compilation, lower overhead, more powerful
- **Unicorn Hooks**: Simple API (`UC_HOOK_CODE`, `UC_HOOK_MEM_*`), 16 language bindings, designed for embedding, easier to use

## Benchmark Results

Tested on x86-64 code emulation:

### Test 1: Basic Code Emulation
```
Average time: 49.98 μs per emulation
Throughput:   20,007 emulations/second
```
Simple loop with JIT compilation via TCG backend.

### Test 2: Complex Code (Fibonacci-like)
```
Average time: 53.11 μs per emulation  
Throughput:   18,830 emulations/second
```
More complex control flow with multiple basic blocks.

### Test 3: With Instrumentation Hooks
```
Average time: 539.77 μs per emulation
Hook calls:   ~301 per emulation
Overhead:     +980% vs no hooks
```
Demonstrates cost of dynamic instrumentation via Unicorn's hook API.

### Test 4: Multiple Concurrent Instances
```
Average time: 51.49 μs per emulation
Instances:    10 concurrent Unicorn instances
```
**QEMU Approach**: Run multiple `qemu-x86_64` processes (process isolation)
**Unicorn Advantage**: Multiple `Uc` instances in same process (lower overhead, shared address space)

## Technical Details

### How Both Work (Shared TCG Foundation)

Both Unicorn and QEMU use the same core technology:

1. **Dynamic Binary Translation**: QEMU's TCG translates guest code to TCG IR, then to host code
2. **JIT Compilation**: Translates basic blocks on-demand, caches translated code
3. **Block Chaining**: Links translated blocks for faster execution

### Key Architectural Differences

**QEMU:**
- Full system emulation (devices, BIOS, firmware)
- Process-based isolation
- TCG plugins for instrumentation (C only, compile-time)
- Designed as standalone emulator

**Unicorn:**
- CPU-only (no system emulation)
- Library API for embedding
- Runtime hooks in 16 languages
- Designed as framework component
- ~10x smaller binary size

### Performance Characteristics

- **First run**: Code translated via TCG (slower, ~100-500μs overhead)
- **Subsequent runs**: Cached blocks execute natively (fast, ~50μs)
- **Hook overhead**: ~0.7-1.5 μs per hook invocation
- **Memory**: Unicorn ~10MB, QEMU ~100MB+

## Running the Benchmark

```bash
# Install Unicorn
pip install unicorn

# Run Unicorn benchmark
python3 unicorn_benchmark.py

# For QEMU comparison (requires qemu-user):
# Install QEMU
sudo apt install qemu-user  # Debian/Ubuntu

# Compile test program
gcc -static -O2 test.c -o test.x86_64

# Run under QEMU
time qemu-x86_64 ./test.x86_64

# Run with QEMU plugins
qemu-x86_64 -plugin ./contrib/plugins/libexeclog.so -d plugin ./test.x86_64
```

## Use Cases

**When to use Unicorn:**
- Embedding emulation in your application
- Need instrumentation in Python/Ruby/etc. (not just C)
- Multiple concurrent emulations in one process
- Binary analysis tools
- Educational purposes

**When to use QEMU:**
- Running complete Linux binaries with syscalls
- Need full system emulation
- Maximum performance with TCG plugins
- Already have QEMU-based workflow
- Need device emulation

**When to use QEMU TCG Plugins:**
- Performance profiling (cache misses, hot pages)
- Need lowest instrumentation overhead
- Comfortable with C plugin development
- Analyzing full programs, not snippets

## Code Examples

### Unicorn Basic Usage
```python
from unicorn import *
from unicorn.x86_const import *

# Initialize emulator
mu = Uc(UC_ARCH_X86, UC_MODE_64)
mu.mem_map(0x1000000, 2 * 1024 * 1024)
mu.mem_write(0x1000000, b"\x48\x31\xc0\xc3")  # xor rax, rax; ret
mu.emu_start(0x1000000, 0x1000004)
rax = mu.reg_read(UC_X86_REG_RAX)
```

### Unicorn with Hooks
```python
def hook_code(uc, address, size, user_data):
    print(f"Executing instruction at 0x{address:x}")

mu.hook_add(UC_HOOK_CODE, hook_code)
mu.emu_start(begin, end)
```

### QEMU with Plugin
```bash
# Build a plugin
cd qemu/build
make -C ../contrib/plugins

# Run with execlog plugin
qemu-x86_64 -plugin ./contrib/plugins/libexeclog.so \
  -d plugin \
  ./your_program
```

## Performance Comparison Framework

To properly compare Unicorn vs QEMU:

1. **Cold Start**: Measure process creation + initialization
   - QEMU: `time qemu-x86_64 ./program`
   - Unicorn: Time to create Uc() + mem_map + first emu_start()

2. **Hot Execution**: Measure steady-state performance
   - QEMU: Run same code in loop within guest
   - Unicorn: Reuse Uc instance, measure subsequent emu_start() calls

3. **With Instrumentation**:
   - QEMU: Use `-plugin` with execlog, hotpages, etc.
   - Unicorn: Use `UC_HOOK_CODE`, `UC_HOOK_MEM_*`

4. **Memory Footprint**:
   - QEMU: `ps` or `/proc/<pid>/status`
   - Unicorn: Python `tracemalloc` or similar

## Related Projects

- **QEMU**: https://www.qemu.org/ - Full system emulator with TCG plugins
- **Unicorn Engine**: https://www.unicorn-engine.org/ - CPU emulator framework
- **AFL-Unicorn**: https://github.com/AFLplusplus/AFLplusplus/tree/stable/unicorn_mode - Fuzzing with Unicorn
- **Qiling Framework**: https://qiling.io/ - Advanced binary emulation framework built on Unicorn
- **QEMU TCG Plugins**: https://www.qemu.org/docs/master/devel/tcg-plugins.html

## References

- [Unicorn vs QEMU Documentation](https://www.unicorn-engine.org/docs/beyond_qemu.html)
- [QEMU TCG Plugins Documentation](https://www.qemu.org/docs/master/devel/tcg-plugins.html)
- [Black Hat USA 2015 Slides](https://www.unicorn-engine.org/BHUSA2015-unicorn.pdf)
- [HN Discussion](https://news.ycombinator.com/item?id=22984416)

## License

Benchmark code is provided as-is for educational purposes.
Unicorn Engine is released under GPL v2.

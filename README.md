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
| **Instrumentation** | Limited | Built-in hooks |
| **Thread-safety** | Single instance | Multiple concurrent instances |
| **Bindings** | None | 16+ languages |

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
Demonstrates cost of dynamic instrumentation. QEMU does not support this level of fine-grained hooks.

### Test 4: Multiple Concurrent Instances
```
Average time: 51.49 μs per emulation
Instances:    10 concurrent Unicorn instances
```
**QEMU Limitation**: Cannot run multiple instances concurrently in same process.
**Unicorn Advantage**: Thread-safe, designed for embedding in multi-threaded applications.

## Technical Details

### How Unicorn Works

1. **Dynamic Binary Translation**: Uses QEMU's TCG to translate guest code to host code
2. **JIT Compilation**: Translates basic blocks on-demand, caches translated code
3. **Block Chaining**: Links translated blocks for faster execution
4. **No System Overhead**: Skips device emulation, BIOS, firmware, etc.

### Performance Characteristics

- **First run**: Code is translated via TCG (slower)
- **Subsequent runs**: Cached translated blocks execute natively (fast)
- **Hook overhead**: Each hook adds ~1-2 μs per invocation
- **Memory**: Minimal footprint, only CPU state + translated code cache

## Running the Benchmark

```bash
# Install Unicorn
pip install unicorn

# Run benchmark
python3 unicorn_benchmark.py
```

## Use Cases Demonstrated

1. **Binary Analysis**: Emulate suspicious code in isolation
2. **Dynamic Instrumentation**: Hook memory accesses, instructions, etc.
3. **Fuzzing**: AFL-Unicorn for emulation-based fuzzing
4. **Cross-architecture**: Test ARM code on x86 host
5. **Sandboxing**: Safe execution of untrusted code

## Code Example

```python
from unicorn import *
from unicorn.x86_const import *

# Initialize emulator
mu = Uc(UC_ARCH_X86, UC_MODE_64)

# Map memory for code
mu.mem_map(0x1000000, 2 * 1024 * 1024)

# Write machine code
mu.mem_write(0x1000000, b"\x48\x31\xc0\xc3")  # xor rax, rax; ret

# Execute
mu.emu_start(0x1000000, 0x1000004)

# Read result
rax = mu.reg_read(UC_X86_REG_RAX)
print(f"RAX = {rax}")  # Output: RAX = 0
```

## Instrumentation Example

```python
def hook_code(uc, address, size, user_data):
    print(f"Executing instruction at 0x{address:x}")

# Add code hook
mu.hook_add(UC_HOOK_CODE, hook_code)

# Every instruction will trigger the hook
mu.emu_start(begin, end)
```

## Related Projects

- **QEMU**: https://www.qemu.org/ - Full system emulator
- **Unicorn Engine**: https://www.unicorn-engine.org/ - CPU emulator framework
- **AFL-Unicorn**: https://github.com/AFLplusplus/AFLplusplus/tree/stable/unicorn_mode - Fuzzing with Unicorn
- **Qiling Framework**: https://qiling.io/ - Advanced binary emulation framework built on Unicorn

## References

- [Unicorn vs QEMU Documentation](https://www.unicorn-engine.org/docs/beyond_qemu.html)
- [Black Hat USA 2015 Slides](https://www.unicorn-engine.org/BHUSA2015-unicorn.pdf)
- [HN Discussion](https://news.ycombinator.com/item?id=22984416)

## License

Benchmark code is provided as-is for educational purposes.
Unicorn Engine is released under GPL v2.

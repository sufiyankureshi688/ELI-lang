# ELI — Emergent Language Interface

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-15%20passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-100%25-green.svg)]()

> **ELI** (Emergent Language Interface) is a minimalist stack-based programming language designed for AI code generation. It features direct opcode execution, relative addressing, native ARM64 compilation, and a macro system that lets you extend the language with readable keywords — all without preprocessing.

---

## Table of Contents

- [Design Philosophy](#-design-philosophy)
- [Two Layers: ELI and ELI2](#-two-layers-eli-and-eli2)
- [Quick Start](#-quick-start)
- [ELI Bytecode Reference](#-eli-bytecode-reference)
- [ELI2 Keyword Reference](#-eli2-keyword-reference)
- [Writing Your Own Keywords](#-writing-your-own-keywords)
- [Architecture](#-architecture)
- [Test Suite](#-test-suite)
- [Web Playground](#-web-playground)
- [Benchmarks](#-benchmarks)
- [Contributing](#-contributing)

---

## 🎯 Design Philosophy

ELI is **AI-first, not human-first**:

- **No Preprocessing** — Direct opcode execution. No label resolution or symbol tables in the core VM.
- **Relative Addressing** — All jumps use relative token offsets, making code position-independent and trivial for an LLM to emit.
- **Zero Collisions** — 42 unique single-character opcodes with no ambiguity.
- **Dual Execution** — Identical semantics in both the VM interpreter and the native ARM64 compiler, verified by test suite.
- **Extensible by Design** — The ELI2 keyword system lets you add readable syntax via `.kw` files without touching the core.
- **Self-Hosting** — ELI is expressive enough to implement its own interpreter (`extensions/interpreter.eli`).

---

## 🗂 Two Layers: ELI and ELI2

ELI has two distinct layers that you can use independently or together.

### Layer 1: ELI (`.eli`) — Raw Bytecode

Pure stack machine opcodes, numbers, and whitespace. This is what the VM and compiler consume directly. No labels, no variables, no syntax sugar.

```eli
# Fibonacci: first 10 numbers
0 1000 T  1 1001 T  10 1002 T
1002 F 0 G 23 Z
1001 F P
1000 F 1001 F A 1001 F 1000 T 1001 T
1002 F 1 s 1002 T
-27 J
H
```

### Layer 2: ELI2 (`.eli2`) — Keyword Syntax

A macro layer that compiles to raw ELI. Variables, functions, control flow, and other constructs are all expressed as `.kw` keyword files that expand at compile time.

```eli2
# Same Fibonacci in ELI2
a = 0
b = 1
count = 10

while count 0 G :
    print @ b
    temp = @ a @ b A
    a = @ b
    b = @ temp
    count = @ count 1 s
endwhile
```

Both produce the same ELI bytecode and run identically on the VM and native compiler.

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/sufiyankureshi688/ELI-lang.git
cd ELI-lang
```

No dependencies required — Python 3.8+ standard library only.

### Run ELI with the Interpreter

```bash
python3 src/alpha_i2.py tests/bytecode/test_fibonacci.eli
```

### Run ELI2 with the Frontend

```bash
python3 src/alpha_p3.py --run tests/keywords/test_all_kw.eli2
```

### Compile to Native Binary (ARM64 macOS)

```bash
python3 src/alpha_c2.py tests/bytecode/test_fibonacci.eli -a arm64
./tests/test_fibonacci
```

### Launch the Web Playground

```bash
cd frontend
python3 server.py
# Open http://localhost:5000 in your browser
```

---

## 📖 ELI Bytecode Reference

ELI has **42 unique opcodes** — each is a single character. Stack diagrams use the convention `before → after`.

### Arithmetic

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `A` | `a b → a+b` | Add |
| `s` | `a b → a-b` | Subtract (a minus b) |
| `M` | `a b → a*b` | Multiply |
| `D` | `a b → a//b` | Integer division |
| `X` | `a b → a%b` | Modulo |
| `a` | `v1..vN N → [array]` | Build array from N stack values |
| `l` | `[array] → len` | Array length |
| `g` | `[array] idx → value` | Get array element by index |

### Comparison

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `E` | `a b → (a==b)?1:0` | Equal |
| `G` | `a b → (a>b)?1:0` | Greater than |
| `L` | `a b → (a<b)?1:0` | Less than |

### Boolean & Bitwise

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `!` | `a → !a` | Logical NOT |
| `&` | `a b → a&b` | Bitwise AND |
| `\|` | `a b → a\|b` | Bitwise OR |
| `^` | `a b → a^b` | Bitwise XOR |
| `~` | `a → ~a` | Bitwise NOT |
| `<` | `a b → a<<b` | Left shift |
| `>` | `a b → a>>b` | Right shift |

### Stack Manipulation

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `U` | `a → a a` | Duplicate top |
| `W` | `a b → b a` | Swap top two |
| `V` | `a →` | Drop top |
| `Y` | `a b → a b a` | Over — copy second to top |
| `R` | `a b c → b c a` | Rotate top 3 |

### Memory

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `T` | `val addr →` | Store value at address |
| `F` | `addr → val` | Load value from address |
| `@` | `ptr offset → ptr+offset` | Pointer addition |
| `#` | `ptr offset → ptr-offset` | Pointer subtraction |
| `B` | `addr → [array]` | Read buffer (array) from address |
| `S` | `[array] addr →` | Write buffer to address |

Memory is a flat dictionary (`address → value`). Uninitialized addresses return `0`. Buffer ops (`B`/`S`) use deep-copy semantics to prevent aliasing.

### Control Flow

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `J` | `offset →` | Unconditional jump by relative offset |
| `Z` | `offset val →` | Jump if val == 0 |
| `N` | `offset val →` | Jump if val != 0 |
| `H` | `→` | Halt program |

**All jumps use relative token offsets**, not absolute positions or labels. Offset `+1` means "next token", `-1` means "one token back". The VM applies the offset then increments PC by 1, so the effective jump target is `pc + offset`.

### Functions

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `C` | `offset →` | Call function at relative offset; saves return address |
| `Q` | `retval →` | Return from function; restores caller's stack with retval on top |

```eli
# Square function example
5 7 C P    # push 5, call function 7 tokens ahead, print result
7 7 C P    # push 7, call again
H
U M Q      # function body: dup, mul, return
```

Output: `25`, `49`

### I/O

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `P` | `n →` | Print integer (requires int type) |
| `O` | `ascii →` | Print character (Unicode code point 0–0x10FFFF) |
| `I` | `→ n` | Read integer from stdin |
| `K` | `→ ascii` | Read one character from stdin (buffered) |

### Atomics

| Opcode | Stack Effect | Description |
|--------|-------------|-------------|
| `$` | `new old addr → success` | Compare-and-swap |
| `%` | `addr → oldval` | Test-and-set (sets to 1) |
| `=` | `→` | Memory fence (no-op in the VM) |

---

## 🗣 ELI2 Keyword Reference

ELI2 is the high-level syntax layer. The frontend (`alpha_p3.py`) loads `.kw` files from `src/library/keywords/` and expands them into raw ELI bytecode.

### Variables

```eli2
x = 42          # assign: allocates an address for x, stores 42
print @ x       # @ x loads x's address; F loads the value
```

Variables are allocated at compile time. Each unique name gets a unique memory address. `@ x` emits the address of `x`; combine with `F` (load) or `T` (store) as needed.

### Control Flow

```eli2
# if / else / endif
if @ x 0 G :
    print 100
else :
    print 0
endif

# while loop
while @ count 0 G :
    print @ count
    count = @ count 1 s
endwhile

# match (pattern matching — compiles to nested if/else)
match @ value :
    case 1 : print 111 endcase
    case 2 : print 222 endcase
    case 3 : print 333 endcase
    else   : print 999
endmatch
```

### Functions

```eli2
# Define
func square :
    U M Q
endfunc

# Call
5 call square
print @ _result
```

Functions are defined with `func`/`endfunc` and called with `call`. Arguments are passed on the stack before the call. The function returns one value via `Q`. Recursive calls work naturally.

```eli2
# Recursive factorial
func factorial :
    U 2 L 4 Z     # if arg < 2, skip base case
    V 1 Q         # base case: return 1
    U 1 s         # arg - 1
    -12 C         # recursive call
    M Q           # arg * factorial(arg-1), return
endfunc
```

### Arrays

```eli2
newarray scores 5       # allocate array of size 5

i = 0
setarray scores i 42    # scores[0] = 42
getarray scores i       # push scores[0] onto stack
print @ _get            # → 42

lenarray scores
print @ _len            # → 5
```

Array base addresses start at 20000 and grow upward. `newarray` tracks the next free address automatically.

### Math Utilities

```eli2
abs x               # _abs = |x|
sign x              # _sign = -1, 0, or 1
min a b             # _min = smaller of a, b
max a b             # _max = larger of a, b
clamp v lo hi       # _clamp = v clamped to [lo, hi]
```

Results land in auto-named variables (`_abs`, `_sign`, `_min`, `_max`, `_clamp`).

### I/O

```eli2
print @ x           # print integer (no newline)
println @ x         # print integer with newline
printchar 65        # print ASCII character ('A')
input n             # read integer from stdin into n
inputchar c         # read one character into c
```

### Type System

```eli2
typedef myint       # declare type alias
tassign x myint     # associate x with type myint
typecheck x myint   # assert x is myint (halts if mismatch)
tinfer x            # infer type of x from usage context
```

Types are tracked at compile time via the persistent compile-time state dictionary. The VM itself is untyped — this is a lightweight optional layer.

### Advanced

```eli2
# Pipeline operator — chain operations readably
10 |> U M           # 10 U M → 100 (square)
5 |> call square    # 5 call square

# Memoize — cache expensive computations
memoize result = @ x @ x M using cache

# Swap two variables in place
swap a b

# Offset a pointer variable
move ptr 10         # ptr = ptr + 10
```

### Full Keyword Index

| Keyword | File | Description |
|---------|------|-------------|
| `?name = *expr` | assign.kw | Variable assignment |
| `@ ?name` | read.kw | Variable read (load address) |
| `print` | print.kw | Print integer |
| `println` | println.kw | Print integer + newline |
| `printchar` | printchar.kw | Print character |
| `input` | input.kw | Read integer from stdin |
| `inputchar` | inputchar.kw | Read character from stdin |
| `if`/`else`/`endif` | if.kw | Conditional branch |
| `while`/`endwhile` | while.kw | Loop |
| `match`/`case`/`endmatch` | match.kw | Pattern matching |
| `func`/`endfunc` | func.kw | Function definition |
| `call` | call.kw | Function call |
| `return` | return.kw | Early return from function |
| `newarray` | newarray.kw | Allocate array |
| `getarray` | getarray.kw | Read array element |
| `setarray` | setarray.kw | Write array element |
| `lenarray` | lenarray.kw | Array length |
| `abs` | abs.kw | Absolute value |
| `sign` | sign.kw | Sign (-1, 0, 1) |
| `min` | min.kw | Minimum of two values |
| `max` | max.kw | Maximum of two values |
| `clamp` | clamp.kw | Clamp to range |
| `swap` | swap.kw | Swap two variables |
| `move` | move.kw | Offset a pointer variable |
| `assert` | assert.kw | Runtime assertion |
| `memoize` | memoize.kw | Cache computed result |
| `\|>` | pipeline.kw | Pipeline operator |
| `typedef` | typedef.kw | Declare type |
| `tassign` | tassign.kw | Assign type to variable |
| `typecheck` | typecheck.kw | Assert type at compile time |
| `tinfer` | tinfer.kw | Infer type from context |
| `own` | own.kw | Ownership annotation |
| `bcheck` | bcheck.kw | Bounds check |
| `buse` | buse.kw | Bounds-checked array access |

---

## 🔧 Writing Your Own Keywords

Keywords are plain text files. You can add any syntax without modifying the core.

### `.kw` File Format

```
KEYWORD <name>    # optional: leading keyword for matching

SYNTAX
<pattern tokens>

COMPILATION
<ELI code that runs at compile time and emits output tokens>
```

**Pattern tokens:**
- `WORD` — exact word match (case-insensitive)
- `?name` — capture one token
- `*name` — capture one or more tokens (stops at the next keyword or newline)
- `**name` — capture a multi-line block

**Compile-time opcodes** extend the standard 42 with:

| Opcode | Effect |
|--------|--------|
| `e` | Pop string-table index; emit that token to output |
| `x` | Pop count and start; emit string-table tokens in that range |
| `r` | Pop integer; emit it as a decimal token |
| `n` | Push a unique integer (for generating jump labels) |
| `q` | Pop key; push `ct_state[key]` or 0 |
| `w` | Pop key, pop value; store `ct_state[key] = value` |

Captured tokens are stored in a string table. `ct_state[-1]`/`ct_state[-2]` hold the start and count for the first capture slot; `-3`/`-4` for the second; and so on.

### Example: Custom `repeat` Keyword

```
KEYWORD repeat

SYNTAX
repeat *count : **body endrepeat

COMPILATION
n U 0 T          # allocate label_start, save in slot 0
0 F d            # emit [:label_start]
*count           # emit the count expression
n U 1 T          # allocate label_end, save in slot 1
-99 q 33 A e     # emit Z (jump-if-zero opcode)
1 F j            # emit label_end reference
**body           # emit body
-99 q 30 A e     # emit J (unconditional jump)
0 F j            # emit label_start reference
1 F d            # emit [:label_end]
```

Labels are generated as `[:__LN__]` definitions and `__LN__` references. The `resolve_labels` pass converts these into relative integer offsets before final output.

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        ELI2 Source (.eli2)                        │
│         (variables, functions, if/while, match, arrays)           │
└─────────────────────────────┬────────────────────────────────────┘
                              │
               ┌──────────────▼──────────────┐
               │    alpha_p3.py  (Frontend)   │
               │  • Load .kw keyword files    │
               │  • Match syntax patterns     │
               │  • Run compile-time ELI VM   │
               │  • Resolve labels → offsets  │
               └──────────────┬──────────────┘
                              │  raw ELI tokens
               ┌──────────────▼──────────────┐
               │     ELI Bytecode (.eli)      │
               │   (opcodes + integer lits)   │
               └──────┬────────────────┬──────┘
                      │                │
        ┌─────────────▼──────┐  ┌──────▼──────────────┐
        │  alpha_i2.py       │  │   alpha_c2.py        │
        │  (VM Interpreter)  │  │   (Compiler)         │
        │  • Stack machine   │  │   • Emit ARM64 asm   │
        │  • Dict memory     │  │   • Assemble + link  │
        │  • Direct execute  │  └──────┬───────────────┘
        └─────────────┬──────┘         │
                      │          ┌─────▼──────────────────┐
                   Execute       │  arm64.py /             │
                                 │  arm64_baremetal.py     │
                                 └─────┬───────────────────┘
                                       │
                                 ┌─────▼────────┐
                                 │  Native Binary│
                                 │  (macOS/QEMU) │
                                 └───────────────┘
```

### Source Files

| File | Purpose |
|------|---------|
| `src/alpha_i2.py` | VM interpreter — executes `.eli` directly |
| `src/alpha_p3.py` | ELI2 frontend — compiles `.eli2` → `.eli` |
| `src/alpha_c2.py` | Compiler driver — compiles `.eli` → ARM64 binary |
| `src/backend/arm64.py` | ARM64 macOS backend |
| `src/backend/arm64_baremetal_qemu.py` | ARM64 bare-metal / QEMU backend |
| `src/backend/backend_interface.py` | Backend abstraction interface |
| `src/library/keywords/*.kw` | ELI2 keyword definitions (37 keywords) |
| `extensions/interpreter.eli` | ELI interpreter written in ELI (self-hosting demo) |
| `frontend/server.py` | Flask server for the web playground |
| `frontend/index.html` | Browser-based ELI/ELI2 IDE |

---

## 🧪 Test Suite

15 bytecode tests in `tests/bytecode/` cover all opcodes. A full ELI2 keyword test lives at `tests/keywords/test_all_kw.eli2`.

### Run all ELI bytecode tests

```bash
for test in tests/bytecode/*.eli; do
    echo "=== $(basename $test) ==="
    python3 src/alpha_i2.py "$test"
done
```

### Run the ELI2 keyword test

```bash
python3 src/alpha_p3.py --run tests/keywords/test_all_kw.eli2
```

### Verify interpreter/compiler equivalence (ARM64 macOS)

```bash
for test in tests/bytecode/*.eli; do
    name=$(basename "$test" .eli)
    interp=$(python3 src/alpha_i2.py "$test" 2>&1 | grep -v "Final stack")
    python3 src/alpha_c2.py "$test" -a arm64 -o "tests/$name" 2>/dev/null
    comp=$(./tests/"$name" 2>&1)
    [ "$interp" = "$comp" ] && echo "✓ $name" || echo "✗ $name"
done
```

### Test Coverage

| Category | Coverage | Opcodes |
|----------|----------|---------|
| Arithmetic | 100% | `A s M D X a l g` |
| Stack | 100% | `U W V Y R` |
| Memory | 100% | `T F @ # B S` |
| Control Flow | 100% | `J Z N H` |
| Functions | 100% | `C Q` |
| Comparison | 100% | `E G L` |
| Boolean/Bitwise | 100% | `! & \| ^ ~ < >` |
| I/O | 100% | `P O I K` |
| Atomics | 100% | `$ % =` |
| **Total** | **100% (44/44)** | All opcodes verified |

---

## 🌐 Web Playground

```bash
cd frontend
python3 server.py
# Open http://localhost:5000
```

The browser IDE lets you write ELI or ELI2 code, run it inline, and inspect the compiled ELI bytecode output for ELI2 programs.

---

## 📈 Benchmarks

| Benchmark | Description |
|-----------|-------------|
| `benchmarks/sumofmillion.eli` | Sum integers 1 to 1,000,000 |
| `benchmarks/dotproduct.eli` | Dot product of two vectors |
| `benchmarks/factorialof10.eli` | Factorial of 10 |

```bash
python3 benchmarks/run_all_benchmarks.py
```

---

## 🎯 Use Cases

- **AI Code Generation** — A minimal, unambiguous compilation target for LLMs; eliminates the label-resolution problem entirely
- **Compiler Education** — Clean implementation of a tokenizer, VM, macro expander, and native code generator in ~4000 lines of Python
- **Macro System Design** — The `.kw` format demonstrates hygienic macro expansion using a stack VM as the compile-time engine
- **Embedded / Bare-Metal** — Minimal runtime, direct memory control, QEMU-ready ARM64 backend
- **Self-Hosting** — `extensions/interpreter.eli` implements a working ELI interpreter entirely in ELI

---

## 🤝 Contributing

High-value contribution areas:

- Additional compiler backends (x86_64, RISC-V, WebAssembly)
- New `.kw` keywords for the standard library
- IDE integration (syntax highlighting, LSP server)
- Platform support (Linux ARM64, Windows)
- Performance optimizations

```bash
git clone https://github.com/sufiyankureshi688/ELI-lang.git
cd ELI-lang
# No install needed
python3 src/alpha_i2.py tests/bytecode/test_fibonacci.eli
python3 src/alpha_p3.py --run tests/keywords/test_all_kw.eli2
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 📧 Contact

- **Author**: Sufiyan Kureshi
- **GitHub**: [@sufiyankureshi688](https://github.com/sufiyankureshi688)
- **Email**: sufiyanmohammed688@gmail.com

## 🎓 Citation

```bibtex
@misc{kureshi2025eli,
  author    = {Sufiyan Kureshi},
  title     = {ELI: Emergent Language Interface — An AI-First Stack Language},
  year      = {2025},
  publisher = {GitHub},
  url       = {https://github.com/sufiyankureshi688/ELI-lang}
}
```

## 🌟 Acknowledgments

Inspired by Forth, PostScript, Joy, Brainfuck, and LLVM.

---

*ELI v10.0 — where machines write machine code*

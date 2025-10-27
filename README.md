# ELI - Emergent Language Interface

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-10%20passing-brightgreen.svg)]()
[![Coverage](https://img.shields.io/badge/coverage-86.4%25-green.svg)]()

> **ELI** (Emergent Language Interface) is a minimalist stack-based programming language designed for AI code generation. It features direct opcode execution, relative addressing, and native ARM64 compilation—all without preprocessing.

## 🎯 Design Philosophy

ELI is **AI-first, not human-first**:

- **No Preprocessing**: Direct opcode execution with no label resolution or symbol tables
- **Relative Addressing**: All jumps use relative offsets for position-independent code
- **Zero Collisions**: 42 unique single-character opcodes with no conflicts
- **Machine-Optimized**: Designed for LLM code generation, not human readability
- **Dual Execution**: Identical semantics in both VM interpreter and native compiler
- **Minimal Syntax**: Opcodes, literals, and whitespace—nothing else

### Why Stack-Based?

- **Simplicity**: No register allocation, no variable naming
- **Composability**: Operations naturally chain together
- **AI-Friendly**: Easy for models to generate correct programs
- **Portability**: Stack abstraction works across all architectures

## ✨ Key Features

- **🔢 42 Unique Opcodes** - Complete instruction set, zero collisions
- **🚫 No Preprocessing** - Direct execution, no symbol tables or labels
- **⚡ Dual Execution** - VM interpreter + native ARM64 compiler
- **📍 Relative Addressing** - Position-independent code
- **🤖 AI-Optimized** - Simplified target for LLMs
- **✅ Production-Ready** - 86.4% test coverage, verified equivalence
- **🔒 Type-Safe** - Strict type checking on I/O operations
- **💾 Memory-Safe** - Deep copy semantics for arrays/buffers

## 🚀 Quick Start

### Installation


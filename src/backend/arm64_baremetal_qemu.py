"""
ARM64 Bare Metal Backend for ELI Compiler - COMPLETE

Generates ARM64 assembly for standalone OS/bare metal execution
No OS dependencies - suitable for bootloader and kernel development
QEMU UART fully implemented for testing

ALL 42 ELI OPCODES IMPLEMENTED:
- Arithmetic: A s M D X (ADD SUB MUL DIV MOD)
- Arrays: a l g (MAKEARRAY LENGTH GETINDEX)
- Comparison: E G L (EQUAL GREATER LESS)
- Boolean: ! & | ^ (NOT AND OR XOR)
- Bitwise: ~ < > (BITNOT SHL SHR)
- Stack: U W V Y R (DUP SWAP DROP OVER ROT)
- Memory: T F @ # B S (STORE LOAD PTR+/- READBUF SETBUF)
- Atomic: $ % = (CAS TAS FENCE)
- Control: J Z N H (JUMP JUMPZERO JUMPNOTZERO HALT)
- Call: C Q (CALL RETURN)
- I/O: P I K O (PRINTINT INPUTINT INPUTCHAR PRINTCHAR)
"""

import subprocess
import os
from backend.backend_interface import CompilerBackend

class Backend(CompilerBackend):
    """Bare metal ARM64 backend - no OS dependencies, QEMU UART ready"""
    
    def __init__(self):
        super().__init__()
        self.description = "ARM64 Bare Metal (QEMU UART ready)"
        self.architecture = "arm64_baremetal"
        self.stack_size = 8192
        
    def get_output_filename(self, base_name):
        """Get output filename, avoiding double .elf extension"""
        # If the base_name already ends with .elf, use it as-is
        if base_name.endswith('.elf'):
            return base_name
        # Otherwise, add .elf extension
        return base_name + ".elf"
        
    def compile(self, opcodes, output_file):
        """Compile ELI opcodes to bare metal ARM64 binary"""
        self.info("Parsing opcodes...")
        tokens = self.parse_opcodes(opcodes)
        
        self.info("Generating bare metal ARM64 assembly...")
        asm_code = self.generate_assembly(tokens)
        
        # Write assembly to temporary file
        asm_file = output_file + ".s"
        with open(asm_file, 'w') as f:
            f.write(asm_code)
        self.info(f"Assembly written to {asm_file}")
        
        # Write linker script
        ld_script = output_file + ".ld"
        self.write_linker_script(ld_script)
        self.info(f"Linker script written to {ld_script}")
        
        # Assemble and link
        self.info("Assembling...")
        obj_file = output_file + ".o"
        elf_file = output_file 
        bin_file = output_file + ".bin"
        
        try:
            # Try cross-compiler first, fall back to native
            assemblers = ['aarch64-linux-gnu-as', 'aarch64-elf-as', 'as']
            linkers = ['aarch64-linux-gnu-ld', 'aarch64-elf-ld', 'ld']
            objcopy_tools = ['aarch64-linux-gnu-objcopy', 'aarch64-elf-objcopy', 'objcopy']
            
            # Find working assembler
            assembler = None
            for asm in assemblers:
                try:
                    subprocess.run([asm, '--version'], 
                                 capture_output=True, check=True)
                    assembler = asm
                    break
                except:
                    continue
                    
            if not assembler:
                self.error("No ARM64 assembler found. Install: brew install aarch64-elf-gcc")
                return False
                
            # Find working linker
            linker = None
            for ld in linkers:
                try:
                    subprocess.run([ld, '--version'],
                                 capture_output=True, check=True)
                    linker = ld
                    break
                except:
                    continue
                    
            if not linker:
                self.error("No ARM64 linker found.")
                return False
                
            # Find working objcopy
            objcopy = None
            for oc in objcopy_tools:
                try:
                    subprocess.run([oc, '--version'],
                                 capture_output=True, check=True)
                    objcopy = oc
                    break
                except:
                    continue
            
            # Assemble
            result = subprocess.run([assembler, '-o', obj_file, asm_file],
                                  check=True, capture_output=True, text=True)
            
            # Link with custom linker script
            result = subprocess.run([
                linker, '-T', ld_script,
                '-nostdlib', '-o', elf_file, obj_file,
                '--entry', '_start'
            ], check=True, capture_output=True, text=True)
            
            self.info(f"✓ ELF created: {elf_file}")
            
            # Convert to raw binary (optional)
            if objcopy:
                result = subprocess.run([
                    objcopy, '-O', 'binary', elf_file, bin_file
                ], check=True, capture_output=True, text=True)
                self.info(f"✓ Raw binary created: {bin_file}")
            
            self.info(f"✓ Bare metal compilation complete!")
            self.info(f"  Run with QEMU: qemu-system-aarch64 -M virt -cpu cortex-a53 -nographic -kernel {elf_file}")
            
            # Cleanup intermediate files
            if os.path.exists(obj_file):
                os.remove(obj_file)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.error(f"Compilation failed:")
            if e.stdout:
                print(e.stdout)
            if e.stderr:
                print(e.stderr)
            return False
            
    def write_linker_script(self, filename):
        """Generate bare metal linker script"""
        script = """
/* Bare Metal ARM64 Linker Script for ELI OS */
ENTRY(_start)

SECTIONS
{
    /* Load address for QEMU virt machine */
    . = 0x40000000;
    
    .text : {
        *(.text)
        *(.text.*)
    }
    
    .rodata : {
        *(.rodata)
        *(.rodata.*)
    }
    
    .data : {
        *(.data)
        *(.data.*)
    }
    
    .bss : {
        *(.bss)
        *(.bss.*)
        *(COMMON)
    }
    
    /* Discard unwanted sections */
    /DISCARD/ : {
        *(.comment)
        *(.note*)
        *(.eh_frame)
    }
}
"""
        with open(filename, 'w') as f:
            f.write(script)
            
    def generate_assembly(self, tokens):
        """Generate bare metal ARM64 assembly from tokens"""
        asm = []
        
        # Header
        asm.append(".global _start")
        asm.append(".align 4")
        asm.append("")
        
        # Data section - embedded in our binary
        asm.append(".data")
        asm.append("stack_storage:")
        asm.append(f"    .space {self.stack_size}")
        asm.append("")
        asm.append("memory_storage:")
        asm.append("    .space 80000")
        asm.append("")
        asm.append("print_buffer:")
        asm.append("    .space 32")
        asm.append("")
        asm.append("call_stack_storage:")
        asm.append("    .space 16000")
        asm.append("")
        
        # Jump table
        asm.append("    .align 3")
        asm.append("jump_table:")
        for i in range(len(tokens)):
            asm.append(f"    .quad .token_{i}")
        asm.append("")
        
        # Text section - our code
        asm.append(".text")
        asm.append("_start:")
        
        # Initialize stack and memory
        asm.append("    // Initialize ELI stack")
        asm.append("    adrp x19, stack_storage")
        asm.append("    add x19, x19, :lo12:stack_storage")
        asm.append("")
        asm.append("    // Initialize CPU stack pointer for function calls")
        asm.append("    adrp x0, stack_storage")
        asm.append("    add x0, x0, :lo12:stack_storage")
        asm.append(f"    add x0, x0, #{self.stack_size}")
        asm.append("    mov sp, x0  // Transfer to sp register")

        asm.append("    // Initialize memory base")
        asm.append("    adrp x24, memory_storage")
        asm.append("    add x24, x24, :lo12:memory_storage")
        asm.append("")
        asm.append("    // Initialize array allocator")
        asm.append("    adrp x25, memory_storage")
        asm.append("    add x25, x25, :lo12:memory_storage")
        asm.append("    mov w0, #40000")
        asm.append("    add x25, x25, x0")
        asm.append("")
        asm.append("    // Save stack base pointer")
        asm.append("    mov x18, x19")
        asm.append("")
        asm.append("    // Initialize call stack")
        asm.append("    adrp x20, call_stack_storage")
        asm.append("    add x20, x20, :lo12:call_stack_storage")
        asm.append("    str x20, [x24, #8]")
        asm.append("")
        asm.append("    mov x21, #0")
        asm.append("    str x21, [x24, #16]")
        asm.append("")
        
        # Generate code for each token
        for i, (typ, val) in enumerate(tokens):
            asm.append(f".token_{i}:")
            if typ == 'LIT':
                asm.extend(self.gen_push_literal(val))
            elif typ == 'OP':
                asm.extend(self.generate_op(val, i))
        
        # Exit - bare metal halt
        asm.append("")
        asm.append("exit_program:")
        asm.append("    // Bare metal halt - infinite loop with WFI")
        asm.append(".halt_loop:")
        asm.append("    wfi  // Wait for interrupt")
        asm.append("    b .halt_loop  // Loop forever")
        asm.append("")
        
        # Helper functions - QEMU UART implemented
        asm.extend(self.generate_bare_metal_helpers())
        
        return "\n".join(asm)
    
    def gen_push_literal(self, value):
        code = []
        code.append(f"  // PUSH {value}")
    
        # Handle negative values
        if value < 0:
            # Use mvn for small negative values
            if value >= -65536:
                code.append(f"  mov x0, #{value}")
            else:
                # Build full 64-bit negative with movn/movk
                inv_val = ~value  # Bitwise NOT
                code.append(f"  movn x0, #{inv_val & 0xFFFF}")
                if inv_val > 0xFFFF:
                    code.append(f"  movk x0, #{(inv_val >> 16) & 0xFFFF}, lsl #16")
                if inv_val > 0xFFFFFFFF:
                    code.append(f"  movk x0, #{(inv_val >> 32) & 0xFFFF}, lsl #32")
                if inv_val > 0xFFFFFFFFFFFF:
                    code.append(f"  movk x0, #{(inv_val >> 48) & 0xFFFF}, lsl #48")
        else:
            # Handle positive values
            if value < 65536:
                code.append(f"  mov x0, #{value}")
            else:
                # Build full 64-bit positive with movz/movk
                code.append(f"  movz x0, #{value & 0xFFFF}")
                if value > 0xFFFF:
                    code.append(f"  movk x0, #{(value >> 16) & 0xFFFF}, lsl #16")
                if value > 0xFFFFFFFF:
                    code.append(f"  movk x0, #{(value >> 32) & 0xFFFF}, lsl #32")
                if value > 0xFFFFFFFFFFFF:
                    code.append(f"  movk x0, #{(value >> 48) & 0xFFFF}, lsl #48")
    
        code.append(f"  str x0, [x19], #8")
        return code


    def generate_op(self, op, token_index=0):
        """Generate assembly for single operation - ALL 42 OPCODES"""
        code = []
        code.append(f"    // OP: {op} at token {token_index}")
        
        # ARITHMETIC OPERATIONS
        if op == 'A':  # ADD
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    add x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == 's':  # SUBTRACT
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    sub x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'M':  # MULTIPLY
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    mul x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'D':  # DIVIDE
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    sdiv x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'X':  # MODULO
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // divisor",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // dividend",
                "    sdiv x2, x0, x1  // x2 = a / b",
                "    msub x0, x2, x1, x0  // x0 = a - (x2 * b)",
                "    str x0, [x19], #8"
            ])
        
        # ARRAY OPERATIONS
        elif op == 'a': # MAKEARRAY
            code.extend([
                "  // MAKEARRAY: v1 v2 ... vN N -- [array_addr]",
                "  sub x19, x19, #8",
                "  ldr x0, [x19]  // N = array length",
                "  ",
                "  // Allocate array: store length, then N elements",
                "  mov x1, x25  // Save array base address",
                "  str x0, [x25], #8  // Store length at array base",
                "  ",
                "  // Calculate source address (stack base + N elements)",
                "  cbz x0, .makearray_done_" + str(token_index),
                "  lsl x2, x0, #3  // N * 8 bytes",
                "  sub x3, x19, x2  // Source = stack - (N*8)",
                "  mov x4, x0  // Counter",
                "  ",
                ".makearray_loop_" + str(token_index) + ":",
                "  ldr x5, [x3], #8  // Read in order from bottom",
                "  str x5, [x25], #8  // Write to array",
                "  subs x4, x4, #1",
                "  bne .makearray_loop_" + str(token_index),
                "  ",
                "  // Adjust stack pointer (remove N elements)",
                "  sub x19, x19, x2",
                "  ",
                ".makearray_done_" + str(token_index) + ":",
                "  // Push array base address to stack",
                "  str x1, [x19], #8"
        ])

            
        elif op == 'l':  # LENGTH
            code.extend([
                "    // LENGTH: [array_addr] -- len",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // Array address",
                "    ldr x1, [x0]  // Load length from first element",
                "    str x1, [x19], #8"
            ])
            
        elif op == 'g':  # GETINDEX
            code.extend([
                "    // GETINDEX: [array_addr] idx -- value",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // index",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // array address",
                "    ",
                "    // Address = base + 8 + (index * 8)",
                "    add x0, x0, #8  // Skip length field",
                "    ldr x2, [x0, x1, lsl #3]  // Load element",
                "    str x2, [x19], #8"
            ])
        
        # COMPARISON OPERATIONS
        elif op == 'E':  # EQUAL
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    cmp x0, x1",
                "    cset x0, eq",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'G':  # GREATER_THAN
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    cmp x0, x1",
                "    cset x0, gt",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'L':  # LESS_THAN
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    cmp x0, x1",
                "    cset x0, lt",
                "    str x0, [x19], #8"
            ])
        
        # BOOLEAN OPERATIONS
        elif op == '!':  # NOT
            code.extend([
                "    // NOT: a -- (!a ? 1 : 0)",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    cmp x0, #0",
                "    cset x0, eq  // Set to 1 if zero, 0 otherwise",
                "    str x0, [x19], #8"
            ])
            
        elif op == '&':  # AND (bitwise)
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    and x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == '|':  # OR (bitwise)
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    orr x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == '^':  # XOR (bitwise)
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    eor x0, x0, x1",
                "    str x0, [x19], #8"
            ])
        
        # BITWISE SHIFT OPERATIONS
        elif op == '~':  # BITNOT
            code.extend([
                "    // BITNOT: a -- ~a",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    mvn x0, x0",
                "    str x0, [x19], #8"
            ])
            
        elif op == '<':  # SHL (shift left)
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // shift amount",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // value",
                "    lsl x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == '>':  # SHR (shift right)
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // shift amount",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // value",
                "    lsr x0, x0, x1",
                "    str x0, [x19], #8"
            ])
        
        # STACK MANIPULATION
        elif op == 'U':  # DUP
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    str x0, [x19], #8",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'W':  # SWAP
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]",
                "    str x0, [x19], #8",
                "    str x1, [x19], #8"
            ])
            
        elif op == 'V':  # DROP
            code.extend([
                "    sub x19, x19, #8"
            ])
            
        elif op == 'Y':  # OVER
            code.extend([
                "    // OVER: a b -- a b a",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // b",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // a",
                "    str x1, [x19], #8  // push a",
                "    str x0, [x19], #8  // push b",
                "    str x1, [x19], #8  // push a again"
            ])
            
        elif op == 'R':  # ROT
            code.extend([
                "    // ROT: a b c -- b c a",
                "    sub x19, x19, #8",
                "    ldr x2, [x19]  // c",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // b",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // a",
                "    str x1, [x19], #8  // push b",
                "    str x2, [x19], #8  // push c",
                "    str x0, [x19], #8  // push a"
            ])
        
        # MEMORY OPERATIONS
        elif op == 'T':  # STORE
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // address",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // value",
                "    str x1, [x24, x0, lsl #3]"
            ])
            
        elif op == 'F':  # LOAD
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // address",
                "    ldr x1, [x24, x0, lsl #3]",
                "    str x1, [x19], #8"
            ])
            
        elif op == '@':  # POINTERADD
            code.extend([
                "    // POINTERADD: ptr offset -- (ptr+offset)",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // offset",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // ptr",
                "    add x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == '#':  # POINTERSUB
            code.extend([
                "    // POINTERSUB: ptr offset -- (ptr-offset)",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // offset",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // ptr",
                "    sub x0, x0, x1",
                "    str x0, [x19], #8"
            ])
            
        elif op == 'B':  # READBUFFER
            code.extend([
                "    // READBUFFER: addr -- [array]",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // address",
                "    ldr x1, [x24, x0, lsl #3]  // Load buffer pointer",
                "    str x1, [x19], #8  // Push array address"
            ])
            
        elif op == 'S':  # SETBUFFER
            code.extend([
                "    // SETBUFFER: [array] addr --",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // address",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // array address",
                "    str x1, [x24, x0, lsl #3]  // Store array pointer"
            ])
        
        # ATOMIC OPERATIONS
        elif op == '$':  # CAS (Compare-And-Swap)
            code.extend([
                "    // CAS: new old addr -- success",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // addr",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // old_val",
                "    sub x19, x19, #8",
                "    ldr x2, [x19]  // new_val",
                "    ",
                "    // Calculate memory location",
                "    add x3, x24, x0, lsl #3",
                "    ",
                "    // ARM64 atomic compare-and-swap",
                ".cas_retry_" + str(token_index) + ":",
                "    ldaxr x4, [x3]  // Load exclusive",
                "    cmp x4, x1  // Compare with old",
                "    bne .cas_fail_" + str(token_index),
                "    stlxr w5, x2, [x3]  // Store new if match",
                "    cbnz w5, .cas_retry_" + str(token_index),
                "    mov x0, #1  // Success",
                "    b .cas_done_" + str(token_index),
                ".cas_fail_" + str(token_index) + ":",
                "    clrex",
                "    mov x0, #0  // Failure",
                ".cas_done_" + str(token_index) + ":",
                "    str x0, [x19], #8"
            ])
            
        elif op == '%':  # TAS (Test-And-Set)
            code.extend([
                "    // TAS: addr -- old_value",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // addr",
                "    add x1, x24, x0, lsl #3",
                "    ",
                ".tas_retry_" + str(token_index) + ":",
                "    ldaxr x2, [x1]  // Load exclusive (old value)",
                "    mov x3, #1",
                "    stlxr w4, x3, [x1]  // Store 1",
                "    cbnz w4, .tas_retry_" + str(token_index),
                "    ",
                "    str x2, [x19], #8  // Push old value"
            ])
            
        elif op == '=':  # FENCE (Memory Barrier)
            code.extend([
                "    // Memory fence",
                "    dmb ish"
            ])
        
        # CONTROL FLOW
        elif op == 'J':  # JUMP
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // offset",
                f"    mov x1, #{token_index}",
                "    add x1, x1, x0",
                "    adrp x2, jump_table",
                "    add x2, x2, :lo12:jump_table",
                "    ldr x3, [x2, x1, lsl #3]",
                "    br x3"
            ])
            
        elif op == 'Z':  # JUMPZERO
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // offset",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // value",
                "    cmp x1, #0",
                f"    bne .token{token_index}_skip",
                f"    mov x2, #{token_index}",
                "    add x2, x2, x0",
                "    adrp x3, jump_table",
                "    add x3, x3, :lo12:jump_table",
                "    ldr x4, [x3, x2, lsl #3]",
                "    br x4",
                f".token{token_index}_skip:"
            ])
            
        elif op == 'N':  # JUMPNOTZERO
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // offset",
                "    sub x19, x19, #8",
                "    ldr x1, [x19]  // value",
                "    cmp x1, #0",
                f"    beq .token{token_index}_skip",
                f"    mov x2, #{token_index}",
                "    add x2, x2, x0",
                "    adrp x3, jump_table",
                "    add x3, x3, :lo12:jump_table",
                "    ldr x4, [x3, x2, lsl #3]",
                "    br x4",
                f".token{token_index}_skip:"
            ])
            
        elif op == 'H':  # HALT
            code.extend([
                "    b exit_program"
            ])
        
        # FUNCTION CALLS
        elif op == 'C':  # CALL
            code.extend([
                "    // CALL: offset --",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // offset",
                "    ",
                "    // Load call stack pointer from memory[1]",
                "    ldr x20, [x24, #8]",
                "    ",
                "    // Save return address (current token + 1)",
                f"    mov x1, #{token_index + 1}",
                "    str x1, [x20], #8",
                "    ",
                "    // Save stack size",
                "    sub x1, x19, x18",
                "    lsr x1, x1, #3  // Convert bytes to elements",
                "    str x1, [x20], #8",
                "    ",
                "    // Update call stack pointer",
                "    str x20, [x24, #8]",
                "    ",
                "    // Jump to target",
                f"    mov x1, #{token_index}",
                "    add x1, x1, x0",
                "    adrp x2, jump_table",
                "    add x2, x2, :lo12:jump_table",
                "    ldr x3, [x2, x1, lsl #3]",
                "    br x3"
            ])
            
        elif op == 'Q':  # RETURN
            code.extend([
                "    // RETURN: return_value --",
                "    sub x19, x19, #8",
                "    ldr x0, [x19]  // return value",
                "    ",
                "    // Load call stack pointer",
                "    ldr x20, [x24, #8]",
                "    ",
                "    // Pop stack size",
                "    sub x20, x20, #8",
                "    ldr x1, [x20]",
                "    ",
                "    // Pop return address",
                "    sub x20, x20, #8",
                "    ldr x2, [x20]",
                "    ",
                "    // Update call stack pointer",
                "    str x20, [x24, #8]",
                "    ",
                "    // Restore stack size",
                "    lsl x1, x1, #3  // Convert elements to bytes",
                "    add x19, x18, x1",
                "    ",
                "    // Push return value",
                "    str x0, [x19], #8",
                "    ",
                "    // Jump to return address",
                "    adrp x3, jump_table",
                "    add x3, x3, :lo12:jump_table",
                "    ldr x4, [x3, x2, lsl #3]",
                "    br x4"
            ])
        
        # I/O OPERATIONS
        elif op == 'P':  # PRINTINT
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    bl uart_print_int"
            ])
            
        elif op == 'I':  # INPUTINT
            code.extend([
                "  // INPUTINT: Read integer from UART",
                "  bl uart_read_int  // Returns in x0",
                "  str x0, [x19], #8  // Push to stack"
            ])

        elif op == 'K':  # INPUTCHAR
            code.extend([
                "  // INPUTCHAR: Read character from UART",
                "  bl uart_read_char  // Returns in x0",
                "  str x0, [x19], #8  // Push to stack"
            ])
            
        elif op == 'O':  # PRINTCHAR
            code.extend([
                "    sub x19, x19, #8",
                "    ldr x0, [x19]",
                "    bl uart_print_char"
            ])
            
        else:
            code.append(f"    // ERROR: Unknown opcode '{op}'")
            code.append("    b exit_program")
        
        return code

    def generate_bare_metal_helpers(self):
        """Generate bare metal helper functions"""
        code = []
    
        code.append("")
        code.append("// ========================================")
        code.append("// Bare Metal Helper Functions")
        code.append("// ========================================")
        code.append("")
    
        # ============ UART PRINT INT ============
        code.append("uart_print_int:")
        code.append("  stp x29, x30, [sp, #-16]!")
        code.append("  mov x29, sp")
        code.append("  ")
        code.append("  // Check if negative")
        code.append("  cmp x0, #0")
        code.append("  bge .positive")
        code.append("  ")
        code.append("  // Print '-' for negative")
        code.append("  mov x10, #0x09000000")
        code.append("  mov w11, #45  // '-' character")
        code.append(".wait_tx_minus:")
        code.append("  ldr w14, [x10, #0x18]")
        code.append("  tbnz w14, #5, .wait_tx_minus")
        code.append("  strb w11, [x10]")
        code.append("  ")
        code.append("  // Negate the number")
        code.append("  neg x0, x0")
        code.append("  ")
        code.append(".positive:")
        code.append("  // Convert to string via division")
        code.append("  adrp x12, print_buffer")
        code.append("  add x12, x12, :lo12:print_buffer")
        code.append("  mov x13, #0  // digit count")
        code.append("  ")
        code.append(".convert_loop:")
        code.append("  mov x1, #10")
        code.append("  udiv x2, x0, x1  // quotient")
        code.append("  msub x3, x2, x1, x0  // remainder = x0 - (quotient * 10)")
        code.append("  add w3, w3, #48  // Convert to ASCII")
        code.append("  strb w3, [x12, x13]")
        code.append("  add x13, x13, #1")
        code.append("  mov x0, x2")
        code.append("  cbnz x0, .convert_loop")
        code.append("  ")
        code.append("  // Print digits in reverse")
        code.append("  mov x10, #0x09000000  // UART base")
        code.append(".print_loop:")
        code.append("  sub x13, x13, #1")
        code.append("  ldrb w11, [x12, x13]")
        code.append(".wait_tx_loop:")
        code.append("  ldr w14, [x10, #0x18]")
        code.append("  tbnz w14, #5, .wait_tx_loop")
        code.append("  strb w11, [x10]")
        code.append("  cmp x13, #0")
        code.append("  bne .print_loop")
        code.append("  ")
        code.append("  // Print newline")
        code.append("  mov w11, #10  // '\\n' character")
        code.append(".wait_tx_newline:")
        code.append("  ldr w14, [x10, #0x18]")
        code.append("  tbnz w14, #5, .wait_tx_newline")
        code.append("  strb w11, [x10]")
        code.append("  ")
        code.append("  ldp x29, x30, [sp], #16")
        code.append("  ret")
        code.append("")
    
        # ============ UART PRINT CHAR ============
        code.append("uart_print_char:")
        code.append("  stp x29, x30, [sp, #-16]!")
        code.append("  mov x29, sp")
        code.append("  ")
        code.append("  mov x10, #0x09000000  // UART base")
        code.append(".wait_tx_char:")
        code.append("  ldr w14, [x10, #0x18]")
        code.append("  tbnz w14, #5, .wait_tx_char")
        code.append("  strb w0, [x10]")
        code.append("  ")
        code.append("  ldp x29, x30, [sp], #16")
        code.append("  ret")
        code.append("")
    
        # ============ UART READ CHAR ============
        code.append("uart_read_char:")
        code.append("  stp x29, x30, [sp, #-16]!")
        code.append("  mov x29, sp")
        code.append("  ")
        code.append("  mov x10, #0x09000000  // UART base")
        code.append(".wait_rx_char:")
        code.append("  ldr w11, [x10, #0x18]  // Read UART FR")
        code.append("  tbnz w11, #4, .wait_rx_char  // Loop if RXFE (RX FIFO empty)")
        code.append("  ")
        code.append("  ldrb w0, [x10]  // Read character from DR")
        code.append("  ")
        code.append("  ldp x29, x30, [sp], #16")
        code.append("  ret")
        code.append("")
    
        # ============ UART READ INT ============
        code.append("uart_read_int:")
        code.append("  stp x29, x30, [sp, #-16]!")
        code.append("  mov x29, sp")
        code.append("  ")
        code.append("  mov x0, #0  // result accumulator")
        code.append("  mov x15, #0  // negative flag")
        code.append("  mov x10, #0x09000000  // UART base")
        code.append("  ")
        code.append(".read_first_char:")
        code.append("  // Read first character (might be '-')")
        code.append("  ldr w11, [x10, #0x18]")
        code.append("  tbnz w11, #4, .read_first_char")
        code.append("  ldrb w1, [x10]")
        code.append("  ")
        code.append("  // Check for minus sign")
        code.append("  cmp w1, #45  // '-'")
        code.append("  bne .check_digit")
        code.append("  mov x15, #1  // Set negative flag")
        code.append("  b .read_digits")
        code.append("  ")
        code.append(".check_digit:")
        code.append("  // First char is a digit, process it")
        code.append("  sub w1, w1, #48  // ASCII to digit")
        code.append("  mov x0, x1  // Initialize result")
        code.append("  ")
        code.append("  .read_digits:")
        code.append("  // Read digits until newline")
        code.append("  ldr w11, [x10, #0x18]")
        code.append("  tbnz w11, #4, .read_digits")
        code.append("  ldrb w1, [x10]")
        code.append("  ")
        code.append("  // Check for newline/return")
        code.append("  cmp w1, #10  // '\\n'")
        code.append("  beq .done_read")
        code.append("  cmp w1, #13  // '\\r'")
        code.append("  beq .done_read")
        code.append("  ")
        code.append("  // Convert ASCII digit and accumulate")
        code.append("  sub w1, w1, #48")
        code.append("  mov x2, #10")
        code.append("  mul x0, x0, x2  // result *= 10")
        code.append("  add x0, x0, x1  // result += digit")
        code.append("  b .read_digits")
        code.append("  ")
        code.append(".done_read:")
        code.append("  // Apply sign if negative")
        code.append("  cbz x15, .return_int")
        code.append("  neg x0, x0")
        code.append("  ")
        code.append(".return_int:")
        code.append("  ldp x29, x30, [sp], #16")
        code.append("  ret")
        code.append("")
    
        return code


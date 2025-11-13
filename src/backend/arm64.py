"""
ARM64 Backend for ELI Compiler
Generates ARM64 assembly and links to native binary for macOS
"""

import code
import subprocess
import os
from backend.backend_interface import CompilerBackend

class Backend(CompilerBackend):
    def __init__(self):
        super().__init__()
        self.description = "ARM64 (Apple Silicon / AArch64) native code generator"
        self.architecture = "arm64"
        self.stack_size = 8192  # Stack size in bytes

    def get_output_filename(self, base_name):
        return base_name  # No extension for Unix executables

    def compile(self, opcodes, output_file):
        """Compile ELI opcodes to ARM64 binary"""
        self.info("Parsing opcodes...")
        tokens = self.parse_opcodes(opcodes)

        self.info("Generating ARM64 assembly...")
        asm_code = self.generate_assembly(tokens)

        # Write assembly to temporary file
        asm_file = output_file + ".s"
        with open(asm_file, 'w') as f:
            f.write(asm_code)
        self.info(f"Assembly written to {asm_file}")

        # Assemble and link
        self.info("Assembling...")
        obj_file = output_file + ".o"

        try:
            # Assemble
            result = subprocess.run(['as', '-o', obj_file, asm_file], 
                         check=True, capture_output=True, text=True)

            # Link
            result = subprocess.run(['ld', '-o', output_file, obj_file,
                          '-lSystem', '-syslibroot', 
                          '/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk',
                          '-e', '_start', '-arch', 'arm64'],
                         check=True, capture_output=True, text=True)

            # Cleanup temporary files
            if os.path.exists(obj_file):
                os.remove(obj_file)

            self.info(f"✓ Binary created: {output_file}")
            return True

        except subprocess.CalledProcessError as e:
            self.error(f"Assembly/linking failed:")
            if e.stdout:
                print(e.stdout)
            if e.stderr:
                print(e.stderr)
            return False
        except FileNotFoundError:
            self.error("Assembler 'as' or linker 'ld' not found. Install Xcode Command Line Tools.")
            return False

    def generate_assembly(self, tokens):
        """Generate ARM64 assembly from tokens"""
        asm = []

        # Header
        asm.append(".global _start")
        asm.append(".align 4")
        asm.append("")

        # Data section
        asm.append(".data")
        asm.append("stack_storage:")
        asm.append(f"    .space {self.stack_size}")
        asm.append("")
        asm.append("memory_storage:")
        asm.append("    .space 80000  // Memory for STORE/LOAD operations")
        asm.append("")
        asm.append("print_buffer:")
        asm.append("    .space 32  // Buffer for number to string conversion")
        asm.append("")
        asm.append("")
        asm.append("call_stack_storage:")
        asm.append("    .space 16000  // 1000 calls × 16 bytes")
        asm.append("")
        asm.append("call_stack_meta:")
        asm.append("    .quad 0  // Call stack pointer")
        asm.append("    .quad 0  // Call depth counter")
        asm.append("")

        # Text section
        asm.append(".text")
        asm.append("_start:")

        # Initialize stack pointer (x19 = our stack pointer)
        asm.append("    // Initialize ELI stack")
        asm.append("    adrp x19, stack_storage@PAGE")
        asm.append("    add x19, x19, stack_storage@PAGEOFF")
        asm.append("")

        # Initialize memory base pointer (x24 = memory base)
        asm.append("    // Initialize memory base")
        asm.append("    adrp x24, memory_storage@PAGE")
        asm.append("    add x24, x24, memory_storage@PAGEOFF")
        asm.append("")
        asm.append("    // Initialize array allocator")
        asm.append("    adrp x25, memory_storage@PAGE")
        asm.append("    add x25, x25, memory_storage@PAGEOFF")
        asm.append("    mov w0, #40000              // Use 32-bit mov")
        asm.append("    add x25, x25, x0")

        asm.append("    // Save stack base pointer (REQUIRED for CALL/RETURN!)")
        asm.append("    mov x18, x19")
        asm.append("")
        asm.append("    // Initialize call stack")
        asm.append("    adrp x20, call_stack_storage@PAGE")
        asm.append("    add x20, x20, call_stack_storage@PAGEOFF")
        asm.append("    str x20, [x24, #8]  // Store call stack base")
        asm.append("")
        asm.append("    mov x21, #0")
        asm.append("    str x21, [x24, #16]  // Call depth = 0")
        asm.append("")

         # NEW: Create a jump table in data section
        asm.insert(asm.index(".text"), "")
        asm.insert(asm.index(".text"), "    .align 3")
        asm.insert(asm.index(".text"), "jump_table:")
        for i in range(len(tokens)):
            asm.insert(asm.index(".text"), f"    .quad .token_{i}")
        asm.insert(asm.index(".text"), "")
    
    # Generate code for each token WITH LABELS
        for i, (typ, val) in enumerate(tokens):
            asm.append(f".token_{i}:")  # Label for this token position
            if typ == 'LIT':
                asm.extend(self.gen_push_literal(val))
            elif typ == 'OP':
                asm.extend(self.generate_op(val, i))  # Pass token index

        # Exit program
        asm.append("")
        asm.append("exit_program:")
        asm.append("    mov x0, #0      // exit code")
        asm.append("    mov x16, #1     // exit syscall")
        asm.append("    svc #0x80")
        asm.append("")

        # Helper functions
        asm.extend(self.generate_helpers())

        return "\n".join(asm)

    def gen_push_literal(self, value):
        """Push literal value to stack"""
        code = []
        code.append(f"    // PUSH {value}")
        code.append(f"    mov x0, #{value}")
        code.append(f"    str x0, [x19], #8")
        return code

    def generate_op(self, op, token_index=0):
        """Generate assembly for single operation"""
        code = []
        code.append(f"    // OP: {op} at token {token_index}")

        # Arithmetic operations
        if op == 'A':  # ADD
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    add x0, x0, x1")
            code.append("    str x0, [x19], #8")

        elif op == 's':  # SUBTRACT
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    sub x0, x0, x1")
            code.append("    str x0, [x19], #8")

        elif op == 'M':  # MULTIPLY
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    mul x0, x0, x1")
            code.append("    str x0, [x19], #8")

        elif op == 'D':  # DIVIDE
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    sdiv x0, x0, x1")
            code.append("    str x0, [x19], #8")

        elif op == 'X':  # MODULO
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    sdiv x2, x0, x1")
            code.append("    msub x0, x2, x1, x0")
            code.append("    str x0, [x19], #8")

        # Stack operations
        elif op == 'U':  # DUPLICATE
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    str x0, [x19], #8")
            code.append("    str x0, [x19], #8")

        elif op == 'W':  # SWAP
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    str x0, [x19], #8")
            code.append("    str x1, [x19], #8")

        elif op == 'V':  # DROP
            code.append("    sub x19, x19, #8")
            
        #array operations
        elif op == 'a':  # MAKE_ARRAY
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    mov x1, x25")
            code.append("    str x0, [x25], #8")
            code.append("    mov x2, x0")
            code.append(f".token{token_index}_loop:")
            code.append(f"    cbz x2, .token{token_index}_done")
            code.append("    sub x3, x2, #1")
            code.append("    lsl x3, x3, #3")
            code.append("    sub x4, x19, x3")
            code.append("    sub x4, x4, #8")
            code.append("    ldr x5, [x4]")
            code.append("    str x5, [x25], #8")
            code.append("    sub x2, x2, #1")
            code.append(f"    b .token{token_index}_loop")
            code.append(f".token{token_index}_done:")
            code.append("    lsl x0, x0, #3")
            code.append("    sub x19, x19, x0")
            code.append("    str x1, [x19], #8")

            
        elif op == 'l':
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    ldr x1, [x0]")
            code.append("    str x1, [x19], #8")
            
        elif op == 'g':
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    add x0, x0, #8")
            code.append("    ldr x3, [x0, x1, lsl #3]")
            code.append("    str x3, [x19], #8")


    



        # Memory operations
        elif op == 'T':  # STORE
            code.append("    // STORE - memory[addr] = value")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")       # Pop address
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")       # Pop value
            code.append("    str x1, [x24, x0, lsl #3]")

        elif op == 'F':  # LOAD
            code.append("    // LOAD - value = memory[addr]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")           # Pop address
            code.append("    ldr x1, [x24, x0, lsl #3]")  # ← CHANGED x20 to x24
            code.append("    str x1, [x19]")           # Push value
            code.append("    add x19, x19, #8")
            
        elif op == '@':  # POINTER_ADD
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]       // Offset")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]       // Pointer")
            code.append("    add x0, x0, x1      // Add offset to pointer")
            code.append("    str x0, [x19], #8")
            
        elif op == '#':  # POINTER_SUBTRACT
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]       // Offset")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]       // Pointer")
            code.append("    sub x0, x0, x1      // Subtract offset from pointer")
            code.append("    str x0, [x19], #8")
            
        elif op == 'B':  # READ_BUFFER
            code.append("    // READ_BUFFER - Load array reference from memory")
            code.append("    // Stack: addr -- [array]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]           // x0 = memory address")
            code.append("    lsl x0, x0, #3          // Scale address")
            code.append("    ldr x1, [x24, x0]       // x1 = array_ptr from memory")
            code.append("    str x1, [x19], #8       // Push array pointer")

        elif op == 'S':  # SET_BUFFER
            code.append("    // SET_BUFFER - Store array reference to memory")
            code.append("    // Stack: [array] addr --")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]           // x0 = memory address")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]           // x1 = array pointer")
            code.append("    lsl x0, x0, #3          // Scale address")
            code.append("    str x1, [x24, x0]       // memory[addr] = array_ptr")


        # Comparison operations
        elif op == 'E':  # EQUAL
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    cmp x0, x1")
            code.append("    cset x0, eq")
            code.append("    str x0, [x19], #8")

        elif op == 'G':  # GREATER_THAN
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    cmp x0, x1")
            code.append("    cset x0, gt")
            code.append("    str x0, [x19], #8")

        elif op == 'L':  # LESS_THAN
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    cmp x0, x1")
            code.append("    cset x0, lt")
            code.append("    str x0, [x19], #8")
            
        #logical operations
        elif op == '!':  # LOGICAL_NOT
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    cmp x0, #0")
            code.append("    cset x0, eq")  # Set to 1 if zero, 0 otherwise
            code.append("    str x0, [x19], #8")
            
        elif op == '&':  # LOGICAL_AND
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    cmp x0, #0")
            code.append("    cset x0, ne")  # x0 = (x0 != 0) ? 1 : 0
            code.append("    cmp x1, #0")
            code.append("    cset x1, ne")  # x1 = (x1 != 0) ? 1 : 0
            code.append("    and x0, x0, x1")  # Logical AND
            code.append("    str x0, [x19], #8")
            
        elif op == '|':  # LOGICAL_OR
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    orr x0, x0, x1")  # Bitwise OR
            code.append("    cmp x0, #0")
            code.append("    cset x0, ne")  # Convert to boolean: 1 if non-zero
            code.append("    str x0, [x19], #8")
            
        elif op == '^':  # LOGICAL_XOR
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    eor x0, x0, x1      // Bitwise XOR")
            code.append("    cmp x0, #0")
            code.append("    cset x0, ne         // Convert to boolean")
            code.append("    str x0, [x19], #8")
            
        elif op == 'Y':  # OVER
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")  # Top value (b)
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")  # Second value (a)
            code.append("    str x1, [x19], #8")  # Push a back
            code.append("    str x0, [x19], #8")  # Push b back
            code.append("    str x1, [x19], #8")  # Push a again
            
        elif op == 'R':  # ROTATE (fixed)
            code.append("    sub x19, x19, #8")
            code.append("    ldr x2, [x19]       // c (top)")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]       // b (middle)")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]       // a (bottom)")
            code.append("    str x1, [x19], #8   // Push b")
            code.append("    str x2, [x19], #8   // Push c")
            code.append("    str x0, [x19], #8   // Push a on top")
            
        #bitwise
        elif op == '~':  # BITWISE_NOT
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    mvn x0, x0          // Bitwise NOT")
            code.append("    str x0, [x19], #8")
            
        elif op == '<':  # BITWISE_SHL
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]       // Shift amount")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]       // Value to shift")
            code.append("    lsl x0, x0, x1      // Logical shift left")
            code.append("    str x0, [x19], #8")

        elif op == '>':  # BITWISE_SHR
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]       // Shift amount")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]       // Value to shift")
            code.append("    lsr x0, x0, x1      // Logical shift right")
            code.append("    str x0, [x19], #8")
            
        #Atomic operations
        elif op == '$':  # CAS
            code.append("    // CAS - Compare and Swap")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]           // Pop addr")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]           // Pop old_val")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x2, [x19]           // Pop new_val")
            code.append("    lsl x0, x0, #3")
            code.append("    add x3, x24, x0         // Memory address")
    
            code.append(f".token{token_index}_cas_retry:")
            code.append("    ldaxr x4, [x3]          // Load exclusive")
            code.append("    cmp x4, x1")
            code.append(f"    b.ne .token{token_index}_cas_fail")
            code.append("    stlxr w5, x2, [x3]      // Store exclusive")
            code.append(f"    cbnz w5, .token{token_index}_cas_retry")
            code.append("    mov x6, #1")
            code.append(f"    b .token{token_index}_cas_done")
    
            code.append(f".token{token_index}_cas_fail:")
            code.append("    clrex")
            code.append("    mov x6, #0")
    
            code.append(f".token{token_index}_cas_done:")
            code.append("    str x6, [x19], #8       // Push result")
            
        elif op == '%':  # TAS
            code.append("    // TAS - Test and Set")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]           // Pop addr")
            code.append("    lsl x0, x0, #3")
            code.append("    add x1, x24, x0         // Memory address")
    
            code.append(f".token{token_index}_tas_retry:")
            code.append("    ldaxr x2, [x1]          // Load exclusive")
            code.append("    mov x3, #1")
            code.append("    stlxr w4, x3, [x1]      // Store 1")
            code.append(f"    cbnz w4, .token{token_index}_tas_retry")
    
            code.append("    str x2, [x19], #8       // Push old value")
            
        elif op == '=':  # FENCE
            code.append("    // FENCE - Memory barrier")
            code.append("    dmb ish                 // Data Memory Barrier")



            
        #control flow
        elif op == 'J':  # JUMP
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]       // Load offset")
            code.append(f"    mov x1, #{token_index}")
            code.append("    add x1, x1, x0      // target = J_pos + offset")
            code.append("    adrp x2, jump_table@PAGE")
            code.append("    add x2, x2, jump_table@PAGEOFF")
            code.append("    ldr x3, [x2, x1, lsl #3]")
            code.append("    br x3")


            
        elif op == 'Z':
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")           # Pop offset
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")           # Pop value
            code.append("    cmp x1, #0")              # Compare to zero
            code.append(f"    b.ne .token{token_index}_skip") 
            code.append(f"    mov x2, #{token_index}")  # Current position
            code.append("    add x2, x2, x0")           # x2 = current + offset
            code.append("    adrp x3, jump_table@PAGE")
            code.append("    add x3, x3, jump_table@PAGEOFF")
            code.append("    ldr x4, [x3, x2, lsl #3]")
            code.append("    br x4")                    # Jump!
            code.append(f".token{token_index}_skip:") 
            
        elif op == 'N':
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")           # Pop offset
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")           # Pop value
            code.append("    cmp x1, #0")              # Compare to zero
            code.append(f"    b.eq .token{token_index}_skip")  
            code.append(f"    mov x2, #{token_index}")  # Current position
            code.append("    add x2, x2, x0")           # x2 = current + offset
            code.append("    adrp x3, jump_table@PAGE")
            code.append("    add x3, x3, jump_table@PAGEOFF")
            code.append("    ldr x4, [x3, x2, lsl #3]")
            code.append("    br x4")                    # Jump!
            code.append(f".token{token_index}_skip:")  # Continue if zero

        elif op == 'C':  # CALL
            code.append("    // CALL - Save return address and jump to function")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")  # Pop offset
            code.append("    ldr x1, [x24, #16]")  # ← FIXED: x20 → x24
            code.append("    cmp x1, #1000")  # Max depth = 1000
            code.append(f"    b.ge .token{token_index}_overflow")
            code.append(f"    mov x2, #{token_index + 1}")  # Return address
            code.append("    sub x3, x19, x18")  # Current stack size
            code.append("    lsr x3, x3, #3")  # Divide by 8 (size in elements)
            code.append("    ldr x4, [x24, #8]")  # ← FIXED: x20 → x24
            code.append("    str x2, [x4]")  # Save return address
            code.append("    str x3, [x4, #8]")  # Save stack size
            code.append("    add x4, x4, #16")  # Move call stack pointer
            code.append("    str x4, [x24, #8]")  # ← FIXED: x20 → x24
            code.append("    add x1, x1, #1")
            code.append("    str x1, [x24, #16]")  # ← FIXED: x20 → x24
            code.append(f"    mov x5, #{token_index}")
            code.append("    add x5, x5, x0")  # target = current + offset
            code.append("    adrp x6, jump_table@PAGE")
            code.append("    add x6, x6, jump_table@PAGEOFF")
            code.append("    ldr x7, [x6, x5, lsl #3]")
            code.append("    br x7")
            code.append(f".token{token_index}_overflow:")
            code.append("    mov x0, #1")  # Exit code 1
            code.append("    b exit_program")


        elif op == 'Q':  # RETURN
            code.append("    // RETURN - Restore stack and return to caller")
            code.append("    ldr x0, [x24, #16]")  # ← FIXED: x20 → x24
            code.append("    cmp x0, #0")
            code.append(f"    b.eq .token{token_index}_underflow")
            code.append("    mov x1, #0")  # Default return value
            code.append("    cmp x19, x18")  # Check if stack empty
            code.append(f"    b.eq .token{token_index}_no_rv")
            code.append("    sub x19, x19, #8")
            code.append("    ldr x1, [x19]")  # Pop return value
            code.append(f".token{token_index}_no_rv:")
            code.append("    ldr x2, [x24, #8]")  # ← FIXED: x20 → x24
            code.append("    sub x2, x2, #16")  # Move back
            code.append("    ldr x3, [x2]")  # Load return address
            code.append("    ldr x4, [x2, #8]")  # Load saved stack size
            code.append("    str x2, [x24, #8]")  # ← FIXED: x20 → x24
            code.append("    sub x0, x0, #1")
            code.append("    str x0, [x24, #16]")  # ← FIXED: x20 → x24
            code.append("    lsl x4, x4, #3")  # Multiply by 8
            code.append("    add x19, x18, x4")  # Restore stack pointer
            code.append("    str x1, [x19]")
            code.append("    add x19, x19, #8")
            code.append("    adrp x5, jump_table@PAGE")
            code.append("    add x5, x5, jump_table@PAGEOFF")
            code.append("    ldr x6, [x5, x3, lsl #3]")
            code.append("    br x6")
            code.append(f".token{token_index}_underflow:")
            code.append("    mov x0, #1")
            code.append("    b exit_program")



        # I/O operations
        elif op == 'P':  # PRINT
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    bl print_int")
            
        elif op == 'I':  # INPUT
            code.append("    bl read_int")
            code.append("    str x0, [x19], #8   // Push result to stack")
            
        elif op == 'K':  # GET_CHARACTER
            code.append("    bl read_char")
            code.append("    str x0, [x19], #8")
            
        elif op == 'O':  # PUT_CHARACTER
            code.append("    sub x19, x19, #8")
            code.append("    ldr x0, [x19]")
            code.append("    bl print_char")
            
        elif op == 'p': # PRINTSTRING
            code.append(" // PRINTSTRING: [array] --")
            code.append(" sub x19, x19, #8")
            code.append(" ldr x0, [x19]      // Pop array address")
            code.append(" bl print_string")


        elif op == 'H':  # HALT
            code.append("    b exit_program")

        else:
            code.append(f"    // TODO: Implement {op}")

        return code

    def generate_helpers(self):
        """Generate helper functions"""
        code = []

        # print_int function - converts integer to string and prints
        code.append("// Helper: Print integer in x0")
        code.append("print_int:")
        code.append("    stp x29, x30, [sp, #-16]!")
        code.append("    mov x29, sp")
        code.append("    ")
        code.append("    // Get print buffer address")
        code.append("    adrp x10, print_buffer@PAGE")
        code.append("    add x10, x10, print_buffer@PAGEOFF")
        code.append("    add x10, x10, #31      // Point to end of buffer")
        code.append("    mov x11, #0            // Null terminator")
        code.append("    strb w11, [x10]")
        code.append("    ")
        code.append("    // Handle negative numbers")
        code.append("    mov x12, #0            // Sign flag")
        code.append("    cmp x0, #0")
        code.append("    bge .Lpositive")
        code.append("    mov x12, #1            // Set sign flag")
        code.append("    neg x0, x0             // Make positive")
        code.append("    ")
        code.append(".Lpositive:")
        code.append("    mov x13, #10           // Divisor")
        code.append("    ")
        code.append(".Lconvert_loop:")
        code.append("    udiv x1, x0, x13       // x1 = x0 / 10")
        code.append("    msub x2, x1, x13, x0   // x2 = x0 - (x1 * 10) = remainder")
        code.append("    add x2, x2, #48        // Convert to ASCII")
        code.append("    sub x10, x10, #1")
        code.append("    strb w2, [x10]")
        code.append("    mov x0, x1             // x0 = quotient")
        code.append("    cbnz x0, .Lconvert_loop")
        code.append("    ")
        code.append("    // Add minus sign if negative")
        code.append("    cbz x12, .Lprint")
        code.append("    mov x2, #45            // ASCII '-'")
        code.append("    sub x10, x10, #1")
        code.append("    strb w2, [x10]")
        code.append("    ")
        code.append(".Lprint:")
        code.append("    // Calculate length")
        code.append("    adrp x11, print_buffer@PAGE")
        code.append("    add x11, x11, print_buffer@PAGEOFF")
        code.append("    add x11, x11, #31")
        code.append("    sub x2, x11, x10       // length")
        code.append("    ")
        code.append("    // Print newline after number")
        code.append("    mov x11, #10           // newline")
        code.append("    adrp x13, print_buffer@PAGE")
        code.append("    add x13, x13, print_buffer@PAGEOFF")
        code.append("    add x13, x13, #31")
        code.append("    strb w11, [x13]")
        code.append("    add x2, x2, #1         // Include newline in length")
        code.append("    ")
        code.append("    // Syscall write(fd=1, buf=x10, len=x2)")
        code.append("    mov x0, #1             // stdout")
        code.append("    mov x1, x10            // buffer")
        code.append("    mov x16, #4            // write syscall")
        code.append("    svc #0x80")
        code.append("    ")
        code.append("    ldp x29, x30, [sp], #16")
        code.append("    ret")
        code.append("")
        code.append("// Helper: Read integer from stdin")
        code.append("read_int:")
        code.append("    stp x29, x30, [sp, #-16]!")
        code.append("    mov x29, sp")
        code.append("    ")
        code.append("    // Allocate buffer on stack")
        code.append("    sub sp, sp, #32")
        code.append("    ")
        code.append("    // Read from stdin (syscall 3)")
        code.append("    mov x0, #0              // stdin fd")
        code.append("    mov x1, sp              // buffer")
        code.append("    mov x2, #31             // max bytes")
        code.append("    mov x16, #3             // read syscall")
        code.append("    svc #0x80")
        code.append("    ")
        code.append("    // Convert ASCII to integer")
        code.append("    mov x10, sp             // Buffer pointer")
        code.append("    mov x11, #0             // Result accumulator")
        code.append("    mov x12, #0             // Sign flag")
        code.append("    ")
        code.append("    // Check for minus sign")
        code.append("    ldrb w13, [x10]")
        code.append("    cmp w13, #45            // ASCII '-'")
        code.append("    b.ne .Lparse_digits")
        code.append("    mov x12, #1             // Set sign flag")
        code.append("    add x10, x10, #1        // Skip minus")
        code.append("    ")
        code.append(".Lparse_digits:")
        code.append("    ldrb w13, [x10], #1     // Load byte and increment")
        code.append("    cmp w13, #10            // Newline?")
        code.append("    b.eq .Lparse_done")
        code.append("    cmp w13, #48            // Less than '0'?")
        code.append("    b.lt .Lparse_done")
        code.append("    cmp w13, #57            // Greater than '9'?")
        code.append("    b.gt .Lparse_done")
        code.append("    sub w13, w13, #48       // Convert to digit")
        code.append("    mov x14, #10")
        code.append("    mul x11, x11, x14       // result *= 10")
        code.append("    add x11, x11, x13       // result += digit")
        code.append("    b .Lparse_digits")
        code.append("    ")
        code.append(".Lparse_done:")
        code.append("    // Apply sign if negative")
        code.append("    cmp x12, #0")
        code.append("    b.eq .Lreturn")
        code.append("    neg x11, x11")
        code.append("    ")
        code.append(".Lreturn:")
        code.append("    mov x0, x11             // Return value in x0")
        code.append("    add sp, sp, #32         // Clean up buffer")
        code.append("    ldp x29, x30, [sp], #16")
        code.append("    ret")
        code.append("")
        code.append("// Helper: Read single character from stdin")
        code.append("read_char:")
        code.append("    stp x29, x30, [sp, #-16]!")
        code.append("    mov x29, sp")
        code.append("    ")
        code.append("    sub sp, sp, #16")
        code.append("    ")
        code.append("    // Read syscall (3)")
        code.append("    mov x0, #0          // stdin")
        code.append("    mov x1, sp          // buffer")
        code.append("    mov x2, #1          // read 1 byte")
        code.append("    mov x16, #3")
        code.append("    svc #0x80")
        code.append("    ")
        code.append("    // Load character")
        code.append("    ldrb w0, [sp]       // Get byte")
        code.append("    ")
        code.append("    add sp, sp, #16")
        code.append("    ldp x29, x30, [sp], #16")
        code.append("    ret")
        code.append("")
        code.append("// Helper: Print single character in x0")
        code.append("print_char:")
        code.append("    stp x29, x30, [sp, #-16]!")
        code.append("    mov x29, sp")
        code.append("    ")
        code.append("    sub sp, sp, #16")
        code.append("    strb w0, [sp]       // Store character")
        code.append("    ")
        code.append("    // Write syscall (4)")
        code.append("    mov x0, #1          // stdout")
        code.append("    mov x1, sp          // buffer")
        code.append("    mov x2, #1          // 1 byte")
        code.append("    mov x16, #4")
        code.append("    svc #0x80")
        code.append("    ")
        code.append("    add sp, sp, #16")
        code.append("    ldp x29, x30, [sp], #16")
        code.append("    ret")
        code.append("")
        
        code.append("// Helper: Print string from array")
        code.append("print_string:")
        code.append(" stp x29, x30, [sp, #-16]!")
        code.append(" mov x29, sp")
        code.append(" ")
        code.append(" // x0 = array address (format: [length, val1, val2, ...])")
        code.append(" ldr x1, [x0], #8      // Load length, advance to data")
        code.append(" cbz x1, .print_string_done")
        code.append(" ")
        code.append(" // Allocate buffer on stack (max 256 chars)")
        code.append(" sub sp, sp, #256")
        code.append(" mov x10, sp           // Buffer pointer")
        code.append(" mov x11, #0           // Buffer index")
        code.append(" ")
        code.append(".print_string_loop:")
        code.append(" ldr x12, [x0], #8     // Load 64-bit element, advance")
        code.append(" strb w12, [x10, x11]  // Store low byte to buffer")
        code.append(" add x11, x11, #1      // Increment buffer index")
        code.append(" subs x1, x1, #1       // Decrement count")
        code.append(" bne .print_string_loop")
        code.append(" ")
        code.append(" // Write buffer to stdout")
        code.append(" mov x0, #1            // stdout")
        code.append(" mov x1, sp            // buffer address")
        code.append(" mov x2, x11           // length")
        code.append(" mov x16, #4           // write syscall")
        code.append(" svc #0x80")
        code.append(" ")
        code.append(" add sp, sp, #256      // Clean up buffer")
        code.append(" ")
        code.append(".print_string_done:")
        code.append(" ldp x29, x30, [sp], #16")
        code.append(" ret")
        code.append("") 


        return code

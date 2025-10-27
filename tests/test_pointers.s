.global _start
.align 4

.data
stack_storage:
    .space 8192

memory_storage:
    .space 80000  // Memory for STORE/LOAD operations

print_buffer:
    .space 32  // Buffer for number to string conversion


call_stack_storage:
    .space 16000  // 1000 calls × 16 bytes

call_stack_meta:
    .quad 0  // Call stack pointer
    .quad 0  // Call depth counter


    .align 3
jump_table:
    .quad .token_0
    .quad .token_1
    .quad .token_2
    .quad .token_3
    .quad .token_4
    .quad .token_5
    .quad .token_6
    .quad .token_7
    .quad .token_8
    .quad .token_9
    .quad .token_10
    .quad .token_11
    .quad .token_12
    .quad .token_13
    .quad .token_14
    .quad .token_15
    .quad .token_16
    .quad .token_17
    .quad .token_18
    .quad .token_19

.text
_start:
    // Initialize ELI stack
    adrp x19, stack_storage@PAGE
    add x19, x19, stack_storage@PAGEOFF

    // Initialize memory base
    adrp x24, memory_storage@PAGE
    add x24, x24, memory_storage@PAGEOFF

    // Initialize array allocator
    adrp x25, memory_storage@PAGE
    add x25, x25, memory_storage@PAGEOFF
    mov w0, #40000              // Use 32-bit mov
    add x25, x25, x0
    // Save stack base pointer (REQUIRED for CALL/RETURN!)
    mov x18, x19

    // Initialize call stack
    adrp x20, call_stack_storage@PAGE
    add x20, x20, call_stack_storage@PAGEOFF
    str x20, [x24, #8]  // Store call stack base

    mov x21, #0
    str x21, [x24, #16]  // Call depth = 0

.token_0:
    // PUSH 1000
    mov x0, #1000
    str x0, [x19], #8
.token_1:
    // PUSH 10
    mov x0, #10
    str x0, [x19], #8
.token_2:
    // OP: @ at token 2
    sub x19, x19, #8
    ldr x1, [x19]       // Offset
    sub x19, x19, #8
    ldr x0, [x19]       // Pointer
    add x0, x0, x1      // Add offset to pointer
    str x0, [x19], #8
.token_3:
    // OP: P at token 3
    sub x19, x19, #8
    ldr x0, [x19]
    bl print_int
.token_4:
    // PUSH 2000
    mov x0, #2000
    str x0, [x19], #8
.token_5:
    // PUSH 500
    mov x0, #500
    str x0, [x19], #8
.token_6:
    // OP: # at token 6
    sub x19, x19, #8
    ldr x1, [x19]       // Offset
    sub x19, x19, #8
    ldr x0, [x19]       // Pointer
    sub x0, x0, x1      // Subtract offset from pointer
    str x0, [x19], #8
.token_7:
    // OP: P at token 7
    sub x19, x19, #8
    ldr x0, [x19]
    bl print_int
.token_8:
    // PUSH 10
    mov x0, #10
    str x0, [x19], #8
.token_9:
    // PUSH 20
    mov x0, #20
    str x0, [x19], #8
.token_10:
    // PUSH 30
    mov x0, #30
    str x0, [x19], #8
.token_11:
    // PUSH 3
    mov x0, #3
    str x0, [x19], #8
.token_12:
    // OP: a at token 12
    sub x19, x19, #8
    ldr x0, [x19]
    mov x1, x25
    str x0, [x25], #8
    mov x2, x0
.token12_loop:
    cbz x2, .token12_done
    sub x3, x2, #1
    lsl x3, x3, #3
    sub x4, x19, x3
    sub x4, x4, #8
    ldr x5, [x4]
    str x5, [x25], #8
    sub x2, x2, #1
    b .token12_loop
.token12_done:
    lsl x0, x0, #3
    sub x19, x19, x0
    str x1, [x19], #8
.token_13:
    // PUSH 100
    mov x0, #100
    str x0, [x19], #8
.token_14:
    // OP: S at token 14
    // SET_BUFFER - Store array reference to memory
    // Stack: [array] addr --
    sub x19, x19, #8
    ldr x0, [x19]           // x0 = memory address
    sub x19, x19, #8
    ldr x1, [x19]           // x1 = array pointer
    lsl x0, x0, #3          // Scale address
    str x1, [x24, x0]       // memory[addr] = array_ptr
.token_15:
    // PUSH 100
    mov x0, #100
    str x0, [x19], #8
.token_16:
    // OP: B at token 16
    // READ_BUFFER - Load array reference from memory
    // Stack: addr -- [array]
    sub x19, x19, #8
    ldr x0, [x19]           // x0 = memory address
    lsl x0, x0, #3          // Scale address
    ldr x1, [x24, x0]       // x1 = array_ptr from memory
    str x1, [x19], #8       // Push array pointer
.token_17:
    // OP: l at token 17
    sub x19, x19, #8
    ldr x0, [x19]
    ldr x1, [x0]
    str x1, [x19], #8
.token_18:
    // OP: P at token 18
    sub x19, x19, #8
    ldr x0, [x19]
    bl print_int
.token_19:
    // OP: H at token 19
    b exit_program

exit_program:
    mov x0, #0      // exit code
    mov x16, #1     // exit syscall
    svc #0x80

// Helper: Print integer in x0
print_int:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    
    // Get print buffer address
    adrp x10, print_buffer@PAGE
    add x10, x10, print_buffer@PAGEOFF
    add x10, x10, #31      // Point to end of buffer
    mov x11, #0            // Null terminator
    strb w11, [x10]
    
    // Handle negative numbers
    mov x12, #0            // Sign flag
    cmp x0, #0
    bge .Lpositive
    mov x12, #1            // Set sign flag
    neg x0, x0             // Make positive
    
.Lpositive:
    mov x13, #10           // Divisor
    
.Lconvert_loop:
    udiv x1, x0, x13       // x1 = x0 / 10
    msub x2, x1, x13, x0   // x2 = x0 - (x1 * 10) = remainder
    add x2, x2, #48        // Convert to ASCII
    sub x10, x10, #1
    strb w2, [x10]
    mov x0, x1             // x0 = quotient
    cbnz x0, .Lconvert_loop
    
    // Add minus sign if negative
    cbz x12, .Lprint
    mov x2, #45            // ASCII '-'
    sub x10, x10, #1
    strb w2, [x10]
    
.Lprint:
    // Calculate length
    adrp x11, print_buffer@PAGE
    add x11, x11, print_buffer@PAGEOFF
    add x11, x11, #31
    sub x2, x11, x10       // length
    
    // Print newline after number
    mov x11, #10           // newline
    adrp x13, print_buffer@PAGE
    add x13, x13, print_buffer@PAGEOFF
    add x13, x13, #31
    strb w11, [x13]
    add x2, x2, #1         // Include newline in length
    
    // Syscall write(fd=1, buf=x10, len=x2)
    mov x0, #1             // stdout
    mov x1, x10            // buffer
    mov x16, #4            // write syscall
    svc #0x80
    
    ldp x29, x30, [sp], #16
    ret

// Helper: Read integer from stdin
read_int:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    
    // Allocate buffer on stack
    sub sp, sp, #32
    
    // Read from stdin (syscall 3)
    mov x0, #0              // stdin fd
    mov x1, sp              // buffer
    mov x2, #31             // max bytes
    mov x16, #3             // read syscall
    svc #0x80
    
    // Convert ASCII to integer
    mov x10, sp             // Buffer pointer
    mov x11, #0             // Result accumulator
    mov x12, #0             // Sign flag
    
    // Check for minus sign
    ldrb w13, [x10]
    cmp w13, #45            // ASCII '-'
    b.ne .Lparse_digits
    mov x12, #1             // Set sign flag
    add x10, x10, #1        // Skip minus
    
.Lparse_digits:
    ldrb w13, [x10], #1     // Load byte and increment
    cmp w13, #10            // Newline?
    b.eq .Lparse_done
    cmp w13, #48            // Less than '0'?
    b.lt .Lparse_done
    cmp w13, #57            // Greater than '9'?
    b.gt .Lparse_done
    sub w13, w13, #48       // Convert to digit
    mov x14, #10
    mul x11, x11, x14       // result *= 10
    add x11, x11, x13       // result += digit
    b .Lparse_digits
    
.Lparse_done:
    // Apply sign if negative
    cmp x12, #0
    b.eq .Lreturn
    neg x11, x11
    
.Lreturn:
    mov x0, x11             // Return value in x0
    add sp, sp, #32         // Clean up buffer
    ldp x29, x30, [sp], #16
    ret

// Helper: Read single character from stdin
read_char:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    
    sub sp, sp, #16
    
    // Read syscall (3)
    mov x0, #0          // stdin
    mov x1, sp          // buffer
    mov x2, #1          // read 1 byte
    mov x16, #3
    svc #0x80
    
    // Load character
    ldrb w0, [sp]       // Get byte
    
    add sp, sp, #16
    ldp x29, x30, [sp], #16
    ret

// Helper: Print single character in x0
print_char:
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    
    sub sp, sp, #16
    strb w0, [sp]       // Store character
    
    // Write syscall (4)
    mov x0, #1          // stdout
    mov x1, sp          // buffer
    mov x2, #1          // 1 byte
    mov x16, #4
    svc #0x80
    
    add sp, sp, #16
    ldp x29, x30, [sp], #16
    ret

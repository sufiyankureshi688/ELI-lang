# -------------------------------
# ELI v10.0 — AI-First Stack Language
# -------------------------------

import copy

class ALPHA_2:
    """
    ELI v10.0 — AI-FIRST STACK LANGUAGE
    
    MAJOR CHANGES from v7.1:
    ✓ REMOVED label system - AI uses relative offsets directly
    ✓ FIXED buffer operations - normal stack order, safe copies
    ✓ ADDED string auto-conversion - "HELLO" → [72,69,76,76,79]
    
    42 unique opcodes (zero collisions):
    - Arithmetic, comparison, boolean, bitwise operations
    - Stack manipulation primitives
    - Memory operations with pointer arithmetic
    - Atomic operations for multicore systems
    - Control flow with relative offsets (NO LABELS)
    - Basic I/O primitives
    
    Design principle: Machine-first for AI code generation.
    Everything optimized for AI, not human readability.
    """
    
    def __init__(self):
        # Core execution state
        self.stack = []           # Main operand stack
        self.memory = {}          # address -> value mapping
        self.call_stack = []      # Function call frames
        self.pc = 0               # Program counter
        self.tokens = []          # Tokenized program (NO LABELS)
        self.debug = False        # Debug output
        self.max_call_depth = 1000  # Stack overflow protection
        
        # Dispatch table: ALL 42 OPCODES
        self.ops = {
            # Arithmetic (7 opcodes)
            'A': self.op_add,        # a b -- (a+b)
            's': self.op_sub,        # a b -- (a-b)
            'M': self.op_mul,        # a b -- (a*b)
            'D': self.op_div,        # a b -- (a//b)
            'X': self.op_mod,        # a b -- (a%b)
            'a': self.op_make_array, # v1..vN N -- [array]
            'l': self.op_length,     # [array] -- len
            'g': self.op_get_index,  # [array] idx -- value
            
            # Comparison (3 opcodes)
            'E': self.op_eq,         # a b -- (a==b ? 1 : 0)
            'G': self.op_gt,         # a b -- (a>b ? 1 : 0)
            'L': self.op_lt,         # a b -- (a<b ? 1 : 0)
            
            # Boolean (4 opcodes)
            '!': self.op_not,        # a -- (!a)
            '&': self.op_and,        # a b -- (a&b)
            '|': self.op_or,         # a b -- (a|b)
            '^': self.op_xor,        # a b -- (a^b)
            
            # Bitwise (3 opcodes)
            '~': self.op_bnot,       # a -- (~a)
            '<': self.op_shl,        # a b -- (a<<b)
            '>': self.op_shr,        # a b -- (a>>b)
            
            # Stack manipulation (5 opcodes)
            'U': self.op_dup,        # a -- a a
            'W': self.op_swap,       # a b -- b a
            'V': self.op_drop,       # a --
            'Y': self.op_over,       # a b -- a b a
            'R': self.op_rot,        # a b c -- b c a
            
            # Memory operations (6 opcodes)
            'T': self.op_store,      # val addr --
            'F': self.op_load,       # addr -- val
            '@': self.op_ptr_add,    # ptr offset -- (ptr+offset)
            '#': self.op_ptr_sub,    # ptr offset -- (ptr-offset)
            'B': self.op_read_buffer,  # addr -- [array]
            'S': self.op_set_buffer,   # [array] addr --
            
            # Atomic operations (3 opcodes)
            '$': self.op_cas,        # new old addr -- success
            '%': self.op_tas,        # addr -- old_value
            '=': self.op_fence,      # -- (memory barrier)
            
            # Control flow (4 opcodes) - CHANGED: use relative offsets
            'J': self.op_jump,       # offset --
            'Z': self.op_jump_zero,  # offset val --
            'N': self.op_jump_not_zero,  # offset val --
            'H': self.op_halt,       # --
            
            # Function calls (2 opcodes)
            'C': self.op_call,       # offset --
            'Q': self.op_return,     # --
            
            # I/O (4 opcodes)
            'P': self.op_print_int,  # n --
            'I': self.op_input_int,  # -- n
            'K': self.op_input_char, # -- ascii
            'O': self.op_print_char  # ascii --
        }
    
    # =============================
    # TOKENIZATION
    # =============================
    
    def is_hex(self, c):
        return c in "0123456789abcdefABCDEF"
    
    def tokenize(self, program):
        """
        Tokenize program.
        CHANGED: NO LABEL SUPPORT - AI uses relative offsets
        ADDED: String literal support with auto-conversion
        """
        tokens = []
        i = 0
        
        while i < len(program):
            c = program[i]
            
            # Skip whitespace
            if c in " \n\t\r":
                i += 1
                continue
            
            # String literal - NEW: Auto-convert to ASCII array
            if c == '"':
                i += 1
                string_chars = []
                while i < len(program) and program[i] != '"':
                    string_chars.append(ord(program[i]))
                    i += 1
                if i < len(program):
                    i += 1  # Skip closing quote
                tokens.append(('BUFFER', string_chars))
                continue
            
            # Negative number
            if c == '-' and i + 1 < len(program) and program[i+1].isdigit():
                i += 1
                num_str = '-'
                while i < len(program) and program[i].isdigit():
                    num_str += program[i]
                    i += 1
                tokens.append(('LIT', int(num_str)))
                continue
            
            # Hexadecimal literal (0xNNNN)
            if c == '0' and i + 1 < len(program) and program[i+1] in 'xX':
                i += 2
                hex_lit = ''
                while i < len(program) and self.is_hex(program[i]):
                    hex_lit += program[i]
                    i += 1
                if not hex_lit:
                    raise ValueError(f"Empty hex literal at position {i-2}")
                tokens.append(('LIT', int(hex_lit, 16)))
                continue
            
            # Decimal number
            if c.isdigit():
                num_str = ''
                while i < len(program) and program[i].isdigit():
                    num_str += program[i]
                    i += 1
                tokens.append(('LIT', int(num_str)))
                continue
            
            # Operation (uppercase + special chars + lowercase 's')
            if c.isupper() or c in '!&|^~<>@#=s$%alg':
                tokens.append(('OP', c))
                i += 1
                continue
            
            raise ValueError(f"Invalid character '{c}' at position {i}")
        
        return tokens
    
    # =============================
    # EXECUTION ENGINE
    # =============================
    
    def execute(self, program):
        """Execute program. NO LABEL PREPROCESSING - AI uses offsets directly."""
        # Reset state
        self.stack = []
        self.memory = {}
        self.call_stack = []
        self.pc = 0
        
        # Tokenize (no label preprocessing)
        self.tokens = self.tokenize(program)
        
        # Main execution loop
        while self.pc < len(self.tokens):
            typ, val = self.tokens[self.pc]
            
            if self.debug:
                print(f"[{self.pc:3d}] {typ:6s} {str(val):15s} | Stack: {self.stack}")
            
            if typ == 'LIT':
                self.stack.append(val)
                self.pc += 1
            elif typ == 'BUFFER':
                self.stack.append(val)
                self.pc += 1
            elif typ == 'OP':
                if val not in self.ops:
                    print(f"Unknown operation: '{val}' at token {self.pc}")
                    return None
                if self.ops[val]() is False:
                    print(f"Runtime error: '{val}' at token {self.pc} | Stack: {self.stack}")
                    return None
                self.pc += 1
        
        return self.stack
    
    # =============================
    # HELPER FUNCTIONS
    # =============================
    
    def _binop(self, func):
        if len(self.stack) < 2:
            return False
        b = self.stack.pop()
        a = self.stack.pop()
        res = func(a, b)
        if res is False:
            return False
        self.stack.append(res)
        return True
    
    # =============================
    # ARITHMETIC OPERATIONS
    # =============================
    
    def op_add(self):
        return self._binop(lambda a, b: a + b)
    
    def op_sub(self):
        return self._binop(lambda a, b: a - b)
    
    def op_mul(self):
        return self._binop(lambda a, b: a * b)
    
    def op_div(self):
        return self._binop(lambda a, b: a // b if b != 0 else False)
    
    def op_mod(self):
        return self._binop(lambda a, b: a % b if b != 0 else False)
    
    # =============================

    def op_make_array(self):
        """Build array from N stack items: v1 v2 ... vN N -- [array]"""
        if not self.stack:
            return False
        n = self.stack.pop()
        if n < 0 or len(self.stack) < n:
            return False
        items = []
        for _ in range(n):
            items.append(self.stack.pop())
        items.reverse()
        self.stack.append(items)
        return True

    def op_length(self):
        """Get array length: [array] -- len"""
        if not self.stack:
            return False
        arr = self.stack.pop()
        if not isinstance(arr, list):
            return False
        self.stack.append(len(arr))
        return True

    def op_get_index(self):
        """Get element at index: [array] idx -- value"""
        if len(self.stack) < 2:
            return False
        idx = self.stack.pop()
        arr = self.stack.pop()
        if not isinstance(arr, list):
            return False
        if idx < 0 or idx >= len(arr):
            return False
        self.stack.append(arr[idx])
        return True

    # COMPARISON OPERATIONS
    # =============================
    
    def op_eq(self):
        return self._binop(lambda a, b: 1 if a == b else 0)
    
    def op_gt(self):
        return self._binop(lambda a, b: 1 if a > b else 0)
    
    def op_lt(self):
        return self._binop(lambda a, b: 1 if a < b else 0)
    
    # =============================
    # BOOLEAN OPERATIONS
    # =============================
    
    def op_not(self):
        if not self.stack:
            return False
        self.stack.append(0 if self.stack.pop() else 1)
        return True
    
    def op_and(self):
        return self._binop(lambda a, b: a & b)
    
    def op_or(self):
        return self._binop(lambda a, b: a | b)
    
    def op_xor(self):
        return self._binop(lambda a, b: a ^ b)
    
    def op_bnot(self):
        if not self.stack:
            return False
        self.stack.append(~self.stack.pop())
        return True
    
    # =============================
    # BITWISE SHIFT OPERATIONS
    # =============================
    
    def op_shl(self):
        """Shift left with bounds checking"""
        return self._binop(lambda a, b: a << b if 0 <= b <= 64 else False)
    
    def op_shr(self):
        """Shift right with bounds checking"""
        return self._binop(lambda a, b: a >> b if 0 <= b <= 64 else False)
    
    # =============================
    # STACK MANIPULATION
    # =============================
    
    def op_dup(self):
        if not self.stack:
            return False
        self.stack.append(self.stack[-1])
        return True
    
    def op_swap(self):
        if len(self.stack) < 2:
            return False
        self.stack[-1], self.stack[-2] = self.stack[-2], self.stack[-1]
        return True
    
    def op_drop(self):
        if not self.stack:
            return False
        self.stack.pop()
        return True
    
    def op_over(self):
        if len(self.stack) < 2:
            return False
        self.stack.append(self.stack[-2])
        return True
    
    def op_rot(self):
        if len(self.stack) < 3:
            return False
        self.stack[-3], self.stack[-2], self.stack[-1] = self.stack[-2], self.stack[-1], self.stack[-3]
        return True
    
    # =============================
    # MEMORY OPERATIONS - FIXED
    # =============================
    
    def op_store(self):
        if len(self.stack) < 2:
            return False
        addr = self.stack.pop()
        val = self.stack.pop()
        self.memory[addr] = val
        return True
    
    def op_load(self):
        if not self.stack:
            return False
        addr = self.stack.pop()
        self.stack.append(self.memory.get(addr, 0))
        return True
    
    def op_ptr_add(self):
        if len(self.stack) < 2:
            return False
        offset = self.stack.pop()
        ptr = self.stack.pop()
        self.stack.append(ptr + offset)
        return True
    
    def op_ptr_sub(self):
        if len(self.stack) < 2:
            return False
        offset = self.stack.pop()
        ptr = self.stack.pop()
        self.stack.append(ptr - offset)
        return True
    
    def op_read_buffer(self):
        """
        FIXED: Returns a COPY of the buffer for memory safety.
        Stack: addr -- [array]
        """
        if not self.stack:
            return False
        addr = self.stack.pop()
        buf = self.memory.get(addr, [])
        
        # Return copy for safety
        if isinstance(buf, list):
            self.stack.append(copy.deepcopy(buf))
        else:
            # Single value - wrap in list
            self.stack.append([buf])
        return True
    
    def op_set_buffer(self):
        """
        FIXED: Normal stack order - buffer addr !
        NO length field - stores buffer atomically
        Stack: [array] addr --
        """
        if len(self.stack) < 2:
            return False
        addr = self.stack.pop()
        buf = self.stack.pop()
        
        if not isinstance(buf, list):
            return False
        
        # Store buffer as atomic value (copy for safety)
        self.memory[addr] = copy.deepcopy(buf)
        return True
    
    # =============================
    # ATOMIC OPERATIONS
    # =============================
    
    def op_cas(self):
        """Compare-and-swap: new old addr -- success"""
        if len(self.stack) < 3:
            return False
        addr = self.stack.pop()
        old_val = self.stack.pop()
        new_val = self.stack.pop()
        
        current = self.memory.get(addr, 0)
        if current == old_val:
            self.memory[addr] = new_val
            self.stack.append(1)  # Success
        else:
            self.stack.append(0)  # Failure
        return True
    
    def op_tas(self):
        """Test-and-set: addr -- old_value"""
        if not self.stack:
            return False
        addr = self.stack.pop()
        old_val = self.memory.get(addr, 0)
        self.stack.append(old_val)
        self.memory[addr] = 1
        return True
    
    def op_fence(self):
        """Memory fence (no-op in Python)"""
        return True
    
    # =============================
    # CONTROL FLOW - FIXED FOR AI
    # =============================
    
    def op_jump(self):
        """
        FIXED: Jump using relative offset (not labels)
        Stack: offset --
        AI calculates offset directly
        """
        if not self.stack:
            return False
        offset = self.stack.pop()
        self.pc += offset - 1  # -1 because pc++ happens after
        return True
    
    def op_jump_zero(self):
        """
        FIXED: Conditional jump with relative offset
        Stack: offset val --
        Jumps if val == 0
        """
        if len(self.stack) < 2:
            return False
        offset = self.stack.pop()
        val = self.stack.pop()
        
        if val == 0:
            self.pc += offset - 1
        return True
    
    def op_jump_not_zero(self):
        """
        FIXED: Conditional jump with relative offset
        Stack: offset val --
        Jumps if val != 0
        """
        if len(self.stack) < 2:
            return False
        offset = self.stack.pop()
        val = self.stack.pop()
        
        if val != 0:
            self.pc += offset - 1
        return True
    
    def op_halt(self):
        self.pc = len(self.tokens)
        return True
    
    # =============================
    # FUNCTION CALLS
    # =============================
    
    def op_call(self):
        """CALL - Jump to function using relative offset"""
        if not self.stack:
            return False
        if len(self.call_stack) >= self.max_call_depth:
            print(f"Max call depth {self.max_call_depth} exceeded")
            return False
    
        offset = self.stack.pop()
    
    # Save return address and stack size BEFORE the call
        self.call_stack.append((self.pc + 1, len(self.stack)))
    
    # Jump: current pc + offset, then loop adds 1, so subtract 1 here
        self.pc = self.pc + offset - 1
        return True


    def op_return(self):
        """
        RETURN - Return from function
        Stack: return_value --
        Restores stack to call state and pushes return value
        """
        if not self.call_stack:
            return False
    
        # Pop return value (must exist)
        if not self.stack:
            return False
        return_value = self.stack.pop()
    
    # Restore call state
        ret_addr, prev_stack_size = self.call_stack.pop()
    
    # Restore stack to size at call time (removes function args)
        self.stack = self.stack[:prev_stack_size]
    
    # Push return value onto restored stack
        self.stack.append(return_value)
    
    # Jump to return address (subtract 1 for loop increment)
        self.pc = ret_addr - 1
        return True



    
    # =============================
    # I/O OPERATIONS
    # =============================
    
    def op_print_int(self):
        """Print integer - STRICT: requires int type"""
        if not self.stack:
            return False
        val = self.stack.pop()
        if not isinstance(val, int):
            return False
        print(val)
        return True
    
    def op_input_int(self):
        """Input integer - STRICT: no fallback to 0"""
        try:
            val = int(input("Int: "))
            self.stack.append(val)
            return True
        except (ValueError, EOFError):
            return False
    
    def op_input_char(self):
        """Input character - STRICT: requires exactly 1 char"""
        try:
            val = input("Char: ")
            if len(val) != 1:
                return False
            self.stack.append(ord(val))
            return True
        except (EOFError, KeyboardInterrupt):
            return False
    
    def op_print_char(self):
        """Print character - STRICT: valid Unicode only (0-0x10FFFF)"""
        if not self.stack:
            return False
        val = self.stack.pop()
        if not isinstance(val, int):
            return False
        if val < 0 or val > 0x10FFFF:
            return False
        try:
            print(chr(val), end='')
            return True
        except ValueError:
            return False


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ELI_v10_STRICT.py <program.eli>")
        print("   or: python ELI_v10_STRICT.py -c 'code here'")
        sys.exit(1)

    vm = ALPHA_2()

    if sys.argv[1] == '-c':
        # Execute code from command line
        code = ' '.join(sys.argv[2:])
        result = vm.execute(code)
        if result is not None:
            print(f"Result: {result}")
    else:
        # Execute code from file
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                code = f.read()

            # Remove comments (lines starting with #)
            lines = []
            for line in code.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)

            if not lines:
                print("No code to execute")
                sys.exit(0)

            # Execute each line separately
            code = '\n'.join(lines)
            result = vm.execute(code)
            if result is not None:
                print(f"Final stack: {result}")

        except FileNotFoundError:
            print(f"Error: File '{filename}' not found")
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

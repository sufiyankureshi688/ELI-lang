#!/usr/bin/env python3
"""
alpha_p3.py — ELI Frontend
============================

.kw file format:
----------------
KEYWORD <name>       # optional — leading keyword for this feature

SYNTAX               # pattern to match
<pattern tokens>

COMPILATION          # ELI that runs at compile time, emits output tokens
<eli code>

SYNTAX               # multiple syntax/compilation pairs allowed per file
<pattern>

COMPILATION
<eli code>

Pattern tokens:
  WORD     exact match (case-insensitive)
  ?name    capture exactly one token
  *name    capture one or more tokens (stops at next fixed word or newline)

Compile-time opcodes (in addition to all 42 standard ELI opcodes):
  e  — pop string-table ID, emit that token to output stream
  x  — pop count, pop start; emit string_table[start..start+count-1]
  r  — pop integer, emit it as a decimal string token
  n  — push a unique label integer (for generating jump labels)
  q  — pop key, push ct_state[key] or 0  (persistent compile-time state)
  w  — pop key, pop value; ct_state[key] = value

String table calling convention (Python sets before running ELI):
  string_table = [slot0_tok0, slot0_tok1, ..., slot1_tok0, ..., OPCODES...]
  ct_state[-1]  = start of capture slot 0
  ct_state[-2]  = count of capture slot 0
  ct_state[-3]  = start of capture slot 1
  ct_state[-4]  = count of capture slot 1
  ct_state[-50] = hash of first token of slot 0  (for variable identity)
  ct_state[-51] = hash of first token of slot 1
  ct_state[-99] = start of opcode table in string_table

Opcode table (accessible via ct_state[-99] + index):
  Ordered list of all 42 ELI opcode symbols appended after captures.
  e.g. to emit 'T': ct_state[-99] 23 ADD e
  See OPCODE_EMIT_TABLE for full order.

Label convention:
  n pushes a unique integer. Use r to emit it, then wrap in label syntax.
  Python resolve_labels converts [:__L5__] and __L5__ to offsets.
  Helper: to emit label def use r then wrap — or just emit the string directly
  via a known string-table entry.
"""

import sys
import os
import re
from typing import List, Dict, Tuple, Optional

# ─────────────────────────────────────────────
# OPCODE TABLES
# ─────────────────────────────────────────────

OPCODE_TO_NAME = {
    'A':'ADD','s':'SUBTRACTION','M':'MULTIPLY','D':'DIVIDE','X':'MODULO',
    'a':'MAKE_ARRAY','l':'LENGTH','g':'GET_INDEX',
    'E':'EQUAL','G':'GREATER_THAN','L':'LESS_THAN',
    '!':'NOT','&':'AND','|':'OR','^':'XOR','~':'BIT_NOT','<':'SHL','>':'SHR',
    'U':'DUP','W':'SWAP','V':'DROP','Y':'OVER','R':'ROT',
    'T':'STORE','F':'LOAD','@':'POINTER_ADD','#':'POINTER_SUB',
    'B':'READ_BUFFER','S':'SET_BUFFER','$':'CAS','%':'TAS','=':'FENCE',
    'J':'JUMP','Z':'JUMP_ZERO','N':'JUMP_NOT_ZERO',
    'H':'HALT','C':'CALL','Q':'RETURN',
    'P':'PRINT_INT','I':'INPUT_INT','K':'INPUT_CHAR','O':'PRINT_CHAR'
}
NAME_TO_OPCODE = {v: k for k, v in OPCODE_TO_NAME.items()}

# Ordered opcode list — index used with 'e' opcode via ct_state[-99]
OPCODE_EMIT_TABLE = list(OPCODE_TO_NAME.keys())


# ─────────────────────────────────────────────
# LABEL RESOLUTION + NAME MAPPING
# ─────────────────────────────────────────────

def resolve_labels(text):
    tokens = text.split()
    label_pos = {}
    filtered = []
    for t in tokens:
        if t.startswith('[:') and t.endswith(']') and len(t) >= 4:
            label_pos[t[2:-1]] = len(filtered)
        else:
            filtered.append(t)
    out = []
    i = 0
    while i < len(filtered):
        t = filtered[i]
        U = t.upper()
        if i + 1 < len(filtered):
            nxt = filtered[i+1]
            if U in ('JUMP','JZ','JNZ','J','Z','N','CALL','C') and not nxt.lstrip('-').isdigit():
                target = label_pos.get(nxt)
                if target is not None:
                    op = {'JUMP':'J','JZ':'Z','JNZ':'N','CALL':'C'}.get(U, U)
                    offset = target - (len(out) + 1)
                    out.append(str(offset)); out.append(op)
                    i += 2; continue
        out.append(t); i += 1
    return ' '.join(out)


def map_full_names(text):
    RE_WORD = re.compile(r'\b([A-Z][A-Z0-9_]+)\b')
    result = RE_WORD.sub(lambda m: NAME_TO_OPCODE.get(m.group(1), m.group(1)), text)
    # Also map lowercase natural keywords to opcodes
    LOWER_ALIASES = {
        'halt': 'H', 'return': 'Q', 'call': 'C',
        'dup': 'U', 'drop': 'V', 'swap': 'W', 'over': 'Y', 'rot': 'R',
    }
    RE_LOWER = re.compile(r'\b(' + '|'.join(LOWER_ALIASES) + r')\b')
    result = RE_LOWER.sub(lambda m: LOWER_ALIASES[m.group(1)], result)
    return result


# ─────────────────────────────────────────────
# COMPILE-TIME ELI VM
# ─────────────────────────────────────────────

class CompileTimeVM:
    def __init__(self, string_table: List[str], ct_state: Dict, debug=False):
        self.stack = []
        self.memory = {}
        self.call_stack = []
        self.pc = 0
        self.program = []
        self.debug = debug
        self.string_table = string_table
        self.ct_state = ct_state
        self.output: List[str] = []

        self.ops = {
            'A': lambda: self._b(lambda a,b: a+b),
            's': lambda: self._b(lambda a,b: a-b),
            'M': lambda: self._b(lambda a,b: a*b),
            'D': lambda: self._b(lambda a,b: a//b if b else False),
            'X': lambda: self._b(lambda a,b: a%b if b else False),
            'a': self._make_array, 'l': self._length, 'g': self._get_index,
            'E': lambda: self._b(lambda a,b: 1 if a==b else 0),
            'G': lambda: self._b(lambda a,b: 1 if a>b else 0),
            'L': lambda: self._b(lambda a,b: 1 if a<b else 0),
            '!': self._not,
            '&': lambda: self._b(lambda a,b: a&b),
            '|': lambda: self._b(lambda a,b: a|b),
            '^': lambda: self._b(lambda a,b: a^b),
            '~': self._bnot,
            '<': lambda: self._b(lambda a,b: a<<b),
            '>': lambda: self._b(lambda a,b: a>>b),
            'U': self._dup, 'W': self._swap, 'V': self._drop,
            'Y': self._over, 'R': self._rot,
            'T': self._store, 'F': self._load,
            '@': lambda: self._b(lambda a,b: a+b),
            '#': lambda: self._b(lambda a,b: a-b),
            'B': self._rbuf, 'S': self._sbuf,
            '$': self._cas, '%': self._tas, '=': lambda: True,
            'J': self._jump, 'Z': self._jz, 'N': self._jnz,
            'H': self._halt, 'C': self._call, 'Q': self._ret,
            'P': self._dbg_int, 'I': self._noop,
            'K': self._noop, 'O': self._dbg_char,
            # compile-time opcodes
            'e': self._emit,
            'x': self._emit_range,
            'r': self._emit_int,
            'n': self._new_label,
            'd': self._emit_label_def,
            'j': self._emit_label_ref,
            'q': self._ct_load,
            'w': self._ct_store,

        }

    def tokenize(self, code: str):
        code = map_full_names(code)
        toks = []
        i, n = 0, len(code)
        while i < n:
            c = code[i]
            if c in ' \t\n\r': i += 1; continue
            if c == '#':
                while i < n and code[i] != '\n': i += 1
                continue
            if c == '-' and i+1 < n and code[i+1].isdigit():
                j = i+1
                while j < n and code[j].isdigit(): j += 1
                toks.append(('LIT', int(code[i:j]))); i = j; continue
            if c.isdigit():
                j = i
                while j < n and code[j].isdigit(): j += 1
                toks.append(('LIT', int(code[i:j]))); i = j; continue
            toks.append(('OP', c)); i += 1
        return toks

    def execute(self, code: str) -> Optional[List[str]]:
        self.stack = []; self.call_stack = []; self.pc = 0; self.output = []
        self.program = self.tokenize(code)
        while self.pc < len(self.program):
            typ, val = self.program[self.pc]
            if self.debug:
                print(f"  CT[{self.pc:3d}] {typ} {val!s:6} stk={self.stack[-4:]}",
                      file=sys.stderr)
            if typ == 'LIT':
                self.stack.append(val); self.pc += 1
            elif typ == 'OP':
                if val not in self.ops:
                    print(f"CT Error: unknown op '{val}' pc={self.pc}", file=sys.stderr)
                    return None
                if self.ops[val]() is False:
                    print(f"CT Error: op '{val}' failed pc={self.pc} stk={self.stack}",
                          file=sys.stderr)
                    return None
                self.pc += 1
        return self.output

    def _b(self, f):
        if len(self.stack)<2: return False
        b=self.stack.pop(); a=self.stack.pop()
        r=f(a,b); 
        if r is False: return False
        self.stack.append(r); return True

    def _make_array(self):
        if not self.stack: return False
        n=self.stack.pop()
        if n<0 or len(self.stack)<n: return False
        items=[self.stack.pop() for _ in range(n)]; items.reverse()
        self.stack.append(items); return True

    def _length(self):
        if not self.stack: return False
        v=self.stack.pop()
        self.stack.append(len(v) if isinstance(v,list) else 0); return True

    def _get_index(self):
        if len(self.stack)<2: return False
        idx=self.stack.pop(); arr=self.stack.pop()
        if not isinstance(arr,list) or not(0<=idx<len(arr)): return False
        self.stack.append(arr[idx]); return True

    def _not(self):
        if not self.stack: return False
        self.stack.append(0 if self.stack.pop() else 1); return True

    def _bnot(self):
        if not self.stack: return False
        self.stack.append(~self.stack.pop()); return True

    def _dup(self):
        if not self.stack: return False
        self.stack.append(self.stack[-1]); return True

    def _swap(self):
        if len(self.stack)<2: return False
        self.stack[-1],self.stack[-2]=self.stack[-2],self.stack[-1]; return True

    def _drop(self):
        if not self.stack: return False
        self.stack.pop(); return True

    def _over(self):
        if len(self.stack)<2: return False
        self.stack.append(self.stack[-2]); return True

    def _rot(self):
        if len(self.stack)<3: return False
        c=self.stack.pop(); b=self.stack.pop(); a=self.stack.pop()
        self.stack.extend([b,c,a]); return True

    def _store(self):
        if len(self.stack)<2: return False
        addr=self.stack.pop(); val=self.stack.pop()
        self.memory[addr]=val; return True

    def _load(self):
        if not self.stack: return False
        self.stack.append(self.memory.get(self.stack.pop(),0)); return True

    def _rbuf(self):
        if not self.stack: return False
        addr=self.stack.pop(); result=[]
        i=addr
        while self.memory.get(i,0): result.append(self.memory[i]); i+=1
        self.stack.append(result); return True

    def _sbuf(self):
        if len(self.stack)<2: return False
        addr=self.stack.pop(); arr=self.stack.pop()
        if not isinstance(arr,list): return False
        for i,v in enumerate(arr): self.memory[addr+i]=v
        self.memory[addr+len(arr)]=0; return True

    def _cas(self):
        if len(self.stack)<3: return False
        addr=self.stack.pop(); old=self.stack.pop(); new=self.stack.pop()
        if self.memory.get(addr,0)==old: self.memory[addr]=new; self.stack.append(1)
        else: self.stack.append(0)
        return True

    def _tas(self):
        if not self.stack: return False
        addr=self.stack.pop()
        self.stack.append(self.memory.get(addr,0))
        self.memory[addr]=1; return True

    def _jump(self):
        if not self.stack: return False
        self.pc+=self.stack.pop()-1; return True

    def _jz(self):
        if len(self.stack)<2: return False
        off=self.stack.pop(); val=self.stack.pop()
        if val==0: self.pc+=off-1
        return True

    def _jnz(self):
        if len(self.stack)<2: return False
        off=self.stack.pop(); val=self.stack.pop()
        if val!=0: self.pc+=off-1
        return True

    def _halt(self): self.pc=len(self.program); return True

    def _call(self):
        if not self.stack: return False
        if len(self.call_stack)>=1000: return False
        off=self.stack.pop()
        self.call_stack.append((self.pc+1, len(self.stack)))
        self.pc+=off-1; return True

    def _ret(self):
        if not self.call_stack or not self.stack: return False
        rv=self.stack.pop(); ra,ps=self.call_stack.pop()
        self.stack=self.stack[:ps]; self.stack.append(rv)
        self.pc=ra-1; return True

    def _dbg_int(self):
        if not self.stack: return False
        print(f"[CT] {self.stack.pop()}", file=sys.stderr); return True

    def _dbg_char(self):
        if not self.stack: return False
        print(chr(self.stack.pop()), end='', file=sys.stderr); return True

    def _noop(self): return True

    # ── compile-time opcodes ──

    def _emit(self):
        if not self.stack: return False
        idx = self.stack.pop()
        if not (0 <= idx < len(self.string_table)): return False
        self.output.append(self.string_table[idx])
        return True

    def _emit_range(self):
        if len(self.stack) < 2: return False
        count = self.stack.pop(); start = self.stack.pop()
        for i in range(count):
            idx = start + i
            if not (0 <= idx < len(self.string_table)): return False
            self.output.append(self.string_table[idx])
        return True

    def _emit_int(self):
        if not self.stack: return False
        self.output.append(str(self.stack.pop()))
        return True

    def _new_label(self):
        count = self.ct_state.get(-99999, 0) + 1
        self.ct_state[-99999] = count
        self.stack.append(count)
        return True

    def _emit_label_def(self):
        """d — pop label int, emit [:__Ln__] as single token"""
        if not self.stack: return False
        self.output.append(f'[:__L{self.stack.pop()}__]')
        return True

    def _emit_label_ref(self):
        """j — pop label int, emit __Ln__ as single token"""
        if not self.stack: return False
        self.output.append(f'__L{self.stack.pop()}__')
        return True

    def _ct_load(self):
        if not self.stack: return False
        k = self.stack.pop()
        self.stack.append(self.ct_state.get(k, 0))
        return True

    def _ct_store(self):
        if len(self.stack) < 2: return False
        k = self.stack.pop(); v = self.stack.pop()
        self.ct_state[k] = v
        return True




# ─────────────────────────────────────────────
# .kw FILE LOADER
# ─────────────────────────────────────────────

class KWVariant:
    def __init__(self, pattern: List[str], compilation: str):
        self.pattern = pattern
        self.compilation = compilation


class KWFeature:
    def __init__(self, name: str, keyword: Optional[str], variants: List[KWVariant]):
        self.name = name
        self.keyword = keyword
        self.variants = variants


def load_keywords(keywords_dir: str) -> List[KWFeature]:
    features = []
    if not os.path.exists(keywords_dir): return features
    for fname in sorted(os.listdir(keywords_dir)):
        if not fname.endswith('.kw'): continue
        f = _parse_kw(os.path.join(keywords_dir, fname))
        if f: features.append(f)
    return features


def _parse_kw(path: str) -> Optional[KWFeature]:
    name = os.path.basename(path)[:-3]
    lines = open(path).read().splitlines()

    keyword = None
    variants = []
    current_pattern = None
    current_eli = []
    section = None

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#'): continue
        U = line.upper()

        if U.startswith('KEYWORD'):
            parts = line.split()
            keyword = parts[1] if len(parts) > 1 else None
            continue

        if U == 'SYNTAX':
            if current_pattern is not None:
                variants.append(KWVariant(current_pattern, '\n'.join(current_eli)))
            current_pattern = None
            current_eli = []
            section = 'syntax'
            continue

        if U == 'COMPILATION':
            section = 'compilation'
            continue

        if section == 'syntax' and current_pattern is None:
            current_pattern = line.split()
            continue

        if section == 'compilation':
            part = line.split('#')[0].strip()
            if part: current_eli.append(part)

    if current_pattern is not None:
        variants.append(KWVariant(current_pattern, '\n'.join(current_eli)))

    if not variants:
        print(f"Warning: '{name}' has no SYNTAX sections", file=sys.stderr)
        return None

    return KWFeature(name, keyword, variants)


# ─────────────────────────────────────────────
# PATTERN MATCHING
# ─────────────────────────────────────────────

def match_pattern(pattern: List[str], tokens: List[str], pos: int
                  ) -> Optional[Tuple[Dict, int]]:
    captures = {}
    i, p = pos, 0
    while p < len(pattern):
        pt = pattern[p]
        if pt.startswith('?'):
            if i >= len(tokens) or tokens[i] == '\\n': return None
            captures[pt[1:]] = [tokens[i]]; i += 1; p += 1
        elif pt.startswith('**'):
            # multi-line capture — crosses newlines, KEEPS them for inner patterns
            stopper = None
            for pp in range(p+1, len(pattern)):
                if not pattern[pp][0] in '?*':
                    stopper = pattern[pp].upper(); break
            captured = []
            while i < len(tokens):
                if stopper and tokens[i].upper() == stopper: break
                captured.append(tokens[i])
                i += 1
            # strip leading/trailing newlines
            while captured and captured[0] == '\\n': captured.pop(0)
            while captured and captured[-1] == '\\n': captured.pop()
            if not captured: return None
            captures[pt[2:]] = captured; p += 1
        elif pt.startswith('*'):
            stopper = None
            for pp in range(p+1, len(pattern)):
                if not pattern[pp][0] in '?*':
                    stopper = pattern[pp].upper(); break
            captured = []
            while i < len(tokens):
                if tokens[i] == '\\n': break
                if stopper and tokens[i].upper() == stopper: break
                captured.append(tokens[i]); i += 1
            if not captured: return None
            captures[pt[1:]] = captured; p += 1
        else:
            while i < len(tokens) and tokens[i] == '\\n': i += 1
            if i >= len(tokens): return None
            if tokens[i].upper() != pt.upper(): return None
            i += 1; p += 1
    return captures, i


# ─────────────────────────────────────────────
# SOURCE TOKENIZER
# ─────────────────────────────────────────────

def tokenize_source(text: str) -> List[str]:
    tokens = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r': i += 1; continue
        if c == '\n':
            if tokens and tokens[-1] != '\\n':
                tokens.append('\\n')
            i += 1; continue
        if c == '#':
            while i < n and text[i] != '\n': i += 1
            continue
        if c == '"':
            j = i+1
            while j < n and text[j] != '"':
                if text[j] == '\\': j += 1
                j += 1
            j += 1; tokens.append(text[i:j]); i = j; continue
        two = text[i:i+2]
        if two in (':=','+=','-=','*=','->','==','!=','<=','>=','&&','||','++','--','|>'):
            tokens.append(two); i += 2; continue
        if c.isdigit() or (c=='-' and i+1<n and text[i+1].isdigit() and (not tokens or tokens[-1] in ('=',':','(','\\n'))):
            pass  # fall through to number handler below
        elif c in '=(),.;:{}[]<>!&|^~+-*/%@':
            tokens.append(c); i += 1; continue
        if c.isdigit() or (c=='-' and i+1<n and text[i+1].isdigit()):
            j = i+(1 if c=='-' else 0)
            while j < n and text[j].isdigit(): j += 1
            tokens.append(text[i:j]); i = j; continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j]=='_'): j += 1
            tokens.append(text[i:j]); i = j; continue
        tokens.append(c); i += 1
    return tokens


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

class FrontendError(Exception): pass


def _name_hash(s: str) -> int:
    h = 5381
    for c in s:
        h = ((h * 31) + ord(c)) & 0x7FFFFFFF
    return h % 8999 + 1  # 1..8999, avoids 0


def _build_string_table(captures: Dict, processed: Dict) -> Tuple[List[str], Dict]:
    """Build string table from processed captures + opcode table. Returns (table, updated_ct_state_fragment)."""
    string_table: List[str] = []
    ct_updates = {}
    cap_list = list(captures.items())
    for slot, (cname, _) in enumerate(cap_list):
        ptoks = processed[cname]
        start = len(string_table)
        string_table.extend(ptoks)
        ct_updates[-(slot*2+1)] = start
        ct_updates[-(slot*2+2)] = len(ptoks)
        if ptoks:
            ct_updates[-(50+slot)] = _name_hash(ptoks[0])
    opcode_base = len(string_table)
    string_table.extend(OPCODE_EMIT_TABLE)
    ct_updates[-99] = opcode_base
    return string_table, ct_updates


def _expand_natural_syntax(tokens: List[str]) -> List[str]:
    """
    Expand natural syntax sugar into primitive forms before feature matching.
    This runs repeatedly until no changes occur (fixed-point).

    Rules (in priority order):
      x ++           ->  x = @ x 1 A
      x --           ->  x = @ x 1 s
      x += expr      ->  x = @ x expr A
      x -= expr      ->  x = @ x expr s
      x *= expr      ->  x = @ x expr M
      x /= expr      ->  x = @ x expr D
      not expr       ->  expr !
      for ?v from *start to *end : **body endfor
                     ->  ?v = *start \n while @ ?v *end L : **body \n ?v = @ ?v 1 A \n endwhile
    """
    out = []
    i = 0
    n = len(tokens)
    changed = False

    while i < n:
        t = tokens[i]

        # x ++  or  x --
        if i + 1 < n and tokens[i+1] in ('++', '--') and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', t):
            op = 'A' if tokens[i+1] == '++' else 's'
            out += [t, '=', '@', t, '1', op]
            i += 2; changed = True; continue

        # x += expr  (collect expr until newline)
        AUG = {'+=': 'A', '-=': 's', '*=': 'M', '/=': 'D'}
        if i + 2 < n and tokens[i+1] in AUG and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', t):
            op = AUG[tokens[i+1]]
            j = i + 2
            expr = []
            while j < n and tokens[j] != '\\n':
                expr.append(tokens[j]); j += 1
            out += [t, '=', '@', t] + expr + [op]
            i = j; changed = True; continue

        # not expr  (collect until newline)
        if t.lower() == 'not':
            j = i + 1
            expr = []
            while j < n and tokens[j] != '\\n':
                expr.append(tokens[j]); j += 1
            out += expr + ['!']
            i = j; changed = True; continue

        # for ?v from *start to *end : **body endfor
        if t.lower() == 'for' and i + 1 < n:
            # find 'from', 'to', ':', 'endfor'
            try:
                vi = i + 1
                var = tokens[vi]
                if tokens[vi+1].lower() != 'from': raise ValueError
                # collect start tokens until 'to'
                j = vi + 2
                start = []
                while j < n and tokens[j].lower() != 'to':
                    start.append(tokens[j]); j += 1
                j += 1  # skip 'to'
                end = []
                while j < n and tokens[j] != ':':
                    end.append(tokens[j]); j += 1
                j += 1  # skip ':'
                # collect body until 'endfor'
                depth = 0
                body = []
                while j < n:
                    if tokens[j].lower() == 'for': depth += 1
                    if tokens[j].lower() == 'endfor':
                        if depth == 0: break
                        depth -= 1
                    body.append(tokens[j]); j += 1
                j += 1  # skip 'endfor'
                # expand: var=start \n while @ var end L : body \n var = @ var 1 A \n endwhile
                out += [var, '='] + start + ['\\n',
                        'while', '@', var] + end + ['L', ':'] + body + ['\\n',
                        var, '=', '@', var, '1', 'A', '\\n',
                        'endwhile']
                i = j; changed = True; continue
            except (ValueError, IndexError):
                pass

        out.append(t); i += 1

    return out, changed


def _process_tokens(tokens: List[str], features: List[KWFeature],
                    ct_state: Dict, debug: bool) -> List[str]:
    output = []
    i = 0
    while i < len(tokens):
        if tokens[i] == '\\n': i += 1; continue

        matched = False
        for feat in features:
            if not isinstance(tokens[i], str):
                raise FrontendError(f"Non-string token at position {i}: {repr(tokens[i])}, prev: {tokens[max(0,i-3):i]}")
            if feat.keyword and tokens[i].upper() != feat.keyword.upper():
                continue

            for variant in feat.variants:
                result = match_pattern(variant.pattern, tokens, i)
                if result is None: continue

                captures, new_i = result

                if debug:
                    print(f"[p3] '{feat.name}' matched: { {k:v for k,v in captures.items()} }",
                          file=sys.stderr)

                # Pre-allocate any ?name single-token captures that look like variable names
                # This ensures variables are allocated before recursive body processing
                for cname, ctoks in captures.items():
                    if len(ctoks) == 1 and re.match(r'^[a-z_][a-zA-Z0-9_]*$', ctoks[0]):
                        key = 10000 + _name_hash(ctoks[0])
                        if ct_state.get(key, 0) == 0:
                            addr = max(ct_state.get(9999, 0), 1)
                            ct_state[9999] = addr + 1
                            ct_state[key] = addr

                # Recursively process captures through feature pipeline
                processed = {}
                for cname, ctoks in captures.items():
                    # Always process - keywords like 'halt' need pipeline even if single token
                    sub = _process_tokens(ctoks, features, ct_state, debug)
                    processed[cname] = sub if sub != ctoks else ctoks

                # Build string table
                string_table, ct_updates = _build_string_table(captures, processed)
                ct_state.update(ct_updates)

                # Run compilation
                emitted = []
                if variant.compilation.strip():
                    comp = variant.compilation
                    # High-level mode: if compilation contains capture refs (?x or *x)
                    # substitute them and run through the feature pipeline
                    has_capture_ref = any(
                        f'?{c}' in comp or f'*{c}' in comp or f'**{c}' in comp
                        for c in captures
                    )
                    if has_capture_ref:
                        # Substitute captures into compilation text
                        for cname, ctoks in processed.items():
                            comp = comp.replace(f'**{cname}', '\n'.join(ctoks))
                            comp = comp.replace(f'*{cname}', ' '.join(ctoks))
                            comp = comp.replace(f'?{cname}', ctoks[0] if ctoks else '')
                        # Run through feature pipeline
                        comp_tokens = tokenize_source(comp)
                        comp_out = _process_tokens(comp_tokens, features, ct_state, debug)
                        emitted = [t for t in comp_out if t != '\\n']
                    else:
                        # Raw ELI mode
                        vm = CompileTimeVM(string_table, ct_state, debug=debug)
                        emitted = vm.execute(comp)
                        if emitted is None:
                            raise FrontendError(
                                f"Compilation ELI failed in '{feat.name}' near token {i}"
                            )

                if debug:
                    print(f"[p3] '{feat.name}' emitted: {emitted}", file=sys.stderr)

                output.extend(emitted)
                for _dbg_t in emitted:
                    if not isinstance(_dbg_t, str):
                        raise FrontendError(f"Non-string token {repr(_dbg_t)} emitted by '{feat.name}'")
                i = new_i
                matched = True
                break

            if matched: break

        if not matched:
            output.append(tokens[i]); i += 1

    return output


def preprocess(source: str, keywords_dir: str = None, debug: bool = False) -> str:
    if keywords_dir is None:
        here = os.path.dirname(os.path.abspath(__file__))
        keywords_dir = os.path.join(here, 'library', 'keywords')

    features = load_keywords(keywords_dir)
    if debug:
        print(f"[p3] Loaded: {[f.name for f in features]}", file=sys.stderr)

    tokens = tokenize_source(source)
    if debug:
        print(f"[p3] Tokens: {tokens}", file=sys.stderr)

    # Fixed-point natural syntax expansion (runs before feature matching)
    for _ in range(100):
        tokens, changed = _expand_natural_syntax(tokens)
        if not changed:
            break

    if debug:
        print(f"[p3] Expanded: {tokens}", file=sys.stderr)

    ct_state: Dict = {}
    for _ in range(20):
        output = _process_tokens(tokens, features, ct_state, debug)
        if output == tokens: break
        tokens = output

    output = [t for t in output if t != '\\n']
    result = ' '.join(output)
    result = resolve_labels(result)
    result = map_full_names(result)
    return result


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='alpha_p3 — ELI frontend')
    parser.add_argument('source')
    parser.add_argument('-o', '--out')
    parser.add_argument('-l', '--library', help='Keywords directory')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()

    with open(args.source) as f:
        src = f.read()

    try:
        result = preprocess(src, keywords_dir=args.library, debug=args.debug)
    except FrontendError as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)

    if args.out:
        with open(args.out, 'w') as f: f.write(result)
        print(f"Wrote -> {args.out}")
    else:
        print(result)

    if args.run:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from alpha_i2 import ALPHA_2
        vm = ALPHA_2(); vm.execute(result)


if __name__ == '__main__':
    main()

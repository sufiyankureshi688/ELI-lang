#!/usr/bin/env python3
"""
alpha_p3.py — ELI New Frontend
================================

.feat file format:
------------------
MATCH <pattern>         # what tokens to recognize
CONSTRAINT              # python guardrails
<constraint(capture)>
ELI                     # computation only - push results to stack
<eli code>
EMIT                    # output template - python fills this in
<template>

Pattern tokens:
  WORD     exact match
  ?name    capture one token
  *name    capture many tokens until next fixed word or end of line

ELI section:
  - Runs at compile time
  - Has access to captures via ct_state (set by Python before running)
  - Just does math/logic and pushes results onto stack
  - Stack values become named results used in EMIT template

EMIT template:
  - Plain tokens emitted as-is
  - {capturename}   expands to all tokens of that capture
  - {0} {1} {2}    expands to integers left on ELI stack (bottom to top)
  - [:label]        emits a unique label definition
  - [label]         emits a label reference (for jumps)
  - Labels with same name within one feature invocation are the same label.

Example:
  EMIT {expr} {0} T
  means: emit expr tokens, then emit stack[0] as integer, then emit T
"""

import sys
import os
import re
from typing import List, Dict, Tuple, Optional

# ── resolve_labels and map_full_names inlined from alpha_p2 ──

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
    return RE_WORD.sub(lambda m: NAME_TO_OPCODE.get(m.group(1), m.group(1)), text)


# ── Opcode tables (from alpha_p2) ──
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


# ─────────────────────────────────────────────
# COMPILE-TIME ELI VM
# Only does computation. No emit opcodes needed.
# Captures are available via ct_state integer keys.
# ─────────────────────────────────────────────

class CompileTimeVM:
    """
    Runs feature ELI at compile time.
    Feature ELI just pushes results onto the stack.
    Python reads the stack after execution.

    Calling convention (set by Python before running):
      ct_state[-1] = start of capture slot 0 in string_table
      ct_state[-2] = count of capture slot 0
      ct_state[-3] = start of capture slot 1
      ct_state[-4] = count of capture slot 1
      ... etc
      ct_state[-50 - slot] = stable hash of first token of that slot

    Persistent state (survives across invocations):
      Any positive integer key in ct_state.
      Features use these for things like variable address tables.
    """

    def __init__(self, string_table: List[str], ct_state: Dict, debug=False):
        self.stack = []
        self.memory = {}
        self.call_stack = []
        self.pc = 0
        self.tokens = []
        self.debug = debug
        self.string_table = string_table
        self.ct_state = ct_state
        self.max_call_depth = 1000

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
            'P': self._dbg, 'I': self._noop, 'K': self._noop, 'O': self._noop,
            # compile-time only
            'q': self._ct_load,   # pop key -> push ct_state[key] or 0
            'w': self._ct_store,  # pop key, pop val -> ct_state[key]=val
        }

    def tokenize(self, code: str):
        # Translate opcode names first (ADD->A, STORE->T etc.)
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

    def execute(self, code: str) -> Optional[List]:
        self.stack = []; self.call_stack = []; self.pc = 0
        self.tokens = self.tokenize(code)
        while self.pc < len(self.tokens):
            typ, val = self.tokens[self.pc]
            if self.debug:
                print(f"  CT[{self.pc:3d}] {typ} {val!s:8} stk={self.stack[-5:]}",
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
        return self.stack

    def _b(self, f):
        if len(self.stack) < 2: return False
        b=self.stack.pop(); a=self.stack.pop()
        r=f(a,b)
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
        v=self.stack.pop(); self.stack.append(len(v) if isinstance(v,list) else 0); return True

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
        addr=self.stack.pop(); r=[]
        i=addr
        while self.memory.get(i,0): r.append(self.memory[i]); i+=1
        self.stack.append(r); return True

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

    def _halt(self): self.pc=len(self.tokens); return True

    def _call(self):
        if not self.stack: return False
        if len(self.call_stack)>=self.max_call_depth: return False
        off=self.stack.pop()
        self.call_stack.append((self.pc+1,len(self.stack)))
        self.pc+=off-1; return True

    def _ret(self):
        if not self.call_stack or not self.stack: return False
        rv=self.stack.pop(); ra,ps=self.call_stack.pop()
        self.stack=self.stack[:ps]; self.stack.append(rv)
        self.pc=ra-1; return True

    def _dbg(self):
        if not self.stack: return False
        print(f"[CT] {self.stack.pop()}", file=sys.stderr); return True

    def _noop(self): return True

    def _ct_load(self):
        if not self.stack: return False
        k=self.stack.pop(); self.stack.append(self.ct_state.get(k,0)); return True

    def _ct_store(self):
        if len(self.stack)<2: return False
        k=self.stack.pop(); v=self.stack.pop()
        self.ct_state[k]=v; return True


# ─────────────────────────────────────────────
# FEATURE
# ─────────────────────────────────────────────

class Feature:
    def __init__(self, name, pattern, constraints, eli_code, emit_template):
        self.name = name
        self.pattern = pattern           # list of pattern tokens
        self.constraints = constraints   # list of constraint expressions
        self.eli_code = eli_code         # ELI to run at compile time (may be empty)
        self.emit_template = emit_template  # list of template tokens


def load_features(features_dir: str) -> List[Feature]:
    feats = []
    if not os.path.exists(features_dir): return feats
    for fname in sorted(os.listdir(features_dir)):
        if not fname.endswith('.feat'): continue
        f = _parse_feat(os.path.join(features_dir, fname))
        if f: feats.append(f)
    return feats


def _parse_feat(path: str) -> Optional[Feature]:
    name = os.path.basename(path)[:-5]
    lines = open(path).read().splitlines()
    pattern, constraints, eli_lines, emit_lines = [], [], [], []
    section = None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith('#'): continue
        U = line.upper()
        if U.startswith('MATCH '):
            pattern = line[6:].split(); section = 'match'; continue
        if U == 'CONSTRAINT': section = 'constraint'; continue
        if U == 'ELI':        section = 'eli';        continue
        if U == 'EMIT':       section = 'emit';       continue
        if section == 'constraint': constraints.append(line)
        elif section == 'eli':      eli_lines.append(line)
        elif section == 'emit':     emit_lines.append(line)
    if not pattern:
        print(f"Warning: '{name}' missing MATCH", file=sys.stderr); return None
    # Strip inline comments from ELI
    clean = []
    for ln in eli_lines:
        part = ln.split('#')[0].strip()
        if part: clean.append(part)
    # Parse emit template into tokens
    emit_toks = ' '.join(emit_lines).split()
    return Feature(name, pattern, constraints, ' '.join(clean), emit_toks)


# ─────────────────────────────────────────────
# PATTERN MATCHING
# ─────────────────────────────────────────────

def match_pattern(pattern, tokens, pos) -> Optional[Tuple[Dict, int]]:
    captures = {}
    i, p = pos, 0
    while p < len(pattern):
        pt = pattern[p]
        if pt.startswith('?'):
            if i >= len(tokens): return None
            captures[pt[1:]] = [tokens[i]]; i += 1; p += 1
        elif pt.startswith('*'):
            stopper = None
            for pp in range(p+1, len(pattern)):
                if not pattern[pp][0] in '?*':
                    stopper = pattern[pp].upper(); break
            captured = []
            while i < len(tokens):
                if tokens[i] == '\\n' and stopper is None: break  # only stop at newline if no keyword stopper
                if stopper and tokens[i].upper() == stopper: break
                captured.append(tokens[i]); i += 1
            if not captured: return None
            captures[pt[1:]] = captured; p += 1
        else:
            if i >= len(tokens): return None
            if tokens[i].upper() != pt.upper(): return None
            i += 1; p += 1
    return captures, i


# ─────────────────────────────────────────────
# CONSTRAINTS
# ─────────────────────────────────────────────

def _is_int(t):   return all(s.lstrip('-').isdigit() for s in t)
def _is_name(t):  return all(re.match(r'^[A-Za-z_]\w*$', s) for s in t)
def _non_empty(t):return len(t) > 0
def _single(t):   return len(t) == 1

CONSTRAINTS = {'is_int':_is_int,'is_name':_is_name,'non_empty':_non_empty,'single':_single}

def check_constraints(constraints, captures) -> Tuple[bool, str]:
    for expr in constraints:
        expr = expr.strip()
        if not expr or expr.startswith('#'): continue
        m = re.match(r'^(\w+)\((\w+)\)$', expr)
        if not m: return False, f"Bad constraint: '{expr}'"
        fn, cap = m.group(1), m.group(2)
        if fn not in CONSTRAINTS: return False, f"Unknown constraint fn: '{fn}'"
        if cap not in captures:   return False, f"Unknown capture: '{cap}'"
        if not CONSTRAINTS[fn](captures[cap]):
            return False, f"{fn}({cap}) failed on {captures[cap]}"
    return True, ""


# ─────────────────────────────────────────────
# EMIT TEMPLATE EXPANDER
# Python expands the EMIT template — no ELI needed for this
# ─────────────────────────────────────────────

_label_counter = 0

def expand_emit(template: List[str], captures: Dict, stack: List,
                label_map: Dict) -> List[str]:
    """
    Expand an EMIT template into a list of output tokens.

    Template tokens:
      {capname}   -> all tokens of that capture
      {0},{1}...  -> integers from ELI stack (bottom to top order)
      [:label]    -> unique label definition  [:__Lx__]
      [label]     -> label reference          __Lx__
      anything    -> literal token
    """
    global _label_counter
    out = []
    for tok in template:
        # {capturename} or {0} {1} etc
        if tok.startswith('{') and tok.endswith('}'):
            inner = tok[1:-1]
            if inner.isdigit():
                idx = int(inner)
                if idx < len(stack):
                    out.append(str(stack[idx]))
            elif inner in captures:
                out.extend(captures[inner])
            continue

        # [:label] — label definition
        if tok.startswith('[:') and tok.endswith(']'):
            lname = tok[2:-1]
            if lname not in label_map:
                _label_counter += 1
                label_map[lname] = _label_counter
            out.append(f'[:__L{label_map[lname]}__]')
            continue

        # [label] — label reference
        if tok.startswith('[') and tok.endswith(']'):
            lname = tok[1:-1]
            if lname not in label_map:
                _label_counter += 1
                label_map[lname] = _label_counter
            out.append(f'__L{label_map[lname]}__')
            continue

        # literal token
        out.append(tok)

    return out


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
        if two in (':=','+=','-=','*=','->','==','!=','<=','>=','&&','||'):
            tokens.append(two); i += 2; continue
        if c in '=(),.;{}[]<>!&|^~+-*/%@':
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
    return sum(ord(c)*(i+1) for i,c in enumerate(s))


def _process_tokens(tokens: List[str], features: List, ct_state: Dict,
                    debug: bool) -> List[str]:
    """Run a token list through the feature pipeline (for recursive capture processing)."""
    output = []
    i = 0
    while i < len(tokens):
        if tokens[i] == '\\n': i += 1; continue
        matched = False
        for feat in features:
            result = match_pattern(feat.pattern, tokens, i)
            if result is None: continue
            captures, new_i = result
            ok, err = check_constraints(feat.constraints, captures)
            if not ok: break  # skip, treat as raw
            cap_list = list(captures.items())
            string_table = []
            for slot, (cname, ctoks) in enumerate(cap_list):
                start = len(string_table); string_table.extend(ctoks)
                ct_state[-(slot*2+1)] = start; ct_state[-(slot*2+2)] = len(ctoks)
                if ctoks: ct_state[-(50+slot)] = _name_hash(ctoks[0])
            stack = []
            if feat.eli_code.strip():
                vm = CompileTimeVM(string_table, ct_state, debug=debug)
                stack = vm.execute(feat.eli_code)
                if stack is None: break
            # Recursively process captures
            processed = {}
            for cname, ctoks in captures.items():
                if len(ctoks) > 1:
                    processed[cname] = _process_tokens(ctoks, features, ct_state, debug)
                else:
                    processed[cname] = ctoks
            label_map = {}
            emitted = expand_emit(feat.emit_template, processed, stack, label_map)
            output.extend(emitted); i = new_i; matched = True; break
        if not matched:
            output.append(tokens[i]); i += 1
    return output


def preprocess(source: str, features_dir: str = None, debug: bool = False) -> str:
    if features_dir is None:
        here = os.path.dirname(os.path.abspath(__file__))
        features_dir = os.path.join(here, 'library', 'features')

    features = load_features(features_dir)
    if debug:
        print(f"[p3] Features: {[f.name for f in features]}", file=sys.stderr)

    tokens = tokenize_source(source)
    if debug:
        print(f"[p3] Tokens: {tokens}", file=sys.stderr)

    ct_state: Dict = {}   # persistent across all feature invocations
    output: List[str] = []
    i = 0

    output = _process_tokens(tokens, features, ct_state, debug)

    # Strip newline sentinels
    output = [t for t in output if t != '\\n']
    result = ' '.join(output)

    # Resolve labels and translate any remaining opcode names
    result = resolve_labels(result)
    result = map_full_names(result)

    return result


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='alpha_p3 — ELI new frontend')
    parser.add_argument('source')
    parser.add_argument('-o', '--out')
    parser.add_argument('-l', '--library')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()

    with open(args.source) as f:
        src = f.read()

    try:
        result = preprocess(src, features_dir=args.library, debug=args.debug)
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

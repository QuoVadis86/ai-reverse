"""
Pure Python bdms JSVMP VM Interpreter.
Loads runtime_full.json and executes VM functions without any browser.
"""

import json, os, hashlib, hmac, base64, math, random, copy
from collections import OrderedDict

DIR = os.path.dirname(__file__)
DATA = os.path.join(DIR, "bdms_vmasm", "runtime_full.json")

with open(DATA) as f:
    RUNTIME = json.load(f)

Z = RUNTIME["Z"]
Z_FUNCS = RUNTIME["z"]
V_DATA = RUNTIME["V"]  # list of {bc, flags, str_refs}

# Build V table: maps function id -> bytecode config
V = {}
for idx, entry in enumerate(V_DATA):
    V[idx] = entry

# ── JS built-in polyfills ──

class JSArray(list):
    """JavaScript-like Array with prototype methods."""
    def push(self, *items):
        super().extend(items)
        return len(self)
    def concat(self, *others):
        result = JSArray(self)
        for o in others:
            if isinstance(o, list):
                result.extend(o)
            else:
                result.append(o)
        return result
    def slice(self, start=0, end=None):
        if end is None: end = len(self)
        return JSArray(super().__getitem__(slice(start, end)))
    def join(self, sep=","):
        return str(sep).join(str(x) for x in self)
    def indexOf(self, val, from_idx=0):
        try: return self.index(val, from_idx)
        except ValueError: return -1
    def map(self, func):
        return JSArray(func(x) for x in self)
    def filter(self, func):
        return JSArray(x for x in self if func(x))
    def forEach(self, func):
        for x in self: func(x)
    def reverse(self):
        super().reverse()
        return self
    def sort(self, key=None):
        super().sort(key=key)
        return self
    def splice(self, start, delete_count=None, *items):
        if delete_count is None: delete_count = len(self) - start
        removed = JSArray(self[start:start+delete_count])
        del self[start:start+delete_count]
        for i, item in enumerate(items):
            self.insert(start + i, item)
        return removed
    @staticmethod
    def isArray(obj):
        return isinstance(obj, (list, JSArray))

class JSString(str):
    """JavaScript-like String with prototype methods."""
    def concat(self, *others):
        return JSString(super().__add__("".join(str(o) for o in others)))
    def slice(self, start=0, end=None):
        if end is None: end = len(self)
        return JSString(super().__getitem__(slice(start, end)))
    def indexOf(self, sub, start=0):
        return super().find(sub, start)
    def replace(self, old, new):
        return JSString(super().replace(old, new))
    def split(self, sep=None, maxsplit=-1):
        if sep is None: return JSArray([self])
        return JSArray(super().split(sep, maxsplit))
    def charCodeAt(self, idx=0):
        if idx < len(self): return ord(self[idx])
        return float('nan')
    def toUpperCase(self):
        return JSString(super().upper())
    def toLowerCase(self):
        return JSString(super().lower())
    def trim(self):
        return JSString(super().strip())
    @staticmethod
    def fromCharCode(*codes):
        return JSString("".join(chr(int(c)) for c in codes))

# ── JS global objects ──

class JSMath:
    @staticmethod
    def random(): return random.random()
    @staticmethod
    def floor(x): return int(math.floor(x))
    @staticmethod
    def ceil(x): return int(math.ceil(x))
    @staticmethod
    def round(x): return int(round(x))
    @staticmethod
    def abs(x): return abs(x)
    @staticmethod
    def max(*args): return max(args)
    @staticmethod
    def min(*args): return min(args)
    @staticmethod
    def pow(x, y): return x ** y
    @staticmethod
    def sqrt(x): return math.sqrt(x)
    @staticmethod
    def sin(x): return math.sin(x)

# ── Crypto (MD5, SHA, AES) ──

class JSCrypto:
    @staticmethod
    def md5(data):
        if isinstance(data, str): data = data.encode('utf-8')
        return hashlib.md5(data).hexdigest()
    @staticmethod
    def sha1(data):
        if isinstance(data, str): data = data.encode('utf-8')
        return hashlib.sha1(data).hexdigest()
    @staticmethod
    def sha256(data):
        if isinstance(data, str): data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()
    @staticmethod
    def hmac_sha1(key, data):
        if isinstance(key, str): key = key.encode('utf-8')
        if isinstance(data, str): data = data.encode('utf-8')
        return hmac.new(key, data, hashlib.sha1).hexdigest()
    @staticmethod
    def hmac_sha256(key, data):
        if isinstance(key, str): key = key.encode('utf-8')
        if isinstance(data, str): data = data.encode('utf-8')
        return hmac.new(key, data, hashlib.sha256).hexdigest()
    @staticmethod
    def btoa(s):
        if isinstance(s, str): s = s.encode('latin-1')
        return base64.b64encode(s).decode()
    @staticmethod
    def atob(s):
        return base64.b64decode(s).decode('latin-1')
    @staticmethod
    def encodeURI(s):
        from urllib.parse import quote
        return quote(s, safe='~@#$&()*!+=:;,.?/')


# ── VM Interpreter ──

def run_func(func_idx, *args, native_registry=None):
    """Execute a VM function."""
    config = Z_FUNCS[func_idx]
    bc = config["bc"]
    flags = config.get("flags", 0)
    
    # VM state
    v = []   # value stack
    p = -1   # stack pointer
    a = 0    # instruction pointer
    s = []   # storage registers
    c = None # this context
    h = []   # call stack (saved state for VM-to-VM calls)
    f = 0    # error flag
    l = None # error value
    
    def push(val):
        nonlocal p
        v.append(val)
        p += 1
    
    def pop():
        nonlocal p
        val = v[p]
        v.pop()
        p -= 1
        return val
    
    # Setup s = [callback, value_stack, ...args]
    # For the top-level call, there's no callback
    s = [None, v] + list(args)
    
    # Quick lookup for common native functions
    # Map string names->(object, method_name) or direct callables
    
    while a < len(bc) and f == 0:
        op = bc[a]
        a += 1
        
        # ── OPCODE DISPATCH (from bdms.js function d()) ──
        
        try:
            if op < 38:
                if op < 19:
                    if op < 9:
                        if op < 4:
                            if op < 2:
                                if op == 0:  # CALL
                                    r = bc[a]; a += 1
                                    args_list = [pop() for _ in range(r)]
                                    args_list.reverse()
                                    fn = pop()
                                    this_ctx = pop()
                                    if callable(fn):
                                        try:
                                            result = fn(*args_list)
                                            push(result)
                                        except Exception as e:
                                            push(None)
                                    else:
                                        f = 3
                                        l = TypeError("not a function")
                                else:  # op 1: <=
                                    b = pop(); av = pop()
                                    push(av <= b)
                            elif op == 2:  # >
                                b = pop(); av = pop()
                                push(av > b)
                            else:  # op 3: FOR_IN
                                x = bc[a]; a += 1
                                obj = pop() or {}
                                keys = [k for k in (obj.keys() if isinstance(obj, dict) else range(len(obj) if hasattr(obj, '__len__') else 0))]
                                if len(s) <= x:
                                    s.extend([None] * (x - len(s) + 1))
                                s[x] = [keys, obj]
                        elif op < 6:
                            if op == 4:  # CHK_DEL (iterate FOR_IN)
                                x = bc[a]; a += 1
                                val = pop()
                                target = pop()
                                keys_info = s[x] if x < len(s) else None
                                if keys_info:
                                    j = next((k for k in keys_info[0] if k in keys_info[1]), None)
                                    if j is not None:
                                        keys_info[0].remove(j)
                                        if isinstance(target, dict):
                                            target[bc[a-2]] = j
                                        push(True)
                                    else:
                                        push(False)
                                else:
                                    push(False)
                            else:  # op 5: LD_STR
                                x = bc[a]; a += 1
                                s_val = Z[x] if x < len(Z) else f"Z[{x}]"
                                push(s_val)
                                push(s_val)
                        elif op == 6:  # !==
                            b = pop(); av = pop()
                            push(av is not b if type(av) is type(b) else av != b)
                        elif op == 7:  # NEW_OBJ
                            push({})
                        else:  # op 8: PROP_GET
                            key = pop(); obj = pop()
                            if obj is None:
                                push(None)
                            elif isinstance(obj, dict):
                                push(obj.get(key, None))
                            elif isinstance(obj, (list, tuple)):
                                try: idx = int(key); push(obj[idx] if 0 <= idx < len(obj) else None)
                                except: push(None)
                            elif hasattr(obj, key):
                                push(getattr(obj, key))
                            else:
                                push(None)
                    elif op < 14:
                        if op < 11:
                            if op == 9: push(True)
                            else: push(None)  # op 10: UNDEF
                        elif op == 11:  # MOD
                            b = pop(); av = pop(); push(av % b)
                        elif op == 12:  # AND
                            b = pop(); av = pop(); push(av & b)
                        else:  # op 13: INSTOF
                            cls = pop(); obj = pop()
                            push(isinstance(obj, cls) if isinstance(cls, type) else isinstance(obj, cls) if hasattr(cls, '__instancecheck__') else False)
                    elif op < 16:
                        if op == 14:  # PROP_SET
                            val = pop(); key = pop(); obj = pop()
                            if isinstance(obj, dict): obj[key] = val
                        else:  # op 15: GLOB_SET
                            x = bc[a]; a += 1
                            val = pop()
                            name = Z[x] if x < len(Z) else f"Z[{x}]"
                            globals()[name] = val
                    elif op == 16:  # PROP_DEL
                        key = pop(); obj = pop()
                        if isinstance(obj, dict) and key in obj:
                            del obj[key]; push(True)
                        else: push(False)
                    else:  # op 17: CJMP
                        U = bc[a]; a += 1
                        if pop(): a += U
                elif op < 28:
                    if op < 23:
                        if op < 21:
                            if op == 19:  # >>>
                                b = pop(); av = pop()
                                push((av & 0xFFFFFFFF) >> (b & 31) if av is not None else 0)
                            else:  # op 20
                                x = bc[a]; a += 1
                                val = pop(); obj = pop()
                                name = Z[x] if x < len(Z) else f"Z[{x}]"
                                if isinstance(obj, dict): obj[name] = val
                        elif op == 21:  # SUB
                            b = pop(); av = pop(); push(av - b)
                        else:  # op 22: check error
                            if f != 0: break
                    elif op < 25:
                        if op == 23:  # CJMP_EQ
                            U = bc[a]; a += 1
                            b = pop(); av = pop()
                            if av == b: a += U
                        else:  # op 24: TYPEOF
                            val = pop()
                            tmap = {type(None): 'undefined', bool: 'boolean', int: 'number', float: 'number', str: 'string', list: 'object', dict: 'object', tuple: 'object'}
                            push(tmap.get(type(val), type(val).__name__))
                    elif op == 25:
                        pass
                    elif op == 26:  # POP
                        pop()
                    else:
                        pass
                elif op < 33:
                    if op < 30:
                        if op == 28: push(float('nan'))
                        else: push(not pop())  # op 29: NOT
                    elif op == 30: pass
                    elif op == 31:  # JMP
                        a += bc[a]; a += 1
                    else: pass
                elif op < 35:
                    if op == 33: push(None)  # PUSH_VOID
                    else: pass
                elif op == 35: pass
                elif op == 36: push(+pop())  # UPLUS
                else: push(~pop())  # op 37: BIT_NOT
                
            elif op < 57:
                if op < 47:
                    if op < 42:
                        if op < 40:
                            if op == 38:  # PUSH_CONST
                                push(bc[a]); a += 1
                            else:  # op 39: DUP/ROT
                                F = bc[a]; a += 1
                                if F > 0:
                                    slice_vals = v[p-F+1:p+1]
                                    v[p+1:p+1] = slice_vals
                                    p += F
                        elif op == 40:  # PRE_INC
                            key = pop(); obj = pop()
                            if isinstance(obj, dict):
                                old = obj.get(key, 0)
                                if not isinstance(old, (int, float)): old = 0
                                obj[key] = old + 1
                                push(old + 1)
                            else: push(None)
                        else:  # op 41: CJMP_FALSE
                            U = bc[a]; a += 1
                            if not pop(): a += U
                    elif op < 44:
                        if op == 42:  # DIV
                            b = pop(); av = pop()
                            push(av / b if b != 0 else float('inf'))
                        else: push(-pop())  # op 43: NEG
                    elif op == 44:  # PRE_DEC
                        key = pop(); obj = pop()
                        if isinstance(obj, dict):
                            old = obj.get(key, 0)
                            if not isinstance(old, (int, float)): old = 0
                            obj[key] = old - 1
                            push(old - 1)
                        else: push(None)
                    else:  # op 45: MUL
                        b = pop(); av = pop(); push(av * b)
                elif op < 57:
                    if op == 46: pass
                    elif op == 47:  # DEFINE_PROPERTY
                        x = bc[a]; a += 1
                        val = pop()
                        name = Z[x] if x < len(Z) else f"Z[{x}]"
                        if p >= 0 and isinstance(v[p], dict):
                            v[p][name] = val
                    elif op == 50:  # POST_INC
                        key = pop(); obj = pop()
                        if isinstance(obj, dict):
                            old = obj.get(key, 0)
                            if not isinstance(old, (int, float)): old = 0
                            obj[key] = old + 1
                            push(old)
                        else: push(None)
                    elif op == 52:  # THROW/ERROR
                        f = 1; l = bc[a]; a += 1
                    elif op == 55:  # IN
                        obj = pop(); key = pop()
                        if isinstance(obj, dict): push(key in obj)
                        elif hasattr(obj, '__contains__'): push(key in obj)
                        else: push(False)
                    else: pass
                    
            elif op < 75:
                # ops 57-74
                if op == 57:  # ===
                    b = pop(); av = pop(); push(av is b if type(av) is type(b) else av == b)
                elif op == 60:  # GLOBAL_DEFINE_CHECK
                    x = bc[a]; a += 1
                    val = pop()
                    name = Z[x] if x < len(Z) else f"Z[{x}]"
                    globals()[name] = val
                elif op == 62:  # !=
                    b = pop(); av = pop(); push(av != b)
                elif op == 65:  # POST_DEC
                    key = pop(); obj = pop()
                    if isinstance(obj, dict):
                        old = obj.get(key, 0)
                        obj[key] = old - 1
                        push(old)
                    else: push(None)
                elif op == 67:  # DEFINE_PROPERTY
                    x = bc[a]; a += 1
                    val = pop()
                    name = Z[x] if x < len(Z) else f"Z[{x}]"
                    if p >= 0 and isinstance(v[p], dict):
                        v[p][name] = val
                elif op == 70:  # XOR
                    b = pop(); av = pop()
                    push(av ^ b if isinstance(av, int) and isinstance(b, int) else av)
                elif op == 72:  # GLOBAL_INIT
                    x = bc[a]; a += 1
                    val = pop()
                    name = Z[x] if x < len(Z) else f"Z[{x}]"
                    if name not in globals():
                        globals()[name] = val
                else:
                    # REGISTER_GET: walk into s
                    N = bc[a]; a += 1
                    x_reg = bc[a]; a += 1
                    U = s
                    for _ in range(N):
                        if isinstance(U, list) and len(U) > 0:
                            U = U[0]
                        else:
                            U = None
                            break
                    if isinstance(U, (list, tuple)) and x_reg < len(U):
                        push(U[x_reg])
                    elif isinstance(U, dict):
                        push(U.get(x_reg, None))
                    else:
                        push(None)
            elif op == 75:  # PUSH_NULL
                push(None)
            else:
                # op >= 76: unknown, skip
                pass
                
        except Exception as e:
            if f == 0:
                f = 3
                l = str(e)
    
    if f != 0:
        raise RuntimeError(f"VM error at ip={a}: {l}")
    
    return pop() if p >= 0 else None


# ── Register V functions and run ──

def make_vm_func(func_idx):
    """Create a callable that executes VM function func_idx."""
    def vm_func(*args):
        return run_func(func_idx, *args)
    return vm_func

# Register all V entries as callables in the V dict
for idx in range(len(V_DATA)):
    V[idx] = V_DATA[idx]
    # Also register the wrapper
    fn_name = f"_vm_func_{idx}"
    globals()[fn_name] = make_vm_func(idx)

if __name__ == "__main__":
    print(f"Loaded V={len(V)}, z={len(Z_FUNCS)}, Z={len(Z)}")
    
    # Test: run func_0
    try:
        result = run_func(0)
        print(f"func_0 result: {result}")
    except Exception as e:
        print(f"func_0 error: {e}")
        import traceback
        traceback.print_exc()

const fs = require('fs');
const crypto = require('crypto');

// Load captured data
const DATA = JSON.parse(fs.readFileSync(__dirname + '/bdms_vmasm/functions.json'));
const Z = DATA.Z;
const Z_FUNCS = DATA.z;

// VM state
let v = [], p = -1, o, a, s = {}, c = null, i = 0, h = [], f = 0, l = null;
const Z_ = Z; // string table reference

function push(val) { v.push(val); p++; }
function pop() { const val = v[p]; v.pop(); p--; return val; }

// Native function V table (VM-to-VM callable functions)
const V = new Map();
const nativeWrappers = new Map();

function wrapNativeFn(fn, name) {
    // Create a wrapper that the VM can call via CALL opcode
    const wrapper = function(thisArg, ...args) {
        // Some natives expect (this, args...), others just (args...)
        // JS native methods expect this context
        try {
            return fn.apply(thisArg, args);
        } catch(e) {
            // Fallback: call without this
            return fn(...args);
        }
    };
    nativeWrappers.set(name, wrapper);
    return wrapper;
}

// Register common JS built-ins as native functions
const builtins = {
    'String.prototype.concat': (s, ...args) => args.reduce((a,b) => a + String(b), String(s)),
    'String.prototype.slice': (s, start, end) => String(s).slice(start, end),
    'String.prototype.indexOf': (s, search) => String(s).indexOf(search),
    'String.prototype.replace': (s, search, replace) => String(s).replace(search, replace),
    'String.prototype.split': (s, sep) => String(s).split(sep),
    'String.prototype.charCodeAt': (s, i) => String(s).charCodeAt(i),
    'String.fromCharCode': (...codes) => String.fromCharCode(...codes),
    'Array.isArray': (a) => Array.isArray(a),
    'Array.prototype.push': (arr, ...items) => Array.prototype.push.apply(arr, items),
    'Array.prototype.concat': (arr, ...args) => arr.concat(...args),
    'Array.prototype.slice': (arr, start, end) => arr.slice(start, end),
    'Array.prototype.join': (arr, sep) => arr.join(sep),
    'Array.prototype.indexOf': (arr, val) => arr.indexOf(val),
    'Array.prototype.map': (arr, fn) => arr.map(fn),
    'Array.prototype.filter': (arr, fn) => arr.filter(fn),
    'Array.prototype.forEach': (arr, fn) => arr.forEach(fn),
    'Object.keys': (obj) => Object.keys(obj),
    'Object.assign': (target, ...sources) => Object.assign(target, ...sources),
    'JSON.stringify': (val) => JSON.stringify(val),
    'JSON.parse': (str) => JSON.parse(str),
    'Math.random': () => Math.random(),
    'Math.floor': (x) => Math.floor(x),
    'Math.ceil': (x) => Math.ceil(x),
    'Math.abs': (x) => Math.abs(x),
    'Math.max': (...args) => Math.max(...args),
    'Math.min': (...args) => Math.min(...args),
    'encodeURIComponent': (s) => encodeURIComponent(s),
    'decodeURIComponent': (s) => decodeURIComponent(s),
    'btoa': (s) => Buffer.from(s, 'binary').toString('base64'),
    'atob': (s) => Buffer.from(s, 'base64').toString('binary'),
    'setTimeout': (fn, ms) => { if (typeof fn === 'function') fn(); return 0; },
    'clearTimeout': () => {},
    'console.log': (...args) => {},
    'performance.now': () => Date.now(),
    'Date.now': () => Date.now(),
    'Date.prototype.getTime': (d) => new Date(d).getTime(),
};

// MD5, SHA, AES via Node.js crypto
const cryptoFns = {
    'md5': (data) => crypto.createHash('md5').update(String(data)).digest('hex'),
    'sha1': (data) => crypto.createHash('sha1').update(String(data)).digest('hex'),
    'sha256': (data) => crypto.createHash('sha256').update(String(data)).digest('hex'),
    'base64encode': (data) => Buffer.from(String(data)).toString('base64'),
    'base64decode': (data) => Buffer.from(data, 'base64').toString(),
};

// Run a VM function
function runFunc(funcIdx, ...args) {
    const config = Z_FUNCS[funcIdx];
    const bc = config.bc;
    i = config.fl || 0;
    o = bc;
    a = 0;
    v = []; p = -1;
    s = {};
    c = null;
    h = [];
    f = 0; l = null;
    
    // Push arguments onto stack
    for (const arg of args) push(arg);
    
    while (a < o.length && f === 0) {
        const op = o[a++];
        
        // Dispatch: mirrors the JSVMP dispatch from bdms.js
        // The dispatch is structured in numeric ranges
        
        if (op < 38) {
            if (op < 19) {
                if (op < 9) {
                    if (op < 4) {
                        if (op < 2) {
                            if (op === 0) { // CALL
                                const r = o[a++];
                                const argsList = [];
                                for (let i = 0; i < r; i++) argsList.unshift(pop());
                                const fn = pop();
                                const thisCtx = pop();
                                if (typeof fn === 'function') {
                                    try {
                                        push(fn.apply(thisCtx, argsList));
                                    } catch(e) {
                                        push(undefined);
                                    }
                                } else {
                                    f = 3; l = new TypeError('Not a function');
                                }
                            } else { // op 1: <=
                                const b = pop(), a_ = pop();
                                push(a_ <= b);
                            }
                        } else if (op === 2) { // >
                            const b = pop(), a_ = pop();
                            push(a_ > b);
                        } else { // op 3: FOR_IN
                            const x = o[a++];
                            const obj = pop();
                            const keys = Object.keys(obj || {});
                            s[x] = [keys, obj];
                        }
                    } else if (op < 6) {
                        if (op === 4) { // CHK_DEL (delete check)
                            const x = o[a++];
                            const val = pop();
                            const target = pop();
                            const ki = s[x];
                            let j = undefined;
                            for (const k of ki[0]) {
                                if (k in ki[1]) { j = k; break; }
                            }
                            if (j !== undefined) {
                                ki[0].shift();
                                target[o[a-2]] = j;
                                push(true);
                            } else push(false);
                        } else { // op 5: LD_STR
                            const x = o[a++];
                            const str = Z[x] !== undefined ? Z[x] : `Z[${x}]`;
                            push(str);
                            push(str);
                        }
                    } else if (op === 6) { // !==
                        const b = pop(), a_ = pop();
                        push(a_ !== b);
                    } else if (op === 7) { // NEW_OBJ
                        push({});
                    } else { // op 8: PROP_GET
                        const key = pop(), obj = pop();
                        if (obj && typeof obj === 'object') push(obj[key]);
                        else push(undefined);
                    }
                } else if (op < 14) {
                    if (op < 11) {
                        if (op === 9) push(true); // TRUE
                        else push(undefined); // op 10: UNDEF
                    } else if (op === 11) { const b = pop(), a_ = pop(); push(a_ % b); }
                    else if (op === 12) { const b = pop(), a_ = pop(); push(a_ & b); }
                    else { const c = pop(), obj = pop(); push(obj instanceof c); }
                } else if (op < 16) {
                    if (op === 14) { const v_ = pop(), k_ = pop(), o_ = pop(); if(o_) o_[k_] = v_; }
                    else {
                        const x = o[a++];
                        const val = pop();
                        const name = Z[x] || `Z[${x}]`;
                        globalThis[name] = val;
                    }
                } else if (op === 16) { // PROP_DEL
                    const k = pop(), obj = pop();
                    if (obj) push(delete obj[k]);
                    else push(false);
                } else { // op 17: CJMP
                    const U = o[a++];
                    if (pop()) a += U;
                }
            } else if (op < 28) {
                if (op < 23) {
                    if (op < 21) {
                        if (op === 19) { // >>> 
                            const b = pop(), a_ = pop();
                            push((a_ >>> b) >>> 0);
                        } else { // op 20
                            const x = o[a++];
                            const v_ = pop(), o_ = pop();
                            if (o_) o_[Z[x]] = v_;
                        }
                    } else if (op === 21) { // -
                        const b = pop(), a_ = pop();
                        push(a_ - b);
                    } else { if (f !== 0) break; } // op 22: error check
                } else if (op < 25) {
                    if (op === 23) { // CJMP_EQ
                        const U = o[a++];
                        const b = pop(), a_ = pop();
                        if (a_ === b) a += U;
                    } else { // op 24: TYPEOF
                        const val = pop();
                        push(typeof val);
                    }
                } else if (op === 25) { /* op 25: generator/iterator */ }
                else if (op === 26) pop(); // POP
                else { /* op 27 */ }
            } else if (op < 33) {
                if (op < 30) {
                    if (op === 28) push(NaN); // NaN
                    else push(!pop()); // op 29: NOT
                } else if (op === 30) { /* op 30 */ }
                else if (op === 31) { a += o[a++]; } // JMP
                else { /* op 32 */ }
            } else if (op < 35) {
                if (op === 33) push(undefined); // PUSH_VOID
                else { /* op 34 */ }
            } else if (op === 35) { /* op 35 */ }
            else if (op === 36) push(+pop()); // UPLUS
            else push(~pop()); // op 37: BIT_NOT
        } else if (op < 57) {
            if (op < 47) {
                if (op < 42) {
                    if (op < 40) {
                        if (op === 38) push(o[a++]); // PUSH_CONST
                        else { // op 39: DUP/ROT
                            const F = o[a++];
                            // Copy F elements from below stack top
                            // v[p-F+1..p] = v.slice(p-F+1, p+1) (duplicate)
                            const slice = v.slice(p-F+1, p+1);
                            v.splice(p+1, 0, ...slice);
                            p += F;
                        }
                    } else if (op === 40) { // PRE_INC
                        const k = pop(), obj = pop();
                        if (obj) { const nv = (obj[k] || 0) + 1; obj[k] = nv; push(nv); }
                        else push(NaN);
                    } else { // op 41: CJMP_FALSE
                        const U = o[a++];
                        if (!pop()) a += U;
                    }
                } else if (op < 44) {
                    if (op === 42) { const b = pop(), a_ = pop(); push(a_ / b); }
                    else push(-pop()); // op 43: NEG
                } else if (op === 44) { // PRE_DEC
                    const k = pop(), obj = pop();
                    if (obj) { const nv = (obj[k] || 0) - 1; obj[k] = nv; push(nv); }
                    else push(NaN);
                } else { // op 45: MUL
                    const b = pop(), a_ = pop(); push(a_ * b);
                }
            } else if (op < 57) {
                // ops 46-56
                if (op === 46) { /* op 46 */ }
                else if (op === 47) {
                    // DEFINE_PROPERTY
                    const x = o[a++];
                    const val = pop();
                    Object.defineProperty(v[p], Z[x], { value: val, enumerable: true, configurable: true, writable: true });
                }
                else if (op === 48 || op === 49) { /* skip */ }
                else if (op === 50) { // POST_INC
                    const k = pop(), obj = pop();
                    if (obj) { const old = obj[k] || 0; obj[k] = old + 1; push(old); }
                    else push(NaN);
                }
                else if (op === 51) { /* skip */ }
                else if (op === 52) { // ERROR/THROW
                    f = 1;
                    l = o[a++]; // jump target
                }
                else if (op === 53 || op === 54) { /* skip */ }
                else if (op === 55) { // IN
                    const obj = pop(), key = pop();
                    push(key in (obj || {}));
                }
                else if (op === 56) { /* skip */ }
            }
        } else if (op < 75) {
            // ops 57-74: default = REGISTER_GET
            // Specific opcodes are checked first
            if (op === 57) { // ===
                const b = pop(), a_ = pop();
                push(a_ === b);
            } else if (op === 60) { // GLOBAL_DEFINE_CHECK
                const x = o[a++];
                const name = Z[x] || `Z[${x}]`;
                if (!(name in globalThis)) {
                    throw new ReferenceError(`${name} is not defined`);
                }
                globalThis[name] = pop();
            } else if (op === 62) { // !=
                const b = pop(), a_ = pop();
                push(a_ != b);
            } else if (op === 65) { // POST_DEC
                const k = pop(), obj = pop();
                if (obj) { const old = obj[k] || 0; obj[k] = old - 1; push(old); }
                else push(NaN);
            } else if (op === 67) { // DEFINE_PROPERTY
                const x = o[a++];
                const val = pop();
                if (v[p] !== undefined) {
                    Object.defineProperty(v[p], Z[x], {
                        value: val, writable: true, enumerable: true, configurable: true
                    });
                }
            } else if (op === 70) { // XOR
                const b = pop(), a_ = pop();
                push(a_ ^ b);
            } else if (op === 72) { // GLOBAL_INIT
                const x = o[a++];
                const name = Z[x] || `Z[${x}]`;
                const val = pop();
                if (!(name in globalThis)) globalThis[name] = val;
            } else {
                // REGISTER_GET: walk into s[N][0][0]...[x]
                const N = o[a++], x = o[a++];
                let U = s;
                for (let i = 0; i < N; i++) U = U[0];
                push(U !== undefined ? U[x] : undefined);
            }
        } else if (op === 75) { // PUSH_NULL
            push(null);
        } else {
            // op >= 76: unknown - skip
        }
    }
    
    if (f !== 0) throw l || new Error(`VM error at ${a}`);
    return p >= 0 ? pop() : undefined;
}

// Register all JS builtins as callable functions 
// Build the V table by wrapping native functions
for (const [name, fn] of Object.entries(builtins)) {
    V.set(wrapNativeFn(fn, name), [null, null]);
}
for (const [name, fn] of Object.entries(cryptoFns)) {
    V.set(wrapNativeFn(fn, name), [null, null]);
}

// Export
module.exports = { runFunc, Z, Z_FUNCS, V };

// Test
if (require.main === module) {
    console.log(`Loaded ${Z_FUNCS.length} functions, ${Z.length} strings`);
    try {
        const result = runFunc(0);
        console.log('func_0 result:', result);
    } catch(e) {
        console.error('func_0 error:', e.message);
    }
}

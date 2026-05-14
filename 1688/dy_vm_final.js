/**
 * Node.js bdms VM - pure JS, no browser.
 * Loads final_runtime.json and executes VM functions.
 */
const fs = require('fs');
const DATA = JSON.parse(fs.readFileSync(__dirname + '/bdms_vmasm/final_runtime.json'));

const Z = DATA.Z;
const Z_FUNCS = DATA.z;      // z[funcIdx] = {bc, flags}
const V_ENTRIES = DATA.V;    // V[idx] = {bc, flags}
const D_SEQ = DATA.D_seq;    // init sequence

// Build V table: maps function reference -> bytecode config
// In the browser, D() creates JS functions. We simulate this by
// creating wrapper functions.
const V = new Map();

// Create wrapper functions for all V entries (like D())
for (let idx = 0; idx < V_ENTRIES.length; idx++) {
    const entry = V_ENTRIES[idx];
    // Create a wrapper function that executes these bytecodes
    const wrapper = function() {
        return runVM(entry.bc, entry.flags || 0, arguments);
    };
    V.set(wrapper, [entry.bc, entry.flags || 0]);
}

// Store wrappers in an array indexed by V entry position
const V_WRAPPERS = [];
for (const [fn] of V) V_WRAPPERS.push(fn);

// HR is V entry 245 (init function)
const HR_WRAPPER = V_WRAPPERS[245];

// ── VM Interpreter ──
// Mirrors bdms.js function d() opcode dispatch

function runVM(bc, flags, args) {
    let v = [];          // value stack
    let p = -1;          // stack pointer
    let a = 0;           // instruction pointer
    let s = [null, v];   // storage: [callback, stack, ...args]
    let c = null;        // this context
    let h = [];          // call stack
    let f = 0;           // error flag
    let l = null;        // error value

    // Push arguments
    if (args) {
        for (let i = 0; i < args.length; i++) {
            s.push(args[i]);
        }
    }

    function push(val) { v.push(val); p++; }
    function pop() { const val = v[p]; v.pop(); p--; return val; }

    // Track s[0] usage - in the browser, s[0] is populated
    // with function references from module initialization
    // s[0] = callback, which is set by the caller of X()
    // For modules, s[0] = n (the module exports object)
    // We need to pre-populate s with the module export structure
    
    // Setup: s = [callback, stack, ...args]
    // The callback (s[0]) should be the module exports object
    // In the browser, this is set up by the module system
    // We'll set it to a generic object for now
    if (!s[0]) s[0] = {};
    
    // Module exports reference - used by property access in VM
    // The module system creates this during init
    globalThis.__module_exports = {};

    while (a < bc.length && f === 0) {
        const op = bc[a++];

        try {
            if (op < 38) {
                if (op < 19) {
                    if (op < 9) {
                        if (op < 4) {
                            if (op < 2) {
                                if (op === 0) { // CALL
                                    const r = bc[a++];
                                    const argsList = [];
                                    for (let i = 0; i < r; i++) argsList.unshift(pop());
                                    const fn = pop();
                                    const thisCtx = pop();
                                    if (typeof fn === 'function') {
                                        try { push(fn.apply(thisCtx, argsList)); }
                                        catch(e) { push(undefined); }
                                    } else { f = 3; l = new TypeError('not a function'); }
                                } else { // op 1: <=
                                    const b = pop(), av = pop(); push(av <= b);
                                }
                            } else if (op === 2) { // >
                                const b = pop(), av = pop(); push(av > b);
                            } else { // op 3: FOR_IN
                                const x = bc[a++];
                                const obj = pop() || {};
                                const keys = Object.keys(obj);
                                s[x] = [keys, obj];
                            }
                        } else if (op < 6) {
                            if (op === 4) { // CHK_DEL
                                const x = bc[a++];
                                pop(); pop(); // skip args
                                const ki = s[x];
                                if (ki && ki[0].length > 0) {
                                    const j = ki[0].shift();
                                    push(true);
                                } else push(false);
                            } else { // op 5: LD_STR
                                const x = bc[a++];
                                const str = Z[x] !== undefined ? Z[x] : `Z[${x}]`;
                                push(str); push(str);
                            }
                        } else if (op === 6) { // !==
                            const b = pop(), av = pop(); push(av !== b);
                        } else if (op === 7) { // NEW_OBJ
                            push({});
                        } else { // op 8: PROP_GET
                            const key = pop(), obj = pop();
                            if (obj != null && typeof obj === 'object') push(obj[key]);
                            else push(undefined);
                        }
                    } else if (op < 14) {
                        if (op < 11) {
                            if (op === 9) push(true);
                            else push(undefined);
                        } else if (op === 11) { push(pop() % pop()); }
                        else if (op === 12) { const b = pop(), a_ = pop(); push(a_ & b); }
                        else { const c = pop(); push(pop() instanceof c); }
                    } else if (op < 16) {
                        if (op === 14) { const v_ = pop(), k_ = pop(), o_ = pop(); if(o_) o_[k_] = v_; }
                        else { const x = bc[a++]; globalThis[Z[x]] = pop(); }
                    } else if (op === 16) { // PROP_DEL
                        const k = pop(), obj = pop();
                        push(obj ? delete obj[k] : false);
                    } else { // op 17: CJMP
                        const U = bc[a++];
                        if (pop()) a += U;
                    }
                } else if (op < 28) {
                    if (op < 23) {
                        if (op < 21) {
                            if (op === 19) { // >>>
                                const b = pop(), a_ = pop();
                                push((a_ >>> b) >>> 0);
                            } else { // op 20
                                const x = bc[a++]; const v_ = pop(), o_ = pop();
                                if (o_) o_[Z[x]] = v_;
                            }
                        } else if (op === 21) { push(pop() - pop()); }
                        else { if (f !== 0) break; }
                    } else if (op < 25) {
                        if (op === 23) { const U = bc[a++]; const b = pop(); if (pop() === b) a += U; }
                        else { push(typeof pop()); }
                    } else if (op === 25) {}
                    else if (op === 26) pop();
                    else {}
                } else if (op < 33) {
                    if (op < 30) {
                        if (op === 28) push(NaN);
                        else push(!pop());
                    } else if (op === 30) {}
                    else if (op === 31) { a += bc[a++]; }
                    else {}
                } else if (op < 35) {
                    if (op === 33) push(undefined);
                    else {}
                } else if (op === 35) {}
                else if (op === 36) push(+pop());
                else push(~pop());
            } else if (op < 57) {
                if (op < 47) {
                    if (op < 42) {
                        if (op < 40) {
                            if (op === 38) push(bc[a++]);
                            else { // op 39: DUP/ROT
                                const F = bc[a++];
                                if (F > 0) {
                                    const slice = v.slice(p-F+1, p+1);
                                    v.splice(p+1, 0, ...slice);
                                    p += F;
                                }
                            }
                        } else if (op === 40) { // PRE_INC
                            const k = pop(), obj = pop();
                            if (obj) { const nv = (obj[k]||0) + 1; obj[k]=nv; push(nv); }
                            else push(NaN);
                        } else { // op 41: CJMP_FALSE
                            const U = bc[a++];
                            if (!pop()) a += U;
                        }
                    } else if (op < 44) {
                        if (op === 42) push(pop() / pop());
                        else push(-pop());
                    } else if (op === 44) { // PRE_DEC
                        const k = pop(), obj = pop();
                        if (obj) { const nv = (obj[k]||0)-1; obj[k]=nv; push(nv); }
                        else push(NaN);
                    } else push(pop() * pop());
                } else if (op < 57) {
                    if (op === 46) {} 
                    else if (op === 47) { const x=bc[a++]; const val=pop(); if(v[p]) v[p][Z[x]]=val; }
                    else if (op === 50) { const k=pop(), obj=pop(); if(obj){const o=obj[k]||0;obj[k]=o+1;push(o)}else push(NaN); }
                    else if (op === 52) { f=1; l=bc[a++]; }
                    else if (op === 55) { const obj=pop(); push(pop() in (obj||{})); }
                    else {}
                }
            } else if (op < 75) {
                if (op === 57) { push(pop() === pop()); }
                else if (op === 60) { const x=bc[a++]; globalThis[Z[x]]=pop(); }
                else if (op === 62) { push(pop() != pop()); }
                else if (op === 65) { const k=pop(),obj=pop();if(obj){const o=obj[k]||0;obj[k]=o-1;push(o)}else push(NaN); }
                else if (op === 67) { const x=bc[a++];const val=pop();if(v[p])v[p][Z[x]]=val; }
                else if (op === 70) { const b=pop(),a_=pop();push(a_ ^ b); }
                else if (op === 72) { const x=bc[a++];const name=Z[x];const val=pop();if(!(name in globalThis))globalThis[name]=val; }
                else { // REGISTER_GET
                    const N = bc[a++], xr = bc[a++];
                    let U = s;
                    for (let i = 0; i < N && U; i++) U = U[0];
                    if (U !== undefined && U !== null) push(U[xr]);
                    else push(undefined);
                }
            } else if (op === 75) push(null);
            else {}
        } catch(e) {
            if (f === 0) { f = 3; l = e.message; }
        }
    }

    if (f !== 0) throw l || new Error(`VM error at ${a}`);
    return p >= 0 ? pop() : undefined;
}

// ── Bootstrap: populate callback table ──
globalThis.__module_exports = {};

// Expose V wrappers on the module exports (used by FOR_IN)
for (let i = 0; i < V_WRAPPERS.length && i < 500; i++) {
    __module_exports[`fn_${i}`] = V_WRAPPERS[i];
}

// ── Test ──
console.log(`V=${V.size}, z=${Z_FUNCS.length}, Z=${Z.length}, D_seq=${D_SEQ.length}`);

// Try running the init function (HR)
if (HR_WRAPPER) {
    console.log('\nCalling init (HR wrapper)...');
    try {
        const result = HR_WRAPPER();
        console.log('init result:', typeof result, result ? JSON.stringify(result).slice(0, 200) : 'undefined');
    } catch(e) {
        console.log('init error:', e.message.slice(0, 200));
    }
}

// Try func_0
console.log('\nCalling func_0...');
try {
    const r = runVM(Z_FUNCS[0].bc, Z_FUNCS[0].flags || 0, []);
    console.log('func_0 result:', typeof r, r);
} catch(e) {
    console.log('func_0 error:', e.message.slice(0, 200));
}

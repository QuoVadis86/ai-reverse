import json, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))

OUT = os.path.join(os.path.dirname(__file__), "bdms_vmasm")
os.makedirs(OUT, exist_ok=True)

OPCODES = {
    0: "CALL", 1: "LE", 2: "GT", 3: "FOR_IN", 4: "CHK_DEL",
    5: "LD_STR", 6: "NE", 7: "NEW_OBJ", 8: "PROP_GET", 9: "TRUE",
    10: "UNDEF", 11: "MOD", 12: "AND", 13: "INSTOF", 14: "PROP_SET",
    15: "GLOB_SET", 16: "PROP_DEL", 17: "CJMP", 19: "URSHIFT",
    21: "SUB", 23: "CJMP_EQ", 24: "TYPEOF", 26: "POP", 28: "PUSH_NAN",
    29: "NOT", 31: "JMP", 33: "PUSH_VOID", 36: "UPLUS", 37: "BIT_NOT",
    38: "PUSH_CONST",
}
HAS_OPERAND = {0, 5, 15, 17, 23, 31, 38}


def capture():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context()
        page = ctx.new_page()
        page.add_init_script("""
        window.__z_arr = []; window.__z_n = 0;
        window.__Z_arr = []; window.__Z_n = 0;
        const _p = Array.prototype.push;
        Array.prototype.push = function(...a) {
            const isZ = a.length === 1 && Array.isArray(a[0]) && a[0].length === 4
                        && Array.isArray(a[0][0]) && a[0][0].length > 5;
            if (isZ && window.__z_n < 2000) {
                window.__z_arr[window.__z_n++] = a[0];
            }
            if (a.length === 1 && typeof a[0] === 'string' && a[0].length > 3 && window.__Z_n < 5000) {
                window.__Z_arr[window.__Z_n++] = a[0];
            }
            return _p.apply(this, a);
        };
        """)
        page.goto("https://www.douyin.com/jingxuan", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(18000)

        z_n = page.evaluate("() => window.__z_n")
        Z_n = page.evaluate("() => window.__Z_n")
        print(f"z={z_n} Z={Z_n}")

        z_data = []
        BATCH = 40
        for start in range(0, z_n, BATCH):
            end = min(start + BATCH, z_n)
            batch = page.evaluate(f"""() => {{
                const refs = window.__z_arr;
                const out = [];
                for (let i = {start}; i < {end}; i++) {{
                    const item = refs[i];
                    out.push({{bc: Array.from(item[0]), fl: item[1], u: item[2], qu: item[3]}});
                }}
                return out;
            }}""")
            z_data.extend(batch)
            print(f"  batch [{start}-{end}]")
            time.sleep(0.3)

        Z_list = page.evaluate(f"""() => {{
            const out = [];
            for (let i = 0; i < {Z_n}; i++) out.push(window.__Z_arr[i]);
            return out;
        }}""")

        # Find bdms Z offset: scan for the first meaningful string
        bdms_offset = 0
        for i, s in enumerate(Z_list):
            if s in ('url', 'data', 'headers', 'signature'):
                bdms_offset = i
                break
        # bdms Z strings from offset
        Z_bdms = Z_list[bdms_offset:]
        print(f"bdms Z offset={bdms_offset}, entries={len(Z_bdms)}")
        print(f"First 15 bdms Z: {Z_bdms[:15]}")

        page.close(); ctx.close(); b.close()
        return {"z": z_data, "Z": Z_bdms, "Z_all": Z_list, "Z_offset": bdms_offset}


def disasm(bc, Z, base=0):
    lines = []
    i = 0
    while i < len(bc):
        op = bc[i]
        a = base + i
        i += 1
        m = OPCODES.get(op, f"OP_{op}")
        if op == 38 and i < len(bc):
            lines.append(f"  @{a:x}: {m} {bc[i]}"); i += 1
        elif op == 5 and i < len(bc):
            idx = bc[i]
            s = Z[idx] if idx < len(Z) else f"Z[{idx}]"
            lines.append(f"  @{a:x}: {m} Z[{idx}]={repr(s)[:60]}"); i += 1
        elif op in HAS_OPERAND and i < len(bc):
            lines.append(f"  @{a:x}: {m} {bc[i]}"); i += 1
        else:
            lines.append(f"  @{a:x}: {m}")
    return lines


def gen_vmasm(data):
    z, Z = data["z"], data["Z"]
    lines = [f"; bdms JSVMP vmasm\n; {len(z)} funcs {len(Z)} strings\n"]
    lines.append("[string_table]")
    for i, s in enumerate(Z[:2000]):
        esc = s.encode("unicode_escape").decode("ascii")
        lines.append(f'  str_{i} = "{esc}"')
    lines.append("\n[functions]\n")
    addr = 0
    for idx, func in enumerate(z):
        bc = func["bc"]; fl = func["fl"]
        lines.append(f"\n.def func_{idx}  ; fl={fl} len={len(bc)}")
        lines.append("  bytecode = [%s]" % ",".join(str(b) for b in bc))
        for dl in disasm(bc, Z, addr):
            lines.append(dl)
        addr += len(bc)
    return "\n".join(lines)


def main():
    print("=== Capturing bdms VM ===")
    data = capture()
    jpath = os.path.join(OUT, "functions.json")
    with open(jpath, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Saved {jpath}")
    vpath = os.path.join(OUT, "bdms.vmasm")
    with open(vpath, "w") as f:
        f.write(gen_vmasm(data))
    print(f"Saved {vpath}")
    sizes = [len(f["bc"]) for f in data["z"]]
    print(f"\n{len(data['z'])} funcs, {len(data['Z'])} strings")
    print(f"BC: min={min(sizes)} max={max(sizes)} avg={sum(sizes)/len(sizes):.0f}")
    print(f"First 10 Z: {data['Z'][:10]}")


if __name__ == "__main__":
    main()

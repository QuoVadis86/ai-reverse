"""对称加密 (Symmetry Challenge) - AES+DES"""
import subprocess, urllib.parse, os, sys, time; import httpx
HOST="spiderdemo.cn"; CT="symmetry_challenge"; TOTAL=100
COOKIE=os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv)>1 else None)
def compute(p,c,t):
    s=f'''
    const C=require('crypto-js');const d='{p}_{c}_{t}';const u='abcdefghijklmnop';
    const k16=C.enc.Utf8.parse('1234567890123456');const k32=C.enc.Utf8.parse('12345678901234567890123456789012');
    const iv=C.enc.Utf8.parse(u);const dk=C.enc.Utf8.parse('6f726c64');const di=C.enc.Utf8.parse('01234567');
    const at=C.AES.encrypt(d,k16,{{iv,mode:C.mode.CTR,padding:C.pad.NoPadding}}).toString();
    const dt=C.DES.encrypt(d,dk,{{iv:di,mode:C.mode.CBC,padding:C.pad.Pkcs7}}).toString();
    const a_s=C.AES.encrypt(d,k32,{{iv,mode:C.mode.OFB,padding:C.pad.NoPadding}}).toString();
    const d_s=C.DES.encrypt(d+'_param',dk,{{iv:di,mode:C.mode.CBC,padding:C.pad.Pkcs7}}).toString();
    console.log(encodeURIComponent(at)+'|'+encodeURIComponent(dt)+'|'+encodeURIComponent(a_s)+'|'+encodeURIComponent(d_s));
    '''
    r=subprocess.run(['node','-e',s],capture_output=True,text=True,timeout=10)
    return r.stdout.strip().split('|') if r.returncode==0 else None
if not COOKIE: print("export SPIDERDEMO_COOKIE=..."); sys.exit(1)
ck=COOKIE if COOKIE.startswith("sessionid=") else f"sessionid={COOKIE}"
h={"Host":HOST,"User-Agent":"Mozilla/5.0...","Accept":"application/json, text/plain, */*","Cookie":ck}
with httpx.Client() as cl:
    r=cl.get(f"https://{HOST}/authentication/api/{CT}/init/?challenge_type={CT}",headers=h)
    nums=list(r.json()['page_data'])
    for i in range(2,TOTAL+1):
        ts=str(int(time.time()*1000)); r2=compute(i,CT,ts)
        if not r2: break
        at,dt,a_s,d_s=r2; h["X-Aes-Token"]=urllib.parse.unquote(at); h["X-Des-Token"]=urllib.parse.unquote(dt)
        r=cl.get(f"https://{HOST}/authentication/api/{CT}/page/{i}/?challenge_type={CT}&aes_sign={a_s}&des_sign={d_s}&t={ts}",headers=h)
        nums.extend(r.json()['page_data'])
        if i%25==0: print(f"  {i}/{TOTAL} ({len(nums)})")
        time.sleep(0.05)
    total=sum(nums); print(f"Total: {total}")
    r=cl.post(f"https://{HOST}/authentication/api/{CT}/submit/",json={"challenge_type":CT,"answer":total},headers={"Content-Type":"application/json","Cookie":ck})
    print("OK" if r.json().get("is_correct") else f"FAIL: {r.json()}")

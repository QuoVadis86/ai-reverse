"""非对称加密 (Fsymmetry Challenge) - RSA+AES"""
import subprocess, urllib.parse, os, sys, time; import httpx
HOST="spiderdemo.cn"; CT="fsymmetry_challenge"; TOTAL=100
COOKIE=os.environ.get("SPIDERDEMO_COOKIE") or (sys.argv[1] if len(sys.argv)>1 else None)
PK="""-----BEGIN PUBLIC KEY-----\nMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC1vKwZUIv7pgpJUXXPpDlD4+VE\non3a0ANOrNmqAESrcGfkmYzDCo2JeuYezhBGjBNjwVmSct/Y3BBOCRGT2bvtCJGd\nS12RMvHbFcdbwS/Adh48+rhLiMNYXLm+7pI3e2k6TlScxKa7EeeZpVtew/Cv5z6o\nl0llNPp6BdqAlOa8DwIDAQAB\n-----END PUBLIC KEY-----"""
PVK="""-----BEGIN RSA PRIVATE KEY-----\nMIICXAIBAAKBgQC1vKwZUIv7pgpJUXXPpDlD4+VEon3a0ANOrNmqAESrcGfkmYzD\nCo2JeuYezhBGjBNjwVmSct/Y3BBOCRGT2bvtCJGdS12RMvHbFcdbwS/Adh48+rhL\niMNYXLm+7pI3e2k6TlScxKa7EeeZpVtew/Cv5z6ol0llNPp6BdqAlOa8DwIDAQAB\nAoGAS0GaWI9AsFAFEXBgoz/jkMf14DKTgEFEJVexeNLMnNuawhCNuBSOIMCaO2Zk\nWfpWaygdUeYs6M3UGKRruXhf92g/BRmJK5FzR0kWW4qw6WwlYob3TPc3c9MFOjmp\nVtWQ0VSeEPrnBNoQRccKl0dGBnToHGuV+KEuKx8oWZc/JM0CQQDH/cvlx0BKz2zN\n6PM8FidAvc+Wgon8YW81KJgC7iJIrK9FOpctOE3L1pdF7guOQNVGRqN4HCIgLfHE\ncqxWJKJtAkEA6KIkwHe/Q23uWH5GP8DHtVkLVfohTumYkpb0rk05EYQ0dsWSNzWH\nXDH/kD6ayNq+fscnS8g+59onzvfhJ0bq6wJBAKNFkDEHenWY4js481sauvEgBVnb\nOMvSv/emLHQ39cVfNbhPHRzN2rWPe/CbZtO8GmJFSS/FyBZ9a+P1uryZLAECQAaw\nApZ12s25b0yj9KkIhbU05hqGokZ+eKBeLpKELcvPHSL88wMbStTfqxUed5ymjStf\n1kVbcFOB9fsBLTvP0hkCQFCON0l1VjFli+vqfN0lypgIqCf85V6FZFN19creGCCd\n76pX/X2FIBbUSDN1z48SM5I/RKdCkTx7FY+509q2Mek=\n-----END RSA PRIVATE KEY-----"""
def compute(p,c,t):
    s=f'''
    const C=require('crypto-js');const J=require('jsencrypt');const d='{p}_{c}_{t}';
    function u(e){{var n=new J();n.setPublicKey(`{PK}`);return n.encrypt(e)||""}}
    const ak=u(d),dp=u(d+'_param');
    const si=new J();si.setPrivateKey(`{PVK}`);const sg=si.sign(d,C.SHA256,'sha256');
    const vv=C.HmacSHA256(d,'dsa_secret_key_2025').toString();
    console.log(encodeURIComponent(ak)+'|'+encodeURIComponent(sg)+'|'+encodeURIComponent(dp)+'|'+encodeURIComponent(vv));
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
        ak,sg,dp,vv=r2; h["X-Auth-Key"]=urllib.parse.unquote(ak); h["X-Signature"]=urllib.parse.unquote(sg)
        r=cl.get(f"https://{HOST}/authentication/api/{CT}/page/{i}/?challenge_type={CT}&data={dp}&verify={vv}&t={ts}",headers=h)
        nums.extend(r.json()['page_data'])
        if i%25==0: print(f"  {i}/{TOTAL} ({len(nums)})")
        time.sleep(0.05)
    total=sum(nums); print(f"Total: {total}")
    r=cl.post(f"https://{HOST}/authentication/api/{CT}/submit/",json={"challenge_type":CT,"answer":total},headers={"Content-Type":"application/json","Cookie":ck})
    print("OK" if r.json().get("is_correct") else f"FAIL: {r.json()}")

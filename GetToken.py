# GetToken.py — pega o token do Discord automaticamente (leveldb local + DPAPI).
# Uso: python GetToken.py  -> imprime e salva em token.txt
import base64
import ctypes
import json
import os
import re
import sys

try:
    import requests
except ImportError:
    sys.exit("[-] instale requests: python -m pip install requests")

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

APPDATA = os.getenv("APPDATA") or ""
LOCAL = os.getenv("LOCALAPPDATA") or ""
CLIENTS = {
    "discord": os.path.join(APPDATA, "discord"),
    "discordcanary": os.path.join(APPDATA, "discordcanary"),
    "discordptb": os.path.join(APPDATA, "discordptb"),
}
TOKEN_RE = [
    re.compile(rb"mfa\.[\w-]{84}"),
    re.compile(rb"dQw4w9WgXcQ:([^\"']+)"),
    re.compile(rb"[\w-]{24}\.[\w-]{6}\.[\w-]{27}"),
]


def dpapi_decrypt(blob: bytes) -> bytes:
    from ctypes import wintypes

    class DATA(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_void_p)]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(DATA),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    buf = ctypes.create_string_buffer(blob, len(blob))
    din = DATA()
    din.cbData = len(blob)
    din.pbData = ctypes.cast(buf, ctypes.c_void_p).value
    dout = DATA()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(din), None, None, None, None, 0, ctypes.byref(dout)
    ):
        raise OSError("CryptUnprotectData falhou")
    try:
        out = (ctypes.c_char * dout.cbData)()
        ctypes.memmove(out, dout.pbData, dout.cbData)
        return bytes(out)
    finally:
        k32 = ctypes.WinDLL("kernel32")
        k32.LocalFree.argtypes = [ctypes.c_void_p]
        k32.LocalFree(dout.pbData)


def get_master_key(base: str):
    try:
        with open(os.path.join(base, "Local State"), encoding="utf-8") as f:
            enc = json.load(f)["os_crypt"]["encrypted_key"]
        raw = base64.b64decode(enc)[5:]  # tira prefixo DPAPI
        return dpapi_decrypt(raw)
    except Exception:
        return None


def decrypt_token(enc: bytes, master: bytes) -> str:
    if not enc.startswith(b"v10") or master is None:
        return ""
    nonce, ct = enc[3:15], enc[15:]
    try:
        return AESGCM(master).decrypt(nonce, ct, None).decode()
    except Exception:
        return ""


def valid(token: str):
    try:
        r = requests.get(
            "https://discord.com/api/v9/users/@me",
            headers={"Authorization": token},
            timeout=10,
        )
        if r.status_code == 200:
            u = r.json()
            return f"{u.get('username')} ({u.get('id')})"
    except Exception:
        pass
    return ""


def hunt(base: str):
    found = []
    master = get_master_key(base)
    ldb = os.path.join(base, "Local Storage", "leveldb")
    if not os.path.isdir(ldb):
        return found
    files = []
    for fn in os.listdir(ldb):
        fp = os.path.join(ldb, fn)
        if os.path.isfile(fp):
            files.append((os.path.getmtime(fp), fp))
    files.sort(reverse=True)  # mais recentes primeiro = sessao atual
    for _, fp in files:
        try:
            with open(fp, "rb") as f:
                data = f.read()
        except OSError:
            continue
        for rx in TOKEN_RE:
            for m in rx.finditer(data):
                tok = m.group(1).decode() if m.lastindex else m.group(0).decode()
                if tok.startswith("dQw4w9WgXcQ:"):
                    tok = tok.split(":", 1)[1]
                if HAS_CRYPTO and master and "." not in tok and not tok.startswith("mfa."):
                    try:
                        tok = decrypt_token(base64.b64decode(tok), master)
                    except Exception:
                        continue
                if tok and tok not in found:
                    found.append(tok)
    return found


def main():
    if os.name != "nt":
        sys.exit("[-] windows only")
    if not HAS_CRYPTO:
        print("[*] sem 'cryptography' — tokens novos criptografados nao serao lidos.")
        print("[*] instale: python -m pip install cryptography\n")
    print("[*] procurando tokens...\n")
    for name, base in CLIENTS.items():
        if not os.path.isdir(base):
            continue
        print(f"[*] {name}...")
        for tok in hunt(base):
            who = valid(tok)
            if who:
                print(f"[+] TOKEN VALIDO ({name}): {who}")
                print(f"    {tok}\n")
                with open("token.txt", "w") as f:
                    f.write(tok)
                print("[+] salvo em token.txt")
                return
            else:
                print(f"[-] token invalido/expirado: {tok[:25]}...")
    print("\n[-] nenhum token valido. abre o discord no pc e tenta de novo.")


if __name__ == "__main__":
    main()

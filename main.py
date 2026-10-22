import os
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

TITLE = "Fuck Discord Mrbeast by StriikerZ"
GUNS_URL = "https://guns.lol/striikerz"


def _startup():
    if os.name == "nt":
        os.system(f"title {TITLE}")
    webbrowser.open(GUNS_URL)


def ask_token():
    global TOKEN, HEADERS
    while True:
        try:
            with open("token.txt", encoding="utf-8") as f:
                saved = f.read().strip()
            if saved and not TOKEN.strip():
                TOKEN = saved
                print("[*] token loaded from token.txt")
        except OSError:
            pass

        while not TOKEN.strip():
            try:
                TOKEN = input("paste your discord token: ").strip().strip('"').strip("'")
            except (EOFError, KeyboardInterrupt):
                raise SystemExit(1)
            if not TOKEN:
                print("empty token, try again.")

        HEADERS["Authorization"] = TOKEN

        # validate before proceeding so an expired token doesn't kill the run
        try:
            chk = requests.get(f"{BASE_URL}/users/@me", headers=HEADERS, timeout=10)
        except Exception:
            chk = None
        if chk is not None and chk.status_code == 200:
            print("[+] token ok.")
            global SESSION
            SESSION = requests.Session()
            SESSION.headers.update(HEADERS)
            try:
                with open("token.txt", "w", encoding="utf-8") as f:
                    f.write(TOKEN)
            except OSError:
                pass
            return
        print("[-] token invalid/expired. try again.")
        TOKEN = ""
        try:
            os.remove("token.txt")
        except OSError:
            pass


TOKEN = ""

SESSION = None

HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
BASE_URL = "https://discord.com/api/v9"


def get_friend_ids():
    print("[*] fetching friend list...")
    res = SESSION.get(f"{BASE_URL}/users/@me/relationships", headers=HEADERS)
    if res.status_code != 200:
        print(f"[-] could not fetch friend list. code: {res.status_code}")
        return []
    friends = []
    for rel in res.json():
        if rel.get("type") == 1:
            user = rel.get("user", {})
            friends.append({
                "id": rel["id"],
                "username": user.get("username", "unknown"),
                "global_name": user.get("global_name")
            })
    return friends


def get_existing_dm_recipient_ids():
    res = SESSION.get(f"{BASE_URL}/users/@me/channels", headers=HEADERS)
    if res.status_code != 200:
        return set()
    existing = set()
    for ch in res.json():
        recipients = ch.get("recipients", [])
        if len(recipients) == 1:
            existing.add(recipients[0]["id"])
    return existing


def open_dm_channel(user_id):
    res = SESSION.post(
        f"{BASE_URL}/users/@me/channels",
        headers=HEADERS,
        json={"recipient_id": user_id}
    )
    if res.status_code == 200:
        return res.json().get("id"), None
    elif res.status_code == 429:
        retry_after = res.json().get("retry_after", 5)
        return None, retry_after
    else:
        return None, f"http {res.status_code}"


def send_message(channel_id, content="."):
    res = SESSION.post(
        f"{BASE_URL}/channels/{channel_id}/messages",
        headers=HEADERS,
        json={"content": content}
    )
    if res.status_code == 200:
        return res.json().get("id")
    elif res.status_code == 429:
        retry_after = res.json().get("retry_after", 5)
        time.sleep(retry_after + 1)
        return send_message(channel_id, content)
    return None


def delete_message(channel_id, message_id):
    res = SESSION.delete(
        f"{BASE_URL}/channels/{channel_id}/messages/{message_id}",
        headers=HEADERS
    )
    if res.status_code == 204:
        return True
    elif res.status_code == 429:
        retry_after = res.json().get("retry_after", 5)
        time.sleep(retry_after + 1)
        return delete_message(channel_id, message_id)
    return False


def get_ignored_user_ids():
    print("[*] fetching ignored users...")

    endpoints = [
        f"{BASE_URL}/users/@me/relationships/ignored",
        f"{BASE_URL}/users/@me/ignored-users",
        f"{BASE_URL}/users/@me/relationships",
    ]

    for url in endpoints:
        res = SESSION.get(url, headers=HEADERS)
        print(f"    trying {url.split('/')[-1]} -> {res.status_code}")
        if res.status_code != 200:
            continue

        data = res.json()
        if not isinstance(data, list):
            continue

        ids = []
        for item in data:
            if isinstance(item, dict):
                # relationships endpoint: only blocked (type == 2) count as ignored
                if "relationships" in url and item.get("type") != 2:
                    continue
                uid = item.get("id") or item.get("user_id")
            else:
                uid = item
            if uid:
                ids.append(uid)

        print(f"[+] found {len(ids)} ignored users via this endpoint")
        return ids

    print("[-] could not find ignored users endpoint")
    return []


def unignore_user(user_id):
    res = SESSION.delete(
        f"{BASE_URL}/users/@me/relationships/{user_id}/ignore",
        headers=HEADERS
    )
    if res.status_code in (200, 204):
        return True

    res = requests.put(
        f"{BASE_URL}/users/@me/relationships/{user_id}",
        headers=HEADERS,
        json={"type": 1}
    )
    if res.status_code in (200, 204):
        return True

    return False


def find_my_last_message(channel_id, me_id):
    before = None
    for _ in range(5):
        url = f"{BASE_URL}/channels/{channel_id}/messages?limit=100"
        if before:
            url += f"&before={before}"
        res = SESSION.get(url, headers=HEADERS)

        if res.status_code == 429:
            retry_after = res.json().get("retry_after", 5)
            time.sleep(retry_after + 1)
            continue
        if res.status_code != 200:
            return None, f"http {res.status_code}"

        messages = res.json()
        if not isinstance(messages, list) or not messages:
            break

        for msg in messages:
            if msg.get("author", {}).get("id") == me_id:
                return msg, None

        before = messages[-1].get("id")
        if len(messages) < 100:
            break

    return None, "no message from you"


def main():
    me_res = SESSION.get(f"{BASE_URL}/users/@me", headers=HEADERS)
    if me_res.status_code != 200:
        print("[-] invalid token.")
        return

    me = me_res.json()
    me_id = me["id"]
    print(f"[+] login successful: {me['username']} ({me_id})\n")

    friends = get_friend_ids()
    print(f"[+] found {len(friends)} friends.\n")

    ignored = get_ignored_user_ids()
    print(f"[*] total ignored: {len(ignored)}\n")

    # unignore first so their dms can be opened / scanned
    print("=" * 50)
    print("[phase 2] removing ignored users...")
    print("=" * 50)

    unignored_count = 0
    if ignored:
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(unignore_user, uid): uid for uid in ignored}
            for fut in as_completed(futures):
                uid = futures[fut]
                try:
                    if fut.result():
                        unignored_count += 1
                        print(f"{uid} -> unignored")
                    else:
                        print(f"{uid} -> failed")
                except Exception:
                    print(f"{uid} -> failed")
    else:
        print("[*] no ignored users found, or endpoint not accessible.")

    print(f"\n[+] phase 2 done. {unignored_count} users unignored.\n")

    existing = get_existing_dm_recipient_ids()
    print(f"[*] already open dm: {len(existing)} people\n")

    target_ids = set(f["id"] for f in friends)
    target_ids.update(ignored)
    target_ids.update(existing)

    to_process = [uid for uid in target_ids if uid not in existing]
    print(f"[*] dm to open: {len(to_process)} people")
    print("[*] no confirmation, starting now...\n")

    print("=" * 50)
    print("[phase 1] opening dm with all users...")
    print("=" * 50)

    opened_channels = []

    for i, user_id in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}] {user_id} -> ", end="", flush=True)

        channel_id, error = open_dm_channel(user_id)

        if error and isinstance(error, (int, float)):
            print(f"rate limit, waiting {error}s...")
            time.sleep(error + 1)
            channel_id, error = open_dm_channel(user_id)

        if not channel_id:
            print(f"failed ({error})")
            time.sleep(0.3)
            continue

        opened_channels.append(channel_id)
        print("ok")
        time.sleep(0.6)

    print(f"\n[+] phase 1 done. {len(opened_channels)} dm opened.\n")

    print("=" * 50)
    print("[phase 3] deleting last messages in all dms...")
    print("=" * 50)

    deleted_count = 0

    all_channels_res = SESSION.get(f"{BASE_URL}/users/@me/channels", headers=HEADERS)
    all_channels = all_channels_res.json() if all_channels_res.status_code == 200 else []

    # process EVERY 1-on-1 dm, not just friends
    dm_channels = [ch for ch in all_channels if len(ch.get("recipients", [])) == 1]
    print(f"[*] scanning {len(dm_channels)} dms...\n")

    def _process_channel(channel, me_id):
        channel_id = channel["id"]
        recipient = channel["recipients"][0]
        name = recipient.get("global_name") or recipient.get("username") or recipient["id"]

        my_msg, err = find_my_last_message(channel_id, me_id)
        if err:
            return name, False, err

        content = my_msg.get("content", "").strip() or "[no text]"
        msg_id = my_msg["id"]

        if delete_message(channel_id, msg_id):
            return name, True, f"deleted -> \"{content[:40]}\""
        return name, False, "could not delete"

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(_process_channel, ch, me_id): ch for ch in dm_channels}
        for fut in as_completed(futures):
            name, ok, info = fut.result()
            print(f"{name} -> {info}")
            if ok:
                deleted_count += 1

    print("\n" + "=" * 50)
    print(f"[+] completed!")
    print(f"    dm opened       : {len(opened_channels)}")
    print(f"    unignored users : {unignored_count}")
    print(f"    messages deleted: {deleted_count}")
    print("=" * 50)


if __name__ == "__main__":
    _startup()
    ask_token()
    main()

import os
import time
import webbrowser

import requests

TITLE = "Fuck Discord Mrbeast by StriikerZ"
GUNS_URL = "https://guns.lol/striikerz"


def _startup():
    if os.name == "nt":
        os.system(f"title {TITLE}")
    webbrowser.open(GUNS_URL)


def ask_token():
    global TOKEN, HEADERS
    try:
        with open("token.txt", encoding="utf-8") as f:
            saved = f.read().strip()
        if saved:
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


TOKEN = ""
 
HEADERS = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
BASE_URL = "https://discord.com/api/v9"
 
 
def get_friend_ids():
    print("[*] fetching friend list...")
    res = requests.get(f"{BASE_URL}/users/@me/relationships", headers=HEADERS)
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
    res = requests.get(f"{BASE_URL}/users/@me/channels", headers=HEADERS)
    if res.status_code != 200:
        return set()
 
    existing = set()
    for ch in res.json():
        recipients = ch.get("recipients", [])
        if len(recipients) == 1:
            existing.add(recipients[0]["id"])
    return existing
 
 
def open_dm_channel(user_id):
    res = requests.post(
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
    res = requests.post(
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
    res = requests.delete(
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
        res = requests.get(url, headers=HEADERS)
        print(f"    trying {url.split('/')[-1]} -> {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list):
                ids = []
                for item in data:
                    if isinstance(item, dict):
                        ids.append(item.get("id"))
                    else:
                        ids.append(item)
                print(f"[+] found {len(ids)} ignored users via this endpoint")
                return ids
 
    print("[-] could not find ignored users endpoint")
    return []
 
 
def unignore_user(user_id):
    res = requests.delete(
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
 
 
def main():
    me_res = requests.get(f"{BASE_URL}/users/@me", headers=HEADERS)
    if me_res.status_code != 200:
        print("[-] invalid token.")
        return
 
    me = me_res.json()
    print(f"[+] login successful: {me['username']} ({me['id']})\n")
 
    friends = get_friend_ids()
    print(f"[+] found {len(friends)} friends.\n")
 
    existing = get_existing_dm_recipient_ids()
    print(f"[*] already open dm: {len(existing)} people\n")
 
    to_process = [f for f in friends if f["id"] not in existing]
    print(f"[*] dm to open: {len(to_process)} people")
    print("[*] no confirmation, starting now...\n")
 
    print("=" * 50)
    print("[phase 1] opening dm with all friends...")
    print("=" * 50)
 
    opened_channels = []
 
    for i, friend in enumerate(to_process, 1):
        name = friend["global_name"] or friend["username"]
        print(f"[{i}/{len(to_process)}] {name} (@{friend['username']}) -> ", end="", flush=True)
 
        channel_id, error = open_dm_channel(friend["id"])
 
        if error and isinstance(error, (int, float)):
            print(f"rate limit, waiting {error}s...")
            time.sleep(error + 1)
            channel_id, error = open_dm_channel(friend["id"])
 
        if not channel_id:
            print(f"failed ({error})")
            time.sleep(1)
            continue
 
        msg_id = send_message(channel_id, ".")
        if msg_id:
            delete_message(channel_id, msg_id)
 
        opened_channels.append((channel_id, name))
        print("ok")
 
        time.sleep(1.5)
 
    print(f"\n[+] phase 1 done. {len(opened_channels)} dm opened.\n")
 
    print("=" * 50)
    print("[phase 2] removing ignored users...")
    print("=" * 50)
 
    ignored = get_ignored_user_ids()
    print(f"[*] total ignored: {len(ignored)}\n")
 
    unignored_count = 0
 
    if ignored:
        for i, user_id in enumerate(ignored, 1):
            print(f"[{i}/{len(ignored)}] {user_id} -> ", end="", flush=True)
            if unignore_user(user_id):
                print("unignored")
                unignored_count += 1
            else:
                print("failed")
            time.sleep(0.8)
    else:
        print("[*] no ignored users found, or endpoint not accessible.")
 
    print(f"\n[+] phase 2 done. {unignored_count} users unignored.\n")
 
    print("=" * 50)
    print("[phase 3] deleting last messages in all dms...")
    print("=" * 50)
 
    deleted_count = 0
 
    all_channels_res = requests.get(f"{BASE_URL}/users/@me/channels", headers=HEADERS)
    all_channels = all_channels_res.json() if all_channels_res.status_code == 200 else []
 
    friend_ids = {f["id"] for f in friends}
    friend_channels = []
    for ch in all_channels:
        recipients = ch.get("recipients", [])
        if len(recipients) == 1 and recipients[0]["id"] in friend_ids:
            friend_channels.append(ch)
 
    print(f"[*] scanning {len(friend_channels)} friend dms...\n")
 
    for i, channel in enumerate(friend_channels, 1):
        channel_id = channel["id"]
        recipient = channel["recipients"][0]
        name = recipient.get("global_name") or recipient["username"]
 
        print(f"[{i}/{len(friend_channels)}] {name} -> ", end="", flush=True)
 
        msg_res = requests.get(
            f"{BASE_URL}/channels/{channel_id}/messages?limit=10",
            headers=HEADERS
        )
 
        if msg_res.status_code == 429:
            retry_after = msg_res.json().get("retry_after", 5)
            print(f"rate limit, waiting {retry_after}s...")
            time.sleep(retry_after + 1)
            msg_res = requests.get(
                f"{BASE_URL}/channels/{channel_id}/messages?limit=10",
                headers=HEADERS
            )
 
        if msg_res.status_code != 200:
            print(f"could not fetch messages ({msg_res.status_code})")
            time.sleep(1)
            continue
 
        messages = msg_res.json()
        if not messages:
            print("no messages")
            time.sleep(1)
            continue
 
        my_msg = None
        for msg in messages:
            if msg["author"]["id"] == me["id"]:
                my_msg = msg
                break
 
        if not my_msg:
            print("no message from you")
            time.sleep(1)
            continue
 
        content = my_msg.get("content", "").strip() or "[no text]"
        msg_id = my_msg["id"]
 
        if delete_message(channel_id, msg_id):
            print(f"deleted -> \"{content[:40]}\"")
            deleted_count += 1
        else:
            print("could not delete")
 
        time.sleep(1.5)
 
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
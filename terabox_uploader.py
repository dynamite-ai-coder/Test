import os
import requests
import time
import json
from configuration import (
    TERABOX_NDUS,
    TERABOX_APP_ID,
    TERABOX_UPLOAD_ID,
    TERABOX_JS_TOKEN,
    TERABOX_BROWSER_ID,
    TERABOX_REMOTE_DIR,
)


TERABOX_API = "https://www.terabox.com"


def _get_headers():
    cookies = {}
    if TERABOX_NDUS:
        cookies["ndus"] = TERABOX_NDUS
    if TERABOX_JS_TOKEN:
        cookies["jsToken"] = TERABOX_JS_TOKEN
    if TERABOX_BROWSER_ID:
        cookies["browserid"] = TERABOX_BROWSER_ID
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    return headers, cookies


def _get_upload_url(filename):
    headers, cookies = _get_headers()
    params = {
        "app_id": TERABOX_APP_ID,
        "method": "precreate",
        "path": os.path.join(TERABOX_REMOTE_DIR, filename),
        "size": 0,
        "isdir": 0,
        "autoinit": 1,
    }
    if TERABOX_JS_TOKEN:
        params["jsToken"] = TERABOX_JS_TOKEN
    try:
        r = requests.get(f"{TERABOX_API}/api/precreate", params=params, headers=headers, cookies=cookies, timeout=30)
        data = r.json()
        if data.get("errno") == 0:
            return data.get("data", {})
        print(f"[UPLOAD] Precreate error: {data}")
        return None
    except Exception as e:
        print(f"[UPLOAD] Precreate exception: {e}")
        return None


def upload_file(local_path, filename=None):
    if filename is None:
        filename = os.path.basename(local_path)
    file_size = os.path.getsize(local_path)
    print(f"[UPLOAD] Uploading {filename} ({file_size} bytes)")
    headers, cookies = _get_headers()
    pre = _get_upload_url(filename)
    if not pre:
        return False, "Precreate failed"
    upload_id = pre.get("uploadid", "")
    block_list = pre.get("block_list", [])
    try:
        with open(local_path, "rb") as f:
            parts = []
            idx = 0
            while True:
                chunk = f.read(4 * 1024 * 1024)
                if not chunk:
                    break
                if idx < len(block_list):
                    part_params = {
                        "app_id": TERABOX_APP_ID,
                        "method": "upload",
                        "uploadid": upload_id,
                        "part-number": idx + 1,
                        "size": len(chunk),
                    }
                    if TERABOX_JS_TOKEN:
                        part_params["jsToken"] = TERABOX_JS_TOKEN
                    files = {"file": (f"part{idx}", chunk, "application/octet-stream")}
                    r = requests.post(
                        f"{TERABOX_API}/api/upload",
                        params=part_params,
                        files=files,
                        headers=headers,
                        cookies=cookies,
                        timeout=300,
                    )
                    resp = r.json()
                    if resp.get("errno") != 0:
                        return False, f"Upload part {idx+1} failed: {resp}"
                    parts.append(str(idx + 1))
                idx += 1
        create_params = {
            "app_id": TERABOX_APP_ID,
            "method": "create",
            "uploadid": upload_id,
            "block_list": json.dumps(parts),
            "path": os.path.join(TERABOX_REMOTE_DIR, filename),
        }
        if TERABOX_JS_TOKEN:
            create_params["jsToken"] = TERABOX_JS_TOKEN
        r = requests.post(
            f"{TERABOX_API}/api/create",
            params=create_params,
            headers=headers,
            cookies=cookies,
            timeout=60,
        )
        resp = r.json()
        if resp.get("errno") == 0:
            print(f"[UPLOAD] Success: {filename}")
            return True, "OK"
        return False, f"Create failed: {resp}"
    except Exception as e:
        return False, str(e)


def verify_upload(filename):
    headers, cookies = _get_headers()
    params = {
        "app_id": TERABOX_APP_ID,
        "method": "filelist",
        "dir": TERABOX_REMOTE_DIR,
    }
    if TERABOX_JS_TOKEN:
        params["jsToken"] = TERABOX_JS_TOKEN
    try:
        r = requests.get(f"{TERABOX_API}/api/list", params=params, headers=headers, cookies=cookies, timeout=30)
        data = r.json()
        if data.get("errno") == 0:
            for f in data.get("list", []):
                if f.get("server_filename") == filename:
                    return True
        return False
    except Exception:
        return False

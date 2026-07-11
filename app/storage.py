"""Supabase Storage client for Classwork document uploads/downloads.

Uses the REST API directly (no SDK dependency). The bucket stays private; the
service_role key (server-side only, never sent to the browser) uploads files
and mints short-lived signed URLs for downloads.
"""
from urllib.parse import quote

import requests
from flask import current_app


def _base():
    return f"{current_app.config['SUPABASE_URL']}/storage/v1"


def _enc(key):
    # Encode each path segment (keeps the "/" between post-id and filename)
    # so spaces/special chars in uploaded filenames don't break the URL.
    return "/".join(quote(part, safe="") for part in key.split("/"))


def _headers(extra=None):
    h = {"Authorization": f"Bearer {current_app.config['SUPABASE_SERVICE_KEY']}"}
    if extra:
        h.update(extra)
    return h


def upload(key, data, content_type):
    bucket = current_app.config["SUPABASE_BUCKET"]
    url = f"{_base()}/object/{bucket}/{_enc(key)}"
    headers = _headers({
        "Content-Type": content_type or "application/octet-stream",
        "x-upsert": "true",
    })
    resp = requests.post(url, headers=headers, data=data, timeout=60)
    if resp.status_code >= 400:
        current_app.logger.error("[storage] upload failed %s: %s", resp.status_code, resp.text[:300])
        raise RuntimeError("Upload failed")


def signed_url(key, expires_in=300):
    bucket = current_app.config["SUPABASE_BUCKET"]
    url = f"{_base()}/object/sign/{bucket}/{_enc(key)}"
    resp = requests.post(url, headers=_headers(), json={"expiresIn": expires_in}, timeout=15)
    if resp.status_code >= 400:
        current_app.logger.error("[storage] sign failed %s: %s", resp.status_code, resp.text[:300])
        return None
    signed_path = resp.json().get("signedURL", "")
    if not signed_path:
        return None
    return f"{_base()}{signed_path}" if signed_path.startswith("/") else signed_path


def delete(key):
    bucket = current_app.config["SUPABASE_BUCKET"]
    url = f"{_base()}/object/{bucket}"
    try:
        requests.request("DELETE", url, headers=_headers({"Content-Type": "application/json"}),
                         json={"prefixes": [key]}, timeout=15)
    except requests.RequestException as e:
        current_app.logger.error("[storage] delete failed: %s", e)

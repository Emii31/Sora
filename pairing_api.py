"""Local laptop account pairing routes for the Android shared-memory backend."""

from flask import Blueprint, abort, g, jsonify, request

import auth
import device_pairing

pairing_bp = Blueprint("pairing", __name__, url_prefix="/api/pairing")


@pairing_bp.after_request
def prevent_credential_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _active_local_account(user_id):
    user = auth.get_user(user_id)
    return bool(user and user.get("status") == "active"
                and user.get("account_type") == auth.LOCAL_SINGLE_DEVICE_ACCOUNT_TYPE)


def _require_pairing():
    if not device_pairing.enabled():
        abort(404)
    if not device_pairing.protected_connection(request):
        abort(403, description="Pairing requires HTTPS or a direct loopback connection")


def _owner():
    _require_pairing()
    header = request.headers.get("Authorization", "")
    user_id = getattr(g, "user_id", None)
    if not device_pairing.direct_loopback(request) or not header.startswith("Bearer "):
        abort(403, description="Manage pairing from the laptop with its account bearer credential")
    token_user, _ = auth.get_user_by_token(header[7:].strip())
    if not token_user or token_user != user_id or not _active_local_account(user_id):
        abort(403, description="Pairing requires the existing local laptop account")
    return user_id


@pairing_bp.post("/code")
def issue():
    code, expires = device_pairing.issue_code(auth._ADMIN_DIR, _owner())
    return jsonify({"code": code, "expires_at": expires}), 201


@pairing_bp.post("/redeem")
def redeem():
    _require_pairing()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="A JSON pairing request is required")
    name = body.get("name", "Android")
    if not isinstance(name, str) or not name.strip() or len(name) > 60 or not name.isprintable():
        abort(400, description="Enter a device name with 1 to 60 printable characters")
    device = device_pairing.redeem_code(auth._ADMIN_DIR, body.get("code"), name.strip(), _active_local_account)
    if not device:
        abort(401, description="The pairing code is invalid, used, or expired")
    return jsonify(device), 201


@pairing_bp.get("/devices")
def devices():
    return jsonify({"devices": device_pairing.list_phones(auth._ADMIN_DIR, _owner())})


@pairing_bp.delete("/devices/<device_id>")
def revoke(device_id):
    if not device_pairing.revoke_phone(auth._ADMIN_DIR, _owner(), device_id):
        abort(404)
    return "", 204

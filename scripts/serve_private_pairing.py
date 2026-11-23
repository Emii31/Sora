"""Serve Sora's owner API on loopback and the paired-phone API over private Wi-Fi."""

import argparse
import ipaddress
from pathlib import Path
import ssl
import threading

from werkzeug.serving import make_server

import auth
import device_pairing

_PRIVATE_NETWORKS = tuple(ipaddress.IPv4Network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))


def wifi_address(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Specify the laptop's private IPv4 address") from exc
    if not any(address in subnet for subnet in _PRIVATE_NETWORKS):
        raise ValueError("The Wi-Fi listener requires a private IPv4 address")
    return str(address)


def tls_context(certificate, key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, key)
    return context


def wifi_app(application):
    def restricted(environ, start_response):
        environ[auth.PRIVATE_PAIRING_LAN] = True
        return application(environ, start_response)

    return restricted


def serve(application, address, owner_port, wifi_port, context):
    address = wifi_address(address)
    if not device_pairing.enabled():
        raise RuntimeError("Set SORA_LOCAL_PAIRING=1 to enable the private listeners")
    if context is None:
        raise ValueError("The Wi-Fi listener requires TLS")
    with (make_server("127.0.0.1", owner_port, application, threaded=True) as owner,
          make_server(address, wifi_port, wifi_app(application), threaded=True,
                      ssl_context=context) as wifi):
        owner_thread = threading.Thread(target=owner.serve_forever, name="sora-local-owner", daemon=True)
        owner_thread.start()
        try:
            print(f"Owner API on http://127.0.0.1:{owner.server_port}", flush=True)
            print(f"Paired-phone API on https://{address}:{wifi.server_port}", flush=True)
            wifi.serve_forever()
        finally:
            owner.shutdown()
            owner_thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wifi-address", required=True, help="Specific private IPv4 address on the laptop")
    parser.add_argument("--wifi-port", required=True, type=int)
    parser.add_argument("--owner-port", default=5000, type=int)
    parser.add_argument("--cert", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    args = parser.parse_args()
    try:
        address = wifi_address(args.wifi_address)
        context = tls_context(args.cert, args.key)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if not device_pairing.enabled():
        parser.error("Set SORA_LOCAL_PAIRING=1 to enable the private listeners")
    from app import app
    serve(app, address, args.owner_port, args.wifi_port, context)


if __name__ == "__main__":
    main()

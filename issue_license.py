"""Generate a license key bound to one machine for the Gist owner."""
import argparse
import hashlib
import re
import secrets


def main(argv=None):
    parser = argparse.ArgumentParser(description="Create a key bound to one SLH machine ID.")
    parser.add_argument("hwid", help="64-character machine code shown by the app")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-f0-9]{64}", args.hwid):
        parser.error("machine code must be 64 lowercase hexadecimal characters")

    key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
    print("Key cấp cho user (chỉ hiển thị lần này):")
    print(key)
    print("Thêm hai entry sau vào file licenses.json trên Gist:")
    print(f'  trong "keys": "{key_hash}": "{args.hwid}",')
    print(f'  trong "machines": "{args.hwid}": "{key_hash}",')


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""Extract apple.com cookies from Safari's binary cookies file → Netscape cookies.txt"""

import struct
import sys
import time
from pathlib import Path

_COOKIE_CANDIDATES = [
    Path.home()
    / "Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
    Path.home() / "Library/Cookies/Cookies.binarycookies",
]
COOKIES_DB = next((p for p in _COOKIE_CANDIDATES if p.exists()), _COOKIE_CANDIDATES[0])
MAC_EPOCH_DELTA = 978307200  # Mac epoch (Jan 1 2001) to Unix epoch offset


def read_cstr(data: bytes, offset: int) -> str:
    end = data.index(b"\x00", offset)
    return data[offset:end].decode("utf-8", errors="replace")


def parse_binarycookies(path: Path) -> list[dict]:
    data = path.read_bytes()
    if data[:4] != b"cook":
        raise ValueError(f"Not a Safari cookies file: {path}")

    num_pages = struct.unpack_from(">I", data, 4)[0]
    page_sizes = [
        struct.unpack_from(">I", data, 8 + i * 4)[0] for i in range(num_pages)
    ]

    pos = 8 + num_pages * 4
    cookies = []

    for page_size in page_sizes:
        page = data[pos : pos + page_size]
        pos += page_size

        if page[:4] != b"\x00\x00\x01\x00":
            continue

        num_cookies = struct.unpack_from("<I", page, 4)[0]
        offsets = [
            struct.unpack_from("<I", page, 8 + i * 4)[0] for i in range(num_cookies)
        ]

        for co in offsets:
            flags = struct.unpack_from("<I", page, co + 8)[0]
            domain_off = struct.unpack_from("<I", page, co + 16)[0]
            name_off = struct.unpack_from("<I", page, co + 20)[0]
            path_off = struct.unpack_from("<I", page, co + 24)[0]
            value_off = struct.unpack_from("<I", page, co + 28)[0]
            expiry = struct.unpack_from("<d", page, co + 40)[0]

            cookies.append(
                {
                    "domain": read_cstr(page, co + domain_off),
                    "name": read_cstr(page, co + name_off),
                    "path": read_cstr(page, co + path_off),
                    "value": read_cstr(page, co + value_off),
                    "secure": bool(flags & 1),
                    "expiry": int(expiry) + MAC_EPOCH_DELTA,
                }
            )

    return cookies


def to_netscape(cookies: list[dict]) -> str:
    lines = ["# Netscape HTTP Cookie File", ""]
    for c in cookies:
        domain = c["domain"]
        lines.append(
            "\t".join(
                [
                    domain,
                    "TRUE" if domain.startswith(".") else "FALSE",
                    c["path"],
                    "TRUE" if c["secure"] else "FALSE",
                    str(c["expiry"]),
                    c["name"],
                    c["value"],
                ]
            )
        )
    return "\n".join(lines) + "\n"


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("cookies.txt")

    if not COOKIES_DB.exists():
        print(f"ERROR: Safari cookies not found at {COOKIES_DB}", file=sys.stderr)
        sys.exit(1)

    try:
        all_cookies = parse_binarycookies(COOKIES_DB)
    except PermissionError:
        print("ERROR: Permission denied reading Safari cookies.", file=sys.stderr)
        print("Grant Full Disk Access to your terminal app:", file=sys.stderr)
        print(
            "  System Settings → Privacy & Security → Full Disk Access", file=sys.stderr
        )
        sys.exit(2)

    apple_cookies = [c for c in all_cookies if "apple.com" in c["domain"]]

    if not apple_cookies:
        print("ERROR: No apple.com cookies found.", file=sys.stderr)
        print(
            "Open Safari → music.apple.com and sign in, then re-run.", file=sys.stderr
        )
        sys.exit(1)

    out_path.write_text(to_netscape(apple_cookies))
    print(f"Extracted {len(apple_cookies)} cookies → {out_path}")

    # The file read fine, so Full Disk Access is not the problem here; say which
    # half of the sign-in is missing instead of sending the user to Settings.
    tokens = [
        c
        for c in apple_cookies
        if c["name"] == "media-user-token" and "music.apple.com" in c["domain"]
    ]
    if not tokens:
        print(
            f"ERROR: Safari has no Apple Music sign-in ({len(all_cookies)} cookies read, "
            "none is music.apple.com's media-user-token).",
            file=sys.stderr,
        )
        print(
            "Sign in at music.apple.com in Safari (top right, Sign In), play a few "
            "seconds of a song, quit Safari so it saves its cookies, then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)
    newest = max(c["expiry"] for c in tokens)
    if newest <= time.time():
        print(
            "ERROR: Safari's Apple Music sign-in expired on "
            f"{time.strftime('%Y-%m-%d', time.localtime(newest))}. Sign in again at "
            "music.apple.com in Safari, quit Safari, then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

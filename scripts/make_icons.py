"""สร้างไอคอน PWA (PNG) ด้วย stdlib ล้วน เพื่อไม่ต้องพึ่งไฟล์รูปภายนอก"""
import os
import struct
import sys
import zlib


def png(size: int) -> bytes:
    bg, fg = (21, 128, 61), (255, 255, 255)
    c, ro, ri = size / 2, size * 0.34, size * 0.22
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            rows.extend(fg if ri <= d <= ro else bg)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b"")


out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for s in (192, 512):
    with open(os.path.join(out, f"icon-{s}.png"), "wb") as f:
        f.write(png(s))

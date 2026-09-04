import struct
import sys
import zlib


def make_png(path, width=1400, height=900, rgb=(15, 23, 42)):
    """Generate a minimal PNG placeholder (dark navy with a blue caption bar)."""
    bar_h = 64
    rows = []
    for y in range(height):
        row = bytearray([0])  # PNG filter type 0 (None)
        c = blue = (30, 58, 138) if y >= height - bar_h else rgb
        row += bytes(c) * width
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    make_png(sys.argv[1] if len(sys.argv) > 1 else "architecture.png")
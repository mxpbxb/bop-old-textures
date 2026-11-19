"""A small PNG reader and writer (8-bit RGBA out), enough to layer Chisel's textures into one."""
import struct
import zlib


class Image:
    def __init__(self, w, h, px):
        self.w, self.h, self.px = w, h, px  # px: bytearray, RGBA, row by row

    def get(self, x, y):
        i = (y * self.w + x) * 4
        return self.px[i:i + 4]

    def opaque(self):
        return all(self.px[i] == 255 for i in range(3, len(self.px), 4))

    def frame(self, n):
        """Frame n of an animation strip (square frames, one above the other), round."""
        frames = max(1, self.h // self.w)
        n %= frames
        size = self.w * self.w * 4
        return Image(self.w, self.w, self.px[n * size:(n + 1) * size])

    def frames(self):
        return max(1, self.h // self.w)


def read(path):
    data = open(path, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a png')
    pos, idat, palette, trns = 8, b'', None, None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            w, h, depth, ctype, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif kind == b'PLTE':
            palette = body
        elif kind == b'tRNS':
            trns = body
        elif kind == b'IDAT':
            idat += body
        elif kind == b'IEND':
            break
    if interlace:
        raise ValueError('interlaced')
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, channels * depth // 8)
    stride = (w * channels * depth + 7) // 8
    raw = zlib.decompress(idat)
    rows, prev = [], bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    px = bytearray()
    for line in rows:
        if depth == 16:
            vals = line[0::2]  # each sample's high byte
        elif depth < 8:
            vals = []
            for byte in line:
                for s in range(8 - depth, -1, -depth):
                    vals.append((byte >> s) & ((1 << depth) - 1))
            vals = vals[:w * channels]
        else:
            vals = line
        for x in range(w):
            if ctype == 6:
                px += bytes(vals[x * 4:x * 4 + 4])
            elif ctype == 2:
                r, g, b = vals[x * 3:x * 3 + 3]
                t = depth == 8 and trns is not None and len(trns) >= 6 and (r, g, b) == struct.unpack('>HHH', trns[:6])
                px += bytes((r, g, b, 0 if t else 255))
            elif ctype == 3:
                k = vals[x]
                r, g, b = palette[k * 3:k * 3 + 3]
                a = trns[k] if trns is not None and k < len(trns) else 255
                px += bytes((r, g, b, a))
            elif ctype == 0:
                v = vals[x] if depth >= 8 else vals[x] * 255 // ((1 << depth) - 1)
                t = depth <= 8 and trns is not None and len(trns) >= 2 and vals[x] == struct.unpack('>H', trns[:2])[0]
                px += bytes((v, v, v, 0 if t else 255))
            elif ctype == 4:
                v, a = vals[x * 2:x * 2 + 2]
                px += bytes((v, v, v, a))
    return Image(w, h, px)


def write(path, img):
    raw = bytearray()
    for y in range(img.h):
        raw.append(0)
        raw += img.px[y * img.w * 4:(y + 1) * img.w * 4]
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', struct.pack('>IIBBBBB', img.w, img.h, 8, 6, 0, 0, 0)))
        f.write(chunk(b'IDAT', zlib.compress(bytes(raw), 9)))
        f.write(chunk(b'IEND', b''))


def scaled(img, size):
    """A square frame scaled (nearest) to size x size."""
    if img.w == size:
        return img
    px = bytearray()
    for y in range(size):
        for x in range(size):
            px += img.get(x * img.w // size, y * img.w // size)
    return Image(size, size, px)


def over(layers):
    """Layers (bottom first) put one over the other. Animated layers keep their frames; the
    result has as many frames as the most animated layer, at the largest frame size."""
    size = max(l.w for l in layers)
    frames = max(l.frames() for l in layers)
    out = bytearray()
    for n in range(frames):
        acc = None
        for l in layers:
            f = scaled(l.frame(n), size)
            if acc is None:
                acc = bytearray(f.px)
                continue
            for i in range(0, len(acc), 4):
                a = f.px[i + 3]
                if a == 255:
                    acc[i:i + 4] = f.px[i:i + 4]
                elif a:
                    ba = acc[i + 3]
                    oa = a + ba * (255 - a) // 255
                    for c in range(3):
                        acc[i + c] = (f.px[i + c] * a + acc[i + c] * ba * (255 - a) // 255) // max(oa, 1)
                    acc[i + 3] = oa
        out += acc
    return Image(size, size * frames, out)

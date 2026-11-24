"""Biomes O' Plenty with its old (1.12) textures: the 26.3 port's textures replaced, name by name,
by the 1.12 jar's where the block or item is the same thing.

    python3 -I tools/oldbop.py <unpacked 26.3 BOP mod> <unpacked 1.12 jar> <out mod folder> [report]

The out folder is the 26.3 mod with the replacements. Each replaced texture's `.mcmeta` becomes the
old one's, or goes when the old texture has none and the new one is animated (a still texture under
an animation would be read as frames). Mipmap-only `.mcmeta` (leaves) stays.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import png  # noqa: E402

# Not the same thing in both (1.12's clover is a flower; its blood is a plain fill): left as 26.3's.
SKIP = {'clover', 'clover_stem', 'blood_still', 'blood_flow'}
WOODS = ['dead', 'fir', 'hellbark', 'jacaranda', 'magic', 'mahogany', 'palm', 'pine', 'redwood', 'umbran',
         'willow']


def block_map(old):
    """{new block texture: old block texture}"""
    m = {}
    for w in WOODS:
        m[f'{w}_door_bottom'] = f'door_{w}_lower'
        m[f'{w}_door_top'] = f'door_{w}_upper'
        m[f'{w}_leaves'] = f'leaves_{w}'
        m[f'{w}_sapling'] = f'sapling_{w}'
    m.update({
        'flowering_oak_leaves': 'leaves_flowering',
        'flowering_oak_leaves_overlay': 'leaves_flowering_overlay',
        'flowering_oak_sapling': 'sapling_flowering',
        'origin_oak_leaves': 'leaves_origin',
        'origin_oak_sapling': 'sapling_origin',
        'origin_grass_block_side': 'grass_origin_side',
        'origin_grass_block_top': 'grass_origin_top',
        'origin_grass_block_snow': 'grass_origin_side_snowed',
        'origin_rose': 'rose',
        'dead_grass': 'deadgrass',
        'desert_grass': 'desertgrass',
        'dune_grass': 'dunegrass',
        'tiny_cactus': 'tinycactus',
        'clover_stem': 'cloverstem',
        'white_sandstone': 'white_sandstone_normal',
        'chiseled_white_sandstone': 'white_sandstone_carved',
        'eyebulb_bottom': 'eyebulb_lower',
        'eyebulb_top': 'eyebulb_upper',
        'cattail_bottom': 'tall_cattail_lower',
        'cattail_top': 'tall_cattail_upper',
        'reed_top': 'reed',
        'blood_flow': 'blood_flowing',
    })
    return {k: v for k, v in m.items() if os.path.exists(os.path.join(old, v + '.png'))}


def item_map(old):
    m = {f'{w}_door': f'door_{w}' for w in WOODS}
    m['music_disc_wanderer'] = 'record_wanderer'
    return {k: v for k, v in m.items() if os.path.exists(os.path.join(old, v + '.png'))}


def saturation(im):
    s, n = 0, 0
    for i in range(0, len(im.px), 4):
        if im.px[i + 3] >= 128:
            r, g, b = im.px[i:i + 3]
            s += max(r, g, b) - min(r, g, b)
            n += 1
    return s / max(1, n)


def lum(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def mean(im):
    s, n = [0, 0, 0], 0
    for i in range(0, len(im.px), 4):
        if im.px[i + 3] >= 128:
            for c in range(3):
                s[c] += im.px[i + c]
            n += 1
    return [v / max(1, n) for v in s]


def to_grey(old, new):
    """The old texture in grey, as bright as the new (tinted) one: the game tints it here."""
    target, have = lum(*mean(new)), lum(*mean(old))
    k = target / max(1.0, have)
    out = bytearray(old.px)
    for i in range(0, len(out), 4):
        v = max(0, min(255, round(lum(*old.px[i:i + 3]) * k)))
        out[i:i + 3] = bytes((v, v, v))
    return png.Image(old.w, old.h, out)


def colourize(old, new):
    """The old grey texture (tinted in 1.12, not here) in the new one's colour."""
    c, have = mean(new), lum(*mean(old))
    out = bytearray(old.px)
    for i in range(0, len(out), 4):
        f = lum(*old.px[i:i + 3]) / max(1.0, have)
        out[i:i + 3] = bytes(max(0, min(255, round(f * ch))) for ch in c)
    return png.Image(old.w, old.h, out)


def animated(path):
    if not os.path.exists(path):
        return False
    try:
        return 'animation' in json.load(open(path))
    except Exception:
        return False


def fix_loot_conditions(v):
    """26.3's 0.2.7 writes some loot pools' `conditions` as `condition` (its signs): the game refuses
    the key and with it the world's data packs. Renamed in place; how many."""
    n = 0
    if isinstance(v, dict):
        if isinstance(v.get('condition'), list) and 'conditions' not in v:
            v['conditions'] = v.pop('condition')
            n += 1
        for x in v.values():
            n += fix_loot_conditions(x)
    elif isinstance(v, list):
        for x in v:
            n += fix_loot_conditions(x)
    return n


def fix_loot_tables(out):
    fixed = 0
    data = os.path.join(out, 'data')
    for ns in os.listdir(data):
        lt = os.path.join(data, ns, 'loot_table')
        for d, _, files in os.walk(lt):
            for f in files:
                if f.endswith('.json'):
                    path = os.path.join(d, f)
                    with open(path) as fh:
                        table = json.load(fh)
                    if fix_loot_conditions(table):
                        with open(path, 'w') as fh:
                            json.dump(table, fh, indent=2)
                            fh.write('\n')
                        fixed += 1
    return fixed


def main():
    new, jar, out = sys.argv[1:4]
    if os.path.exists(out):
        shutil.rmtree(out)
    shutil.copytree(new, out)
    print(fix_loot_tables(out), 'loot tables: condition -> conditions')
    nt = os.path.join(out, 'assets', 'biomesoplenty', 'textures')
    ot = os.path.join(jar, 'assets', 'biomesoplenty', 'textures')
    pairs = []
    for sub_new, sub_old, mapping in [('block', 'blocks', None), ('item', 'items', None)]:
        nd, od = os.path.join(nt, sub_new), os.path.join(ot, sub_old)
        m = {n[:-4]: n[:-4] for n in os.listdir(od) if n.endswith('.png') and os.path.exists(os.path.join(nd, n))}
        m.update(block_map(od) if sub_new == 'block' else item_map(od))
        for n, o in sorted(m.items()):
            if n in SKIP or not os.path.exists(os.path.join(nd, n + '.png')):
                continue
            pairs.append((sub_new, n, os.path.join(nd, n + '.png'), os.path.join(od, o + '.png')))
    report = []
    for sub, n, np_, op in pairs:
        a, b = png.read(np_), png.read(op)
        note = []
        if a.w != b.w:
            note.append(f'width {a.w} -> {b.w}')
        sa, sb = saturation(a), saturation(b)
        if sa < 8 <= sb and sub == 'block' and not any(w in n for w in ('_log', 'planks', 'door')):
            png.write(np_, to_grey(b, a))
            note.append('greyed: tinted here')
        elif sb < 8 <= sa and n.endswith('_leaves'):
            png.write(np_, colourize(b, a))
            note.append('coloured: tinted in 1.12 only')
        else:
            shutil.copyfile(op, np_)
        nm, om = np_ + '.mcmeta', op + '.mcmeta'
        if os.path.exists(om):
            shutil.copyfile(om, nm)
        elif animated(nm):
            os.remove(nm)
            note.append('animation dropped')
        report.append((sub, n, os.path.basename(op)[:-4], note))
    for sub, n, o, note in report:
        print(f'{sub}/{n} <- {o}' + (f'  [{"; ".join(note)}]' if note else ''))
    print(len(report), 'textures replaced')


main()

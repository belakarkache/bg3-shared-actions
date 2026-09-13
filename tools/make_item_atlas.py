#!/usr/bin/env python3
import json
import math
import os
import re
import struct
import subprocess
import zlib
from pathlib import Path

from generate_stats import (CATEGORIES, ENABLED_CATEGORIES, ITEM_ATLAS_LSX,
                            atlas_icon_key, category_items)

ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(os.environ.get("BG3_BUILD", "build")) / "atlas"
GAME_DATA_DIR = os.environ.get("BG3_GAME_DATA",
                               r"C:\Program Files (x86)\Steam\steamapps\common\Baldurs Gate 3\Data")
DIVINE = os.environ.get("DIVINE", "Divine.exe")
TEXCONV = os.environ.get("TEXCONV", "texconv.exe")


def windows_path(path):
    return subprocess.run(["wslpath", "-w", str(path)],
                          capture_output=True, text=True, check=True).stdout.strip()

ATLAS_NAME = "SharedActions_Items"
ATLAS_UUID = "b7d4e2a9-5c31-4f08-9e6a-2d7c15b83f40"
TILE_SIZE = 64
ATLAS_COLUMNS = 16

OUT_DDS = ROOT / f"src/Public/SharedActions/Assets/Textures/Icons/{ATLAS_NAME}.dds"
OUT_LSX = ITEM_ATLAS_LSX
MERGED_LSX = ROOT / "src/Public/SharedActions/Content/UI/[PAK]_UI/_merged.lsx"

SOURCE_ATLASES = [
    ("Icons", "Public/Shared/Assets/Textures/Icons/Icons_Items{n}.dds",
     "Shared", "Public/Shared/GUI/Icons_Items{n}.lsx", ["", "_2", "_3", "_4", "_5", "_6"]),
    ("Icons", "Public/SharedDev/Assets/Textures/Icons/Icons_Items_Dev.dds",
     "Shared", "Public/SharedDev/GUI/Icons_Items_Dev.lsx", [""]),
    ("Icons", "Public/GustavX/Assets/Textures/Icons/Icons.dds",
     "GustavX", "Public/GustavX/GUI/Icons.lsx", [""]),
]

RARITIES = ["uncommon", "rare", "veryrare", "legendary", "story"]
RARITY_FRAME_PATH = "Public/Game/GUI/Assets/Shared/rarityFrame_{rarity}_{side}.DDS"

ICON_UV_PATTERN = re.compile(
    r'value="([^"]+)"/>\s*<attribute id="U1" type="float" value="([\d.eE+-]+)"/>'
    r'\s*<attribute id="U2" type="float" value="([\d.eE+-]+)"/>'
    r'\s*<attribute id="V1" type="float" value="([\d.eE+-]+)"/>'
    r'\s*<attribute id="V2" type="float" value="([\d.eE+-]+)"/>')


def read_png(path):
    data = path.read_bytes()
    position, idat_chunks, width, height = 8, [], None, None
    while position < len(data):
        length, chunk_type = struct.unpack(">I4s", data[position:position + 8])
        chunk = data[position + 8:position + 8 + length]
        position += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
            if (bit_depth, color_type) != (8, 6):
                raise SystemExit(f"{path}: esperado RGBA8, veio {bit_depth}/{color_type}")
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk)

    raw = zlib.decompress(b"".join(idat_chunks))
    stride = width * 4
    pixels = bytearray(width * height * 4)
    previous = bytearray(stride)
    offset = 0

    for y in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset:offset + stride])
        offset += stride
        if filter_type == 1:
            for x in range(4, stride):
                line[x] = (line[x] + line[x - 4]) & 255
        elif filter_type == 2:
            for x in range(stride):
                line[x] = (line[x] + previous[x]) & 255
        elif filter_type == 3:
            for x in range(stride):
                left = line[x - 4] if x >= 4 else 0
                line[x] = (line[x] + (left + previous[x]) // 2) & 255
        elif filter_type == 4:
            for x in range(stride):
                left = line[x - 4] if x >= 4 else 0
                up = previous[x]
                upper_left = previous[x - 4] if x >= 4 else 0
                predictor = left + up - upper_left
                da, db, dc = (abs(predictor - left), abs(predictor - up),
                              abs(predictor - upper_left))
                if da <= db and da <= dc:
                    chosen = left
                elif db <= dc:
                    chosen = up
                else:
                    chosen = upper_left
                line[x] = (line[x] + chosen) & 255
        pixels[y * stride:(y + 1) * stride] = line
        previous = line

    return width, height, pixels


def write_png(path, width, height, pixels):
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data)))

    rows = b"".join(b"\x00" + bytes(pixels[y * width * 4:(y + 1) * width * 4])
                    for y in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows, 9))
                     + chunk(b"IEND", b""))


def resample_to_tile(source, source_width, left, top, crop_width, crop_height):
    tile = bytearray(TILE_SIZE * TILE_SIZE * 4)
    for ty in range(TILE_SIZE):
        y0 = top + ty * crop_height // TILE_SIZE
        y1 = max(top + (ty + 1) * crop_height // TILE_SIZE, y0 + 1)
        for tx in range(TILE_SIZE):
            x0 = left + tx * crop_width // TILE_SIZE
            x1 = max(left + (tx + 1) * crop_width // TILE_SIZE, x0 + 1)
            red = green = blue = alpha = samples = 0
            for y in range(y0, y1):
                index = (y * source_width + x0) * 4
                for _ in range(x1 - x0):
                    red += source[index]
                    green += source[index + 1]
                    blue += source[index + 2]
                    alpha += source[index + 3]
                    index += 4
                    samples += 1
            out = (ty * TILE_SIZE + tx) * 4
            tile[out] = red // samples
            tile[out + 1] = green // samples
            tile[out + 2] = blue // samples
            tile[out + 3] = alpha // samples
    return tile


def whole_image_to_tile(image):
    width, height, pixels = image
    return resample_to_tile(pixels, width, 0, 0, width, height)


def composite_over(top, bottom):
    for i in range(0, len(bottom), 4):
        top_alpha = top[i + 3]
        if top_alpha == 0:
            continue
        if top_alpha == 255:
            bottom[i:i + 4] = top[i:i + 4]
            continue
        bottom_alpha = bottom[i + 3]
        out_alpha = top_alpha + bottom_alpha * (255 - top_alpha) // 255
        for channel in range(3):
            blended = (top[i + channel] * top_alpha
                       + bottom[i + channel] * bottom_alpha * (255 - top_alpha) // 255)
            bottom[i + channel] = min(255, blended // out_alpha)
        bottom[i + 3] = out_alpha
    return bottom


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"falhou: {command}\n{result.stdout}\n{result.stderr}")


def fetch_png(pak, inner_path, name):
    png = WORK_DIR / f"{name}.png"
    if png.exists():
        return png
    dds = WORK_DIR / f"{name}.dds"
    if not dds.exists():
        run([DIVINE, "-a", "extract-single-file", "-g", "bg3",
             "-s", f"{GAME_DATA_DIR}\\{pak}.pak", "-f", inner_path,
             "-d", f"{WORK_DIR_WINDOWS}\\{name}.dds"])
    run([TEXCONV, "-ft", "png", "-y", "-o", WORK_DIR_WINDOWS, f"{WORK_DIR_WINDOWS}\\{name}.dds"])
    return png


def fetch_lsx(pak, inner_path, name):
    lsx = WORK_DIR / f"{name}.lsx"
    if not lsx.exists():
        run([DIVINE, "-a", "extract-single-file", "-g", "bg3",
             "-s", f"{GAME_DATA_DIR}\\{pak}.pak", "-f", inner_path,
             "-d", f"{WORK_DIR_WINDOWS}\\{name}.lsx"])
    return lsx


def load_source_index():
    uv_by_icon, atlas_sources = {}, {}
    for dds_pak, dds_template, lsx_pak, lsx_template, suffixes in SOURCE_ATLASES:
        for suffix in suffixes:
            dds_path = dds_template.format(n=suffix)
            lsx_path = lsx_template.format(n=suffix)
            name = Path(dds_path).stem + ("_GustavX" if lsx_pak == "GustavX" else "")
            atlas_sources[name] = (dds_pak, dds_path)
            text = fetch_lsx(lsx_pak, lsx_path, name).read_text(encoding="utf-8")
            for match in ICON_UV_PATTERN.finditer(text):
                uv_by_icon.setdefault(
                    match.group(1), (name,) + tuple(float(v) for v in match.groups()[1:]))
    return uv_by_icon, atlas_sources


def emit_atlas_lsx(icon_keys, width, height):
    entries = []
    for index, key in enumerate(icon_keys):
        column, row = index % ATLAS_COLUMNS, index // ATLAS_COLUMNS
        entries += [
            '                <node id="IconUV">',
            f'                    <attribute id="MapKey" type="FixedString" value="{key}"/>',
            f'                    <attribute id="U1" type="float" value="{column * TILE_SIZE / width:.8f}"/>',
            f'                    <attribute id="U2" type="float" value="{(column + 1) * TILE_SIZE / width:.8f}"/>',
            f'                    <attribute id="V1" type="float" value="{row * TILE_SIZE / height:.8f}"/>',
            f'                    <attribute id="V2" type="float" value="{(row + 1) * TILE_SIZE / height:.8f}"/>',
            "                </node>"]

    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>', "<save>",
        '    <version major="4" minor="8" revision="0" build="500"/>',
        '    <region id="TextureAtlasInfo">', '        <node id="root">',
        "            <children>",
        '                <node id="TextureAtlasIconSize">',
        f'                    <attribute id="Height" type="int32" value="{TILE_SIZE}"/>',
        f'                    <attribute id="Width" type="int32" value="{TILE_SIZE}"/>',
        "                </node>",
        '                <node id="TextureAtlasPath">',
        f'                    <attribute id="Path" type="string" value="Public/SharedActions/Assets/Textures/Icons/{ATLAS_NAME}.dds"/>',
        f'                    <attribute id="UUID" type="FixedString" value="{ATLAS_UUID}"/>',
        "                </node>",
        '                <node id="TextureAtlasTextureSize">',
        f'                    <attribute id="Height" type="int32" value="{height}"/>',
        f'                    <attribute id="Width" type="int32" value="{width}"/>',
        "                </node>",
        "            </children>", "        </node>", "    </region>",
        '    <region id="IconUVList">', '        <node id="root">', "            <children>",
        *entries,
        "            </children>", "        </node>", "    </region>", "</save>", ""])


def ensure_texture_bank_entry():
    text = MERGED_LSX.read_text(encoding="utf-8")
    if ATLAS_UUID in text:
        return
    node = f"""\t\t\t\t<node id="Resource">
\t\t\t\t\t<attribute id="ID" type="FixedString" value="{ATLAS_UUID}" />
\t\t\t\t\t<attribute id="Localized" type="bool" value="False" />
\t\t\t\t\t<attribute id="Name" type="LSString" value="{ATLAS_NAME}" />
\t\t\t\t\t<attribute id="SRGB" type="bool" value="True" />
\t\t\t\t\t<attribute id="SourceFile" type="LSString" value="Public/SharedActions/Assets/Textures/Icons/{ATLAS_NAME}.dds" />
\t\t\t\t\t<attribute id="Streaming" type="bool" value="True" />
\t\t\t\t\t<attribute id="Template" type="FixedString" value="{ATLAS_NAME}" />
\t\t\t\t\t<attribute id="Type" type="int64" value="0" />
\t\t\t\t</node>
\t\t\t</children>"""
    MERGED_LSX.write_text(text.replace("\t\t\t</children>", node, 1), encoding="utf-8")


def catalog_items_with_rarity():
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))
    by_stat = {}
    for category in CATEGORIES:
        if category["key"] not in ENABLED_CATEGORIES:
            continue
        for item in category_items(category, catalog):
            if (item.get("rarity") or "").lower() in RARITIES and item["icon"]:
                by_stat.setdefault(item["stat"], item)
    return list(by_stat.values())


def main():
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    global WORK_DIR_WINDOWS
    WORK_DIR_WINDOWS = windows_path(WORK_DIR)
    items = catalog_items_with_rarity()
    uv_by_icon, atlas_sources = load_source_index()

    rarity_tiles = {
        rarity: tuple(
            whole_image_to_tile(read_png(
                fetch_png("Game", RARITY_FRAME_PATH.format(rarity=rarity, side=side),
                          f"rf_{rarity}_{side}")))
            for side in ("back", "front"))
        for rarity in RARITIES
    }

    decoded_atlases = {}
    tiles, icon_keys, missing = [], [], []

    for item in items:
        uv = uv_by_icon.get(item["icon"])
        if not uv:
            missing.append(item["icon"])
            continue

        atlas_name, u1, u2, v1, v2 = uv
        if atlas_name not in decoded_atlases:
            pak, inner_path = atlas_sources[atlas_name]
            decoded_atlases[atlas_name] = read_png(fetch_png(pak, inner_path, atlas_name))
        source_width, source_height, source = decoded_atlases[atlas_name]

        left, top = round(u1 * source_width), round(v1 * source_height)
        icon = resample_to_tile(source, source_width, left, top,
                                round(u2 * source_width) - left,
                                round(v2 * source_height) - top)

        back, front = rarity_tiles[item["rarity"].lower()]
        composed = bytearray(back)
        composite_over(icon, composed)
        composite_over(front, composed)

        tiles.append(composed)
        icon_keys.append(atlas_icon_key(item["stat"]))

    rows = math.ceil(len(tiles) / ATLAS_COLUMNS)
    width, height = ATLAS_COLUMNS * TILE_SIZE, rows * TILE_SIZE
    atlas = bytearray(width * height * 4)
    for index, tile in enumerate(tiles):
        origin_x = (index % ATLAS_COLUMNS) * TILE_SIZE
        origin_y = (index // ATLAS_COLUMNS) * TILE_SIZE
        for y in range(TILE_SIZE):
            destination = ((origin_y + y) * width + origin_x) * 4
            atlas[destination:destination + TILE_SIZE * 4] = \
                tile[y * TILE_SIZE * 4:(y + 1) * TILE_SIZE * 4]

    write_png(WORK_DIR / f"{ATLAS_NAME}.png", width, height, atlas)
    run([TEXCONV, "-m", "1", "-f", "DXT5", "-dx9", "-y", "-o", WORK_DIR_WINDOWS,
         f"{WORK_DIR_WINDOWS}\\{ATLAS_NAME}.png"])
    OUT_DDS.write_bytes((WORK_DIR / f"{ATLAS_NAME}.dds").read_bytes())
    OUT_LSX.write_text(emit_atlas_lsx(icon_keys, width, height), encoding="utf-8")
    ensure_texture_bank_entry()

    print(f"{len(tiles)} ícones com fundo de raridade -> {width}x{height}")
    if missing:
        print(f"sem tile no atlas do jogo ({len(missing)}): {missing}")
    print("agora rode: ./tools/generate.sh e reempacote o mod")


if __name__ == "__main__":
    main()

import os
import re
import xml.etree.ElementTree as ET


def time_to_sec(time_str: str) -> float:
    """'00:00:01.875' を秒数 (1.875) に変換"""
    h, m, s = time_str.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_kdenlive_keyframes(xml_path: str, fps: float):
    """track.xml からフレーム番号基準のキーフレームリストを抽出"""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if root.tag == "property" and root.attrib.get("name") == "rect":
        rect_elem = root
    else:
        rect_elem = root.find(".//property[@name='rect']")

    if rect_elem is None or not rect_elem.text:
        raise ValueError(
            "track.xml 内に name='rect' の property 要素が見つかりません"
        )

    keyframes = []
    for item in rect_elem.text.strip().split(";"):
        if not item.strip():
            continue
        m = re.match(r"^([^=~|]+)([~|]?=)(.+)$", item.strip())
        if m:
            sec = time_to_sec(m.group(1))
            frame = int(round(sec * fps))
            interp = m.group(2)
            vals = [float(v) for v in m.group(3).split()]
            x, y, w, h = vals[0], vals[1], vals[2], vals[3]
            keyframes.append((frame, interp, x, y, w, h))

    keyframes.sort(key=lambda k: k[0])
    return keyframes


def bake_all_frames(keyframes, fps: float):
    """全フレーム(0 .. max_frame)の描画座標 (ox, oy) とサイズ (size) を事前計算"""
    if not keyframes:
        raise ValueError("有効なキーフレームが見つかりません")

    max_frame = keyframes[-1][0]
    ox_list, oy_list, size_list = [], [], []
    frame_rect = {}

    first_f, _, fx, fy, fw, fh = keyframes[0]
    for f in range(0, first_f + 1):
        frame_rect[f] = (fx, fy, fw, fh)

    for i in range(len(keyframes) - 1):
        f0, interp0, x0, y0, w0, h0 = keyframes[i]
        f1, _, x1, y1, w1, h1 = keyframes[i + 1]

        if f1 <= f0:
            frame_rect[f1] = (x1, y1, w1, h1)
            continue

        for f in range(f0, f1 + 1):
            if interp0 == "|=":
                if f < f1:
                    frame_rect[f] = (x0, y0, w0, h0)
                else:
                    frame_rect[f] = (x1, y1, w1, h1)
            else:
                alpha = (f - f0) / (f1 - f0)
                x = x0 + (x1 - x0) * alpha
                y = y0 + (y1 - y0) * alpha
                w = w0 + (w1 - w0) * alpha
                h = h0 + (h1 - h0) * alpha
                frame_rect[f] = (x, y, w, h)

    for f in range(max_frame + 1):
        x, y, w, h = frame_rect[f]
        size = max(2, int(round(h)))
        cx = x + w / 2.0
        cy = y + h / 2.0
        ox = int(round(cx - size / 2.0))
        oy = int(round(cy - size / 2.0))

        ox_list.append(ox)
        oy_list.append(oy)
        size_list.append(size)

    return ox_list, oy_list, size_list


def build_frame_lookup_expr(values: list[int], idx_expr: str = "n") -> str:
    """全フレーム値リストをランレングス圧縮し、二分探索木式に変換"""
    if not values:
        return "0"

    segments: list[tuple[int | None, int]] = []
    curr_val = values[0]

    for idx in range(1, len(values)):
        if values[idx] != curr_val:
            segments.append((idx, curr_val))
            curr_val = values[idx]

    segments.append((None, curr_val))

    def build_tree(segs: list[tuple[int | None, int]]) -> str:
        if len(segs) == 1:
            return str(segs[0][1])
        mid = len(segs) // 2
        split_n = segs[mid - 1][0]
        left = build_tree(segs[:mid])
        right = build_tree(segs[mid:])
        return f"if(lt({idx_expr},{split_n}),{left},{right})"

    return build_tree(segments)


def generate_bash_script(
    xml_path: str,
    output_sh_path: str = "render.sh",
    fps: float = 8.0,
):
    keyframes = parse_kdenlive_keyframes(xml_path, fps)
    ox_list, oy_list, size_list = bake_all_frames(keyframes, fps)

    # overlay の n は 1 始まりのため (n-1) で 0 始まりに補正する
    ox_expr = build_frame_lookup_expr(ox_list, idx_expr="(n-1)").replace(",", r"\,")
    oy_expr = build_frame_lookup_expr(oy_list, idx_expr="(n-1)").replace(",", r"\,")
    # scale の n は 0 始まりのためそのまま n を使う
    size_expr = build_frame_lookup_expr(size_list, idx_expr="(n-1)").replace(",", r"\,")

    if len(set(size_list)) == 1:
        const_size = size_list[0]
        icon_chain = (
            f"[1:v]format=rgba,scale=w={const_size}:h={const_size}:flags=bilinear,"
            f"loop=loop=-1:size=1:start=0[icon];"
        )
    else:
        icon_chain = (
            f"[1:v]format=rgba,loop=loop=-1:size=1:start=0,"
            f"scale=w='{size_expr}':h='{size_expr}':eval=frame:flags=bilinear[icon];"
        )

    filter_complex = (
        f"{icon_chain}"
        f"[0:v][icon]overlay=x='{ox_expr}':y='{oy_expr}':eval=frame:shortest=1"
    )

    sh_content = f"""#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <base_video_path> <avatar_png_path> [output_mp4_path]" >&2
  exit 1
fi

BASE_VIDEO="$1"
AVATAR_PNG="$2"
OUTPUT_MP4="${{3:-output.mp4}}"

ffmpeg -y -hide_banner -loglevel error \\
  -i "$BASE_VIDEO" \\
  -framerate {fps} -i "$AVATAR_PNG" \\
  -filter_complex "{filter_complex}" \\
  -c:v libx264 \\
  -preset ultrafast \\
  -crf 28 \\
  -pix_fmt yuv420p \\
  -c:a copy \\
  "$OUTPUT_MP4"
"""

    with open(output_sh_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sh_content)

    os.chmod(output_sh_path, 0o755)
    print(f"生成完了: {output_sh_path} (総ベイクフレーム数: {len(ox_list)})")


if __name__ == "__main__":
    generate_bash_script("track.xml", "render.sh", fps=8.0)

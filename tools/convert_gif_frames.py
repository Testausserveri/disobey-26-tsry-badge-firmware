#!/usr/bin/env python3
"""Convert a GIF animation to palette-indexed frames for MicroPython badge firmware.

Outputs a Python module with a shared 256-color palette (RGB565_I format)
and concatenated 1-byte-per-pixel frame data.

Usage:
    python3 tools/convert_gif_frames.py background.GIF \
        frozen_firmware/modules/images/testausserveri_bg_anim.py --frames 20
"""

import argparse
import sys
from PIL import Image


def rgb_to_rgb565i(r, g, b):
    """Convert RGB888 to RGB565_I (byte-swapped, XOR 0xFFFF)."""
    rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    # Byte-swap
    swapped = ((rgb565 & 0xFF) << 8) | ((rgb565 >> 8) & 0xFF)
    # Invert (RGB565_I format)
    return swapped ^ 0xFFFF


def extract_frames(gif_path, num_frames, crop_top=5, crop_bottom=5):
    """Extract evenly-spaced frames from a GIF, cropped."""
    img = Image.open(gif_path)

    # Count total frames
    total = 0
    try:
        while True:
            total += 1
            img.seek(img.tell() + 1)
    except EOFError:
        pass

    print(f"GIF has {total} frames, extracting {num_frames}")

    # Calculate which frames to extract (evenly spaced)
    if num_frames >= total:
        indices = list(range(total))
    else:
        indices = [int(i * total / num_frames) for i in range(num_frames)]

    frames = []
    for idx in indices:
        img.seek(idx)
        frame = img.convert("RGB")
        w, h = frame.size
        # Crop top and bottom
        frame = frame.crop((0, crop_top, w, h - crop_bottom))
        frames.append(frame)

    return frames


def quantize_frames(frames, num_colors=256):
    """Quantize all frames to a shared palette."""
    # Concatenate all frames vertically to get a shared palette
    w, h = frames[0].size
    combined = Image.new("RGB", (w, h * len(frames)))
    for i, f in enumerate(frames):
        combined.paste(f, (0, i * h))

    # Quantize to get shared palette
    quantized = combined.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT)

    # Extract palette
    palette = quantized.getpalette()  # flat list of R, G, B values

    # Split back into individual frames
    quantized_frames = []
    for i in range(len(frames)):
        region = quantized.crop((0, i * h, w, (i + 1) * h))
        quantized_frames.append(region)

    return quantized_frames, palette


def build_palette_rgb565i(palette_rgb):
    """Convert RGB palette to RGB565_I bytes (256 entries, 512 bytes)."""
    result = bytearray(512)
    num_colors = len(palette_rgb) // 3
    for i in range(min(256, num_colors)):
        r = palette_rgb[i * 3]
        g = palette_rgb[i * 3 + 1]
        b = palette_rgb[i * 3 + 2]
        val = rgb_to_rgb565i(r, g, b)
        result[i * 2] = val & 0xFF
        result[i * 2 + 1] = (val >> 8) & 0xFF
    return bytes(result)


def frame_to_indices(quantized_frame):
    """Extract palette index bytes from a quantized frame."""
    return bytes(quantized_frame.getdata())


def bytes_to_python_literal(data, line_width=16):
    """Format bytes as a Python bytes literal with line continuations."""
    lines = []
    for i in range(0, len(data), line_width):
        chunk = data[i:i + line_width]
        hex_str = "".join(f"\\x{b:02x}" for b in chunk)
        lines.append(f"b'{hex_str}'")
    return "\\\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Convert GIF to palette-indexed frames module")
    parser.add_argument("gif", help="Input GIF file")
    parser.add_argument("output", help="Output Python module path")
    parser.add_argument("--frames", type=int, default=20, help="Number of frames to extract")
    parser.add_argument("--crop-top", type=int, default=5, help="Pixels to crop from top")
    parser.add_argument("--crop-bottom", type=int, default=5, help="Pixels to crop from bottom")
    args = parser.parse_args()

    print(f"Extracting {args.frames} frames from {args.gif}...")
    frames = extract_frames(args.gif, args.frames, args.crop_top, args.crop_bottom)

    rows, cols = frames[0].size[1], frames[0].size[0]
    print(f"Frame size: {cols}x{rows}")

    print("Quantizing to shared 256-color palette...")
    quantized_frames, palette_rgb = quantize_frames(frames)

    print("Building RGB565_I palette...")
    palette_bytes = build_palette_rgb565i(palette_rgb)

    print("Extracting frame indices...")
    frame_data_list = []
    for i, qf in enumerate(quantized_frames):
        indices = frame_to_indices(qf)
        frame_data_list.append(bytes(indices))
        if (i + 1) % 5 == 0:
            print(f"  Frame {i + 1}/{len(quantized_frames)}")

    frame_size = rows * cols
    num_frames = len(quantized_frames)
    total_size = len(palette_bytes) + sum(len(f) for f in frame_data_list)
    print(f"Total data: {total_size} bytes ({total_size / 1024:.1f} KB)")
    print(f"  Palette: {len(palette_bytes)} bytes")
    print(f"  Frames: {num_frames} x {frame_size} = {total_size - len(palette_bytes)} bytes")

    print(f"Writing {args.output}...")
    with open(args.output, "w") as f:
        f.write(f'# Generated by convert_gif_frames.py\n')
        f.write(f'rows = {rows}\n')
        f.write(f'cols = {cols}\n')
        f.write(f'num_frames = {num_frames}\n')
        f.write(f'palette =\\\n{bytes_to_python_literal(palette_bytes)}\n')
        # Write each frame as a separate bytes object to avoid mpy-cross memory limits
        for i, fd in enumerate(frame_data_list):
            f.write(f'_f{i} =\\\n{bytes_to_python_literal(fd)}\n')
        frame_refs = ", ".join(f"_f{i}" for i in range(num_frames))
        f.write(f'frames = ({frame_refs})\n')

    print("Done!")


if __name__ == "__main__":
    main()

from PIL import Image, ImageDraw
import os

SIZE = 256

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background circle - deep navy gradient effect
for i in range(128):
    ratio = i / 128
    r = int(10 + ratio * 20)
    g = int(15 + ratio * 30)
    b = int(40 + ratio * 80)
    draw.ellipse(
        [i, i, SIZE - i, SIZE - i],
        fill=(r, g, b, 255)
    )

# Outer glow ring
for thickness in range(6, 0, -1):
    alpha = int(60 * (thickness / 6))
    draw.ellipse(
        [10 - thickness, 10 - thickness, SIZE - 10 + thickness, SIZE - 10 + thickness],
        outline=(100, 180, 255, alpha),
        width=1
    )

# Main accent ring
draw.ellipse([12, 12, SIZE - 12, SIZE - 12], outline=(80, 160, 255, 200), width=3)

# Sound wave arcs - left side
cx, cy = SIZE // 2, SIZE // 2
for i, radius in enumerate([38, 52, 66]):
    alpha = 220 - i * 40
    draw.arc(
        [cx - radius - 10, cy - radius, cx - 10, cy + radius],
        start=150, end=210,
        fill=(100, 200, 255, alpha),
        width=3
    )

# Sound wave arcs - right side
for i, radius in enumerate([38, 52, 66]):
    alpha = 220 - i * 40
    draw.arc(
        [cx + 10, cy - radius, cx + radius + 10, cy + radius],
        start=330, end=390,
        fill=(100, 200, 255, alpha),
        width=3
    )

# Microphone body
mic_w, mic_h = 28, 40
draw.rounded_rectangle(
    [cx - mic_w // 2, cy - mic_h // 2 - 10,
     cx + mic_w // 2, cy + mic_h // 2 - 10],
    radius=14,
    fill=(220, 235, 255, 255),
    outline=(180, 210, 255, 255),
    width=2
)

# Mic grille lines
for offset in [-8, -3, 2, 7]:
    draw.line(
        [cx - mic_w // 2 + 5, cy + offset - 10,
         cx + mic_w // 2 - 5, cy + offset - 10],
        fill=(100, 130, 180, 160),
        width=1
    )

# Mic stand
stand_y = cy + mic_h // 2 - 10
draw.rectangle(
    [cx - 2, stand_y, cx + 2, stand_y + 16],
    fill=(200, 220, 255, 255)
)

# Mic base
draw.rounded_rectangle(
    [cx - 16, stand_y + 13, cx + 16, stand_y + 20],
    radius=4,
    fill=(200, 220, 255, 255)
)

# Specular highlight on mic
draw.ellipse(
    [cx - 7, cy - mic_h // 2 - 6,
     cx - 1, cy - mic_h // 2 + 2],
    fill=(255, 255, 255, 180)
)

# Save in multiple sizes for .ico — USE RELATIVE PATHS
sizes = [256, 128, 64, 48, 32, 16]
images = []
for s in sizes:
    resized = img.resize((s, s), Image.LANCZOS)
    images.append(resized)

# Save icon to current directory (GitHub workspace)
icon_path = os.path.join(os.getcwd(), "whisperpro.ico")
images[0].save(
    icon_path,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=images[1:]
)

print(f"Icon saved to: {icon_path}")

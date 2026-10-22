# The macOS "hello" screen, as a texture for the models that show one.
#
# The wordmark is NOT a font. It is Apple's own hand-lettered mark, and the drawing is on this
# machine in the Hello screensaver bundle: two connected strokes, 34 cubic segments, each
# control point [x, y, z, radius] in a 1000-unit em. "Macintosh 3D", (c) 2020 Apple. Snell
# Roundhand -- which the MacBook build used first -- is a 1965 calligraphic face with high
# stroke contrast and no loops; against the real mark it reads as a different word.
#
# Background: the setup assistant's blurred wallpaper, orange with blue in the corners. The
# sampled palette and the layout fractions come from a 1411x821 screenshot of the real screen;
# both models use the same fractions, so the mark occupies the same share of the display.
#
#   python3 hello_screen.py            # writes macbookpro/hello-screen.png and imac/hello-screen.png
#
# Rerun after changing the palette or the placement. The build scripts load the PNGs as source
# assets -- the same way they load Apple's USDZ -- so a build does not need PIL installed.
import json, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
GLYPHS = "/System/Library/ExtensionKit/Extensions/Hello.appex/Contents/Resources/Languages/en.json"
UI_FONT = "/System/Library/Fonts/SFNS.ttf"

# Fractions of the display, measured off the reference screenshot.
WM_W, WM_CY = 0.291, 0.422          # wordmark width, centre of its inked box
BTN_ICON_CY, BTN_TEXT_CY = 0.869, 0.910
BTN_ICON_D, BTN_FONT = 0.0195, 0.0265
WHITE = (250, 250, 250)

# Panels in millimetres: 14.2" 3024x1964 at 254 ppi; 24" 4480x2520 at 218 ppi.
MAC = (302.4, 196.4)
IMAC = (521.2, 293.0)
TEX_W = 2048                        # 6.8 px/mm on the laptop, 3.9 on the iMac

# Blurred-wallpaper palette, sampled from the reference. (cx, cy, rx, ry, rgb), drawn back to
# front on a low-res canvas and blurred; the shapes are deliberately vague -- it is a blur.
BLOBS = [
    (0.50, 0.50, 0.62, 0.62, (205, 82, 12)),
    (0.18, 0.05, 0.38, 0.30, (230, 150, 20)),
    (0.72, 0.02, 0.34, 0.26, (210, 120, 10)),
    (0.62, 0.55, 0.38, 0.35, (175, 35, 8)),
    (0.95, 0.95, 0.40, 0.40, (150, 25, 8)),
    (0.35, 0.85, 0.30, 0.28, (190, 70, 10)),
    (0.00, 0.98, 0.28, 0.30, (10, 70, 165)),
    (0.88, 0.00, 0.20, 0.25, (30, 85, 150)),
    (-0.02, 0.02, 0.15, 0.15, (30, 100, 120)),
    (0.00, 0.75, 0.15, 0.18, (15, 60, 140)),
]


def gradient(w, h):
    """Soft colour field. Draw solid ellipses small, blur, upscale: cheap and smooth."""
    sw = 256
    sh = max(1, round(sw * h / w))
    im = Image.new("RGB", (sw, sh), BLOBS[0][4])
    for cx, cy, rx, ry, c in BLOBS:
        ImageDraw.Draw(im).ellipse(
            ((cx - rx) * sw, (cy - ry) * sh, (cx + rx) * sw, (cy + ry) * sh), fill=c)
    im = im.filter(ImageFilter.GaussianBlur(sw * 0.10))
    return im.resize((w, h), Image.BICUBIC)


def strokes():
    d = json.load(open(GLYPHS))
    return d["strokes"]


def wordmark(size, ss):
    """Render the two strokes as a tube of the varying radius Apple's data carries. Returns
    (RGBA layer, ink bbox in pixels) at ss times the display size."""
    W, H = size
    st = strokes()
    xs = [p[0] for s in st for seg in s for p in (seg[k] for k in ("p0", "p1", "p2", "p3"))]
    ys = [p[1] for s in st for seg in s for p in (seg[k] for k in ("p0", "p1", "p2", "p3"))]
    rmax = max(p[3] for s in st for seg in s for p in (seg[k] for k in ("p0", "p1", "p2", "p3")))
    gw, gh = max(xs) - min(xs) + 2 * rmax, max(ys) - min(ys) + 2 * rmax
    tw = WM_W * W * ss
    k = tw / gw
    th = gh * k
    x0, x1 = (W * ss - tw) / 2, (W * ss + tw) / 2
    y1 = WM_CY * H * ss + th / 2           # top edge, in image coordinates
    y0 = y1 - th
    # centre the data's padded box on the target box
    ox = x0 - (min(xs) - rmax) * k
    oy = y1 + (min(ys) - rmax) * k         # font y is up, image y is down
    layer = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    for s in st:
        for seg in s:
            p0, p1, p2, p3 = (seg[k] for k in ("p0", "p1", "p2", "p3"))
            for i in range(121):
                t = i / 120
                u = 1 - t
                px = (u ** 3 * p0[0] + 3 * u * u * t * p1[0]
                      + 3 * u * t * t * p2[0] + t ** 3 * p3[0]) * k + ox
                py = oy - (u ** 3 * p0[1] + 3 * u * u * t * p1[1]
                           + 3 * u * t * t * p2[1] + t ** 3 * p3[1]) * k
                r = (u ** 3 * p0[3] + 3 * u * u * t * p1[3]
                     + 3 * u * t * t * p2[3] + t ** 3 * p3[3]) * k
                dr.ellipse((px - r, py - r, px + r, py + r), fill=(*WHITE, 255))
    return layer, (x0, y0, x1, y1)


def screen(size_mm, out, ss=2):
    W = TEX_W
    H = max(1, round(TEX_W * size_mm[1] / size_mm[0]))
    im = gradient(W * ss, H * ss).convert("RGBA")
    mark, _ = wordmark((W, H), ss)
    im = Image.alpha_composite(im, mark)

    dr = ImageDraw.Draw(im, "RGBA")
    # the button: a dim disc, a white ring with a dot, and the label -- as on the real screen
    r = BTN_ICON_D * H * ss / 2
    cx, cy = W * ss / 2, BTN_ICON_CY * H * ss
    dr.ellipse((cx - 2.2 * r, cy - 2.2 * r, cx + 2.2 * r, cy + 2.2 * r), fill=(0, 0, 0, 42))
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(*WHITE, 255), width=max(1, round(r * 0.30)))
    dr.ellipse((cx - 0.30 * r, cy - 0.30 * r, cx + 0.30 * r, cy + 0.30 * r), fill=(*WHITE, 255))
    font = ImageFont.truetype(UI_FONT, round(BTN_FONT * H * ss))
    label = "Get Started"
    # anchor="mm" already treats the x coordinate as the centre; subtracting half the text
    # width here shifted the label left by half its own width.
    dr.text((W * ss / 2, BTN_TEXT_CY * H * ss), label, font=font, fill=(*WHITE, 255),
            anchor="mm")

    im = im.convert("RGB").resize((W, H), Image.LANCZOS)
    im.save(out)
    print(f"wrote {out} {W}x{H}")


if __name__ == "__main__":
    screen(MAC, os.path.join(HERE, "macbookpro", "hello-screen.png"))
    screen(IMAC, os.path.join(HERE, "imac", "hello-screen.png"))

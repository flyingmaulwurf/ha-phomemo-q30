"""Label rendering and Phomemo (ESC/POS raster) encoding. No Home Assistant imports."""

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

DOTS_PER_MM = 8  # 203 dpi

# Bundled so accented letters (á, ő, ű, ...) work on Home Assistant OS, which ships
# no system fonts; Pillow's built-in fallback font has no glyphs for them.
BUNDLED_FONT = str(Path(__file__).parent / "fonts" / "DejaVuSans-Bold.ttf")

FONT_CANDIDATES = [
    BUNDLED_FONT,
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "Arial Bold.ttf",
    "arialbd.ttf",
]


@dataclass(frozen=True)
class LabelGeometry:
    """Label size in printer dots. width = along the feed direction."""

    width: int
    height: int
    margin_x: int
    margin_y: int

    @classmethod
    def from_mm(
        cls, width_mm: float, height_mm: float, margin_x_mm: float, margin_y_mm: float
    ) -> LabelGeometry:
        return cls(
            width=round(width_mm * DOTS_PER_MM),
            height=round(height_mm * DOTS_PER_MM),
            margin_x=round(margin_x_mm * DOTS_PER_MM),
            margin_y=round(margin_y_mm * DOTS_PER_MM),
        )


# Sequence confirmed on a real Phomemo Q30 (M110-family commands):
#   ESC N 0D 05 : print speed, ESC N 04 0F : density (max), 1F 11 0A : label with gaps
PRE = bytes.fromhex("1b4e0d05" "1b4e040f" "1f110a")
#   1F F0 05 00 / 1F F0 03 00 : end of job / feed to next label gap
POST = bytes.fromhex("1ff00500" "1ff00300")
MAX_BLOCK_LINES = 255  # the printer only accepts raster blocks of up to 255 lines


@dataclass(frozen=True)
class PrintJob:
    """Raster header, raster data and web-app footer; parts() gives what the Q30 needs."""

    header: bytes
    data: bytes
    footer: bytes

    def parts(self) -> list[bytes]:
        """Byte strings to send in order: PRE, raster blocks (<=255 lines), POST."""
        bpl = self.header[6] + self.header[7] * 256
        lines = len(self.data) // bpl
        out = [PRE]
        for start in range(0, lines, MAX_BLOCK_LINES):
            n = min(MAX_BLOCK_LINES, lines - start)
            out.append(bytes([0x1D, 0x76, 0x30, 0x00, bpl % 256, bpl // 256, n % 256, n // 256]))
            out.append(self.data[start * bpl : (start + n) * bpl])
        out.append(POST)
        return out


def _load_font(size: int, font_path: str | None = None) -> ImageFont.FreeTypeFont:
    for path in ([font_path] if font_path else []) + FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def _text_bbox(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, size: int
) -> tuple[int, int, int, int]:
    return draw.multiline_textbbox(
        (0, 0), text, font=font, align="center", spacing=max(1, size // 10)
    )


def _fit_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    avail_w: int,
    avail_h: int,
    font_path: str | None,
) -> int:
    """Largest integer font size at which `text` fits the box (0 if even 4 px does not)."""
    lo, hi, best = 4, 250, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        bbox = _text_bbox(draw, text, _load_font(mid, font_path), mid)
        if bbox[2] - bbox[0] <= avail_w and bbox[3] - bbox[1] <= avail_h:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


def _two_line_variants(text: str) -> list[str]:
    """Every way to split a one-line text into two lines at a space."""
    words = text.split()
    return [
        " ".join(words[:i]) + "\n" + " ".join(words[i:]) for i in range(1, len(words))
    ]


def render_text(
    text: str,
    geo: LabelGeometry,
    font_size: int | None = None,
    font_path: str | None = None,
) -> Image.Image:
    """Render centered text. Returns an 'L' image, white background.

    Auto size (font_size not given): a one-line text is printed on one line at the
    largest size that fits; if wrapping it into two lines allows a larger size, it is
    wrapped at the best space instead. Lines you break yourself with a newline are kept.
    """
    img = Image.new("L", (geo.width, geo.height), 255)
    draw = ImageDraw.Draw(img)
    avail_w = max(1, geo.width - 2 * geo.margin_x)
    avail_h = max(1, geo.height - 2 * geo.margin_y)

    if font_size:
        size = font_size
    else:
        text = text.strip()
        candidates = [text]
        if "\n" not in text:
            candidates += _two_line_variants(text)
        best_size = -1
        for cand in candidates:  # first (one line) wins ties
            cand_size = _fit_size(draw, cand, avail_w, avail_h, font_path)
            if cand_size > best_size:
                best_size, text = cand_size, cand
        size = max(best_size, 4)

    font = _load_font(size, font_path)
    bbox = _text_bbox(draw, text, font, size)
    x = (geo.width - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (geo.height - (bbox[3] - bbox[1])) / 2 - bbox[1]
    draw.multiline_text(
        (x, y), text, font=font, fill=0, align="center", spacing=max(1, size // 10)
    )
    return img


def render_image(
    source: str | bytes,
    geo: LabelGeometry,
    rotate: int = 0,
) -> Image.Image:
    """Fit an image file (path) or raw bytes onto the label. Returns 'L', white bg."""
    src = Image.open(io.BytesIO(source) if isinstance(source, bytes) else source)
    src = ImageOps.exif_transpose(src)
    if src.mode in ("RGBA", "LA", "P"):
        src = src.convert("RGBA")
        bg = Image.new("RGBA", src.size, (255, 255, 255, 255))
        src = Image.alpha_composite(bg, src)
    src = src.convert("L")
    if rotate:
        src = src.rotate(-rotate, expand=True, fillcolor=255)
    box = (
        max(1, geo.width - 2 * geo.margin_x),
        max(1, geo.height - 2 * geo.margin_y),
    )
    fitted = ImageOps.contain(src, box, Image.Resampling.LANCZOS)
    img = Image.new("L", (geo.width, geo.height), 255)
    img.paste(
        fitted,
        ((geo.width - fitted.width) // 2, (geo.height - fitted.height) // 2),
    )
    return img


def encode(img: Image.Image, dither: bool = False) -> PrintJob:
    """Convert a white-background 'L' label image to a Phomemo print job.

    Same layout as the web app: the label's x axis is the feed direction (mirrored),
    each printed line is one image column, 8 pixels per byte, MSB = top, 1 = black.
    """
    width, height = img.size
    bytes_per_line = (height + 7) // 8

    inverted = ImageOps.invert(img.convert("L"))  # black -> 255
    mirrored = ImageOps.mirror(inverted)
    lines = mirrored.transpose(Image.Transpose.TRANSPOSE)  # row = one printed line
    mono = lines.convert(
        "1", dither=Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    )
    data = mono.tobytes()  # rows padded to whole bytes with 0 (= no dot)
    assert len(data) == bytes_per_line * width

    header = bytes(
        [
            0x1B, 0x40,  # ESC @ : initialize
            0x1D, 0x76, 0x30, 0x00,  # GS v 0 : raster image, normal
            bytes_per_line % 256, bytes_per_line // 256,
            width % 256, width // 256,
        ]
    )  # fmt: skip
    footer = bytes([0x1B, 0x64, 0x00])  # ESC d 0 : feed 0 lines
    return PrintJob(header=header, data=data, footer=footer)

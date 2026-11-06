"""Drawing game pictures for AI players that read images."""

__all__: tuple[str, ...] = (
    "Canvas",
    "png",
)

import io

from PIL import Image, ImageDraw, ImageFont

from ludotastic.types import Byte, Pixels

type Color = str | tuple[Byte, Byte, Byte]
"""A color: a name or `#rrggbb` that Pillow knows, or red, green and blue."""


class Canvas:
    """A white picture to draw a game on, with a few helpers."""

    def __init__(self, width: Pixels, height: Pixels) -> None:
        """Start a blank picture.

        Image-reading models such as Jev take 280 to 1568 pixels a side.
        """
        self.image = Image.new("RGB", (width, height), "white")
        self.draw = ImageDraw.Draw(self.image)

    def text(
        self,
        xy: tuple[float, float],
        text: str,
        *,
        size: Pixels,
        fill: Color = "black",
    ) -> None:
        """Write text centered on a point.

        Pillow's built-in font has every size, so pictures need no font files.
        """
        font = ImageFont.load_default(size=size)
        self.draw.text(xy, text, fill=fill, font=font, anchor="mm")

    def png(self) -> bytes:
        """The picture as PNG bytes."""
        return png(self.image)


def png(image: Image.Image) -> bytes:
    """Encode a picture as PNG.

    Examples:
        >>> png(Image.new("RGB", (280, 280)))[1:4]
        b'PNG'
    """
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

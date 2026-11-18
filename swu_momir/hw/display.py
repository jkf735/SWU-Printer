"""The 2.42" OLED display: an SSD1309 on SPI0.

Needs luma.oled. Draw frames with render.render_display(). The display may keep showing
its last frame while it has power, even after the Pi halts, so call off() before
shutting down.
"""

SPI_PORT = 0
SPI_DEVICE = 0  # CE0, header pin 24
# DC is GPIO 24 (pin 18) and RST is GPIO 25 (pin 22), which are luma's defaults.


class Display:
    def __init__(self):
        from luma.core.interface.serial import spi
        from luma.oled.device import ssd1309

        self._device = ssd1309(spi(port=SPI_PORT, device=SPI_DEVICE))

    def show(self, image) -> None:
        """Show a 1-bit image the size of the display."""
        self._device.display(image)

    def off(self) -> None:
        self._device.clear()
        self._device.hide()

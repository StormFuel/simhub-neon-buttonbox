"""Rasterize the control symbols for SimHub's embedded image items.

Symbols follow the ISO 2575 dashboard conventions drivers already know: wiper over a windscreen, ignition spark,
start/stop power symbol, main beam (flash-to-pass) for the flasher, dipped beam for the lights, turn-signal arrows,
a video camera, and a fuel pump.
Each is drawn on a 96-unit grid with one stroke weight and rendered at 2x its on-dash size.
"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAMP = 'M50 24Q82 26 82 48T50 72Z'
ARROW = 'M40 20 12 48 40 76V60H82V36H40Z'  # turn-signal tell-tale, pointing left
ICONS = {
    'wipers': ('<path d="M10 28Q48 12 86 28L78 74Q48 82 18 74Z"/>'
               '<path d="M48 70 40 52"/><path d="M40 52 25 33" stroke-width="8"/>'),
    'ignition': ('<path d="M54 14 32 52H48L42 82 66 44H50Z"/>'
                 '<path d="M18 30 26 34M14 54H23M78 62 70 58M82 38H73" stroke-width="4"/>'),
    'engine': '<path d="M31 29A28 28 0 1 0 65 29"/><path d="M48 14V46"/>',
    'flasher': f'<path d="{LAMP}"/><path d="M12 30H38M12 42H38M12 54H38M12 66H38"/>',
    'lights': f'<path d="{LAMP}"/><path d="M38 28 14 36M38 40 14 48M38 52 14 60M38 64 14 72"/>',
    'indicator-left': f'<path d="{ARROW}"/>',
    'indicator-right': f'<path d="{ARROW}" transform="matrix(-1 0 0 1 96 0)"/>',
    'camera': ('<path d="M8 32a6 6 0 0 1 6-6h40a6 6 0 0 1 6 6v32a6 6 0 0 1-6 6H14a6 6 0 0 1-6-6Z"/>'
               '<path d="M60 42 86 28V68L60 54Z"/>'),  # video camera: body and lens cone
    'fuel': ('<path d="M18 84V20a6 6 0 0 1 6-6h24a6 6 0 0 1 6 6V84M12 84H60"/><path d="M26 24H46V42H26Z"/>'
             '<path d="M54 46h6a5 5 0 0 1 5 5v19a5 5 0 0 0 10 0V34l-9-9"/>'),
}
# Telemetry dashboard palette, chosen to match real tell-tales: main beam blue, dipped beam green,
# ignition amber, engine start/stop red, wipers cyan, turn signals green; camera in the livery magenta.
COLORS = {'wipers': '#00D0FF', 'ignition': '#FFD000', 'engine': '#FF2D2D',
          'flasher': '#2F7DFF', 'lights': '#A8F000', 'fuel': '#A8F000',
          'indicator-left': '#39FF14', 'indicator-right': '#39FF14', 'camera': '#FF1ED2'}
SIZE = 128  # on-dash 64 px


def main():
    browser = Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe')
    if not browser.exists():
        browser = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    for name, paths in ICONS.items():
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none" color="{COLORS[name]}" '
               f'stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')
        render(name, svg, SIZE, SIZE, browser)


def render(name, svg, width, height, browser):
    (ROOT/'assets'/f'{name}.svg').write_text(svg, encoding='utf-8')
    page = ROOT/'assets'/f'{name}.html'
    page.write_text(f'<html><style>html,body{{margin:0;background:transparent;width:{width}px;height:{height}px;'
                    f'overflow:hidden}}svg{{width:{width}px;height:{height}px;display:block}}</style>{svg}</html>',
                    encoding='utf-8')
    result = subprocess.run([str(browser), '--headless=new', '--disable-gpu', '--hide-scrollbars',
        '--default-background-color=00000000', f'--window-size={width},{height}',
        '--force-device-scale-factor=1', f'--screenshot={ROOT/"assets"/(name+".png")}', page.as_uri()],
        capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    print('Rendered', name)


if __name__ == '__main__':
    main()

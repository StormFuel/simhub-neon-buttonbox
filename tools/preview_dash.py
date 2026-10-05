"""Render the actual generated item positions with sample telemetry in headless Chrome.

This is a visual approximation, not an evaluation of SimHub formulas.
"""
import base64
import html
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from build_dash import ROOT, NAME

FONT_DIR = Path(r'C:\Program Files (x86)\SimHub\DashFonts')
FONTS = {'EurasiaEx':'EurasiaEx-Bold.ttf'}
SAMPLES = {'TC':'4','ABS':'3','BRAKEBIAS':'56.2','ENGINEMAP':'2',
           'TyreTemperatureFL':'88','TyreTemperatureFR':'91',
           'TyreTemperatureRL':'99','TyreTemperatureRR':'87','Tyres unit':'°C',
           'FL brake label':'BRAKE °C','FR brake label':'BRAKE °C','RL brake label':'BRAKE °C','RR brake label':'BRAKE °C',
           'TyrePressureFL':'27.4PSI','TyrePressureFR':'27.6PSI',
           'TyrePressureRL':'27.1PSI','TyrePressureRR':'27.3PSI',
           'FrontLeft':'432','FrontRightbrake':'451','RearLeftbrake':'378','RearRight':'392',
           'Game':'ACC  ·  SILVERSTONE','Clock':'4:52 PM','Fuel amount':'42.6','Fuel laps':'14.8',
           'Fuel per lap':'2.88','Fuel last lap':'2.91','Fuel percent':'62%'}
FUEL_PERCENT = 62
# Sample tyres under ACC's 75-95-105 °C window: 88 / 91 / 87 optimal, 99 warm.
# Sample brakes in °C: three working, one warm.
BRAKES = {'FL':432,'FR':451,'RL':378,'RR':712}
TYRE_COLORS = {'FL':'#FF39FF14','FR':'#FF39FF14','RL':'#FFFFEA00','RR':'#FF39FF14'}
HIDDEN = {'FrontLeftbrake','FrontRight1','RearLeft1','RearRightbrake',
          'brake2leftFyellow','brake2RightFyellow','brake2leftRyellow','brake2RightRyellow'}


def color(value):
    if len(value) == 9 and value.startswith('#'):
        return f'rgba({int(value[3:5],16)},{int(value[5:7],16)},{int(value[7:9],16)},{int(value[1:3],16)/255})'
    return value


def main():
    path = ROOT/'dash'/NAME/(NAME+'.djson')
    dash = json.loads(path.read_text(encoding='utf-8'))
    with zipfile.ZipFile(str(path)+'.ressources') as z:
        images = {Path(n).stem:base64.b64encode(z.read(n)).decode() for n in z.namelist()}
    rendered = []
    for i in dash['Screens'][0]['Items']:
        name = i['Name']
        if name in HIDDEN or 'ButtonItem' in i['$type']:
            continue
        corner = name.split()[0]
        if name.endswith((' brake fill',' brake outline')):
            band = '39FF14' if BRAKES[corner] <= 650 else 'FFEA00'
            i = dict(i, BackgroundColor=('#66' if name.endswith('fill') else '#FF')+band)
            if name.endswith('fill'):
                i['Width'] = i['Width']*BRAKES[corner]/1000
        if name.endswith(' brake value'):
            i = dict(i, Text=str(BRAKES[corner]))
        style = (f'position:absolute;box-sizing:border-box;left:{i["Left"]}px;top:{i["Top"]}px;'
                 f'width:{i["Width"]}px;height:{i["Height"]}px;')
        bg = i.get('BackgroundColor','#00FFFFFF')
        if name.startswith('brake1'):
            bg = '#FF90EE90'
        if name.startswith('Fuel segment '):
            bg = '#FFA8F000' if (int(name.split()[-1])+0.5)*5 <= FUEL_PERCENT else bg
        if name.endswith(' tyre'):
            bg = TYRE_COLORS[name.split()[0]]
        style += f'background:{color(bg)};'
        border = i.get('BorderStyle',{})
        for side in ('Top','Right','Bottom','Left'):
            style += f'border-{side.lower()}:{border.get("Border"+side,0)}px solid {color(border.get("BorderColor","#00FFFFFF"))};'
        style += 'border-radius:'+' '.join(str(border.get('Radius'+c,0))+'px' for c in ('TopLeft','TopRight','BottomRight','BottomLeft'))+';'
        inner = ''
        if 'IntegratedLedItem' in i['$type']:
            led = i['Settings']['Profiles'][0]['LedContainers'][0]['Color']
            style += f'border-radius:50%;background:{led};'
        elif i.get('IsTextItem'):
            value = SAMPLES.get(name,i.get('Text',''))
            fg = '#FF90EE90' if name in ('FrontLeft','FrontRightbrake','RearLeftbrake','RearRight') else i.get('TextColor','#FFFFFFFF')
            style += (f'display:flex;align-items:center;justify-content:{["flex-start","center","flex-end"][i.get("HorizontalAlignment",0)]};'
                      f'font-family:"{i.get("Font","Oswald")}";font-size:{i["FontSize"]}px;color:{color(fg)};'
                      f'font-weight:{i.get("FontWeight","Normal")};line-height:1;white-space:nowrap;')
            inner = html.escape(value)
        elif 'Image' in i:
            inner = f'<img style="width:100%;height:100%" src="data:image/png;base64,{images[i["Image"]]}">'
        rendered.append(f'<div style=\'{style}\'>{inner}</div>')
    faces = ''.join(f'@font-face{{font-family:"{family}";src:url("{(FONT_DIR/file).as_uri()}");font-weight:100 900;}}' for family,file in FONTS.items())
    document = ('<!doctype html><html><head><meta charset="utf-8"><style>'+faces+
                'body{margin:0;width:1280px;height:720px;background:#050505;overflow:hidden}</style></head><body>'+
                ''.join(rendered)+'</body></html>')
    page = ROOT/'docs/preview.html'
    page.write_text(document,encoding='utf-8')
    browser = next(p for p in [Path(r'C:\Program Files\Google\Chrome\Application\chrome.exe'),
                              Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')] if p.exists())
    result = subprocess.run([str(browser),'--headless=new','--disable-gpu','--hide-scrollbars',
                             '--allow-file-access-from-files','--no-pdf-header-footer','--force-device-scale-factor=1',
                             '--window-size=1280,720','--virtual-time-budget=1000',
                             f'--screenshot={ROOT/"docs/preview.png"}',page.as_uri()],capture_output=True,timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    for suffix in ('.djson.png', '.djson.00.png'):
        shutil.copy2(ROOT/'docs/preview.png', path.parent/(NAME+suffix))
    # Refresh the import package with its Dash Studio selection previews.
    with zipfile.ZipFile(ROOT/'dist'/(NAME+'.simhubdash'),'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(path.parent.glob(NAME+'.djson*')):
            z.write(f,f'{NAME}/{f.name}')
    print('Rendered',ROOT/'docs/preview.png')


if __name__ == '__main__':
    main()

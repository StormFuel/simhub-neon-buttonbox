"""Restyle BOXV2.0 without changing its keyboard commands or telemetry formulas.

Run with `py tools/build_dash.py`. Requires only the Python standard library.
"""
import copy
import json
import struct
import zlib
import zipfile
from pathlib import Path

import dashlib as D

ROOT = Path(__file__).resolve().parent.parent
NAME = 'ButtonBoxLivery'
# Livery palette from simhub-telemetry tools/themes.py: each kind of data keeps its own colour
# (TC yellow, ABS cyan, brake red, throttle/engine lime, "you" blue).
LIME, WHITE, MUTED, INK = '#FFA8F000', '#FFFFFFFF', '#FFB4B4B4', '#FF000000'
YELLOW, CYAN, RED, BLUE = '#FFFFD000', '#FF00D0FF', '#FFFF2D2D', '#FF2F7DFF'
# Tyre colours and temperature windows (°C) from simhub-telemetry: TyrePalette.Neon in plugin
# TurnTelemetry.Core/Tyres/TyreModel.cs and data/tyres/presets.json. Below optLow cold, to optHigh optimal,
# below hot warm, then hot. ACC uses the acc-dry window and AC the ac-slick one; other sims use generic.
TYRE_NODATA, TYRE_COLD, TYRE_OPTIMAL, TYRE_WARM, TYRE_HOT = '#FF262B26', '#FF00B3FF', '#FF39FF14', '#FFFFEA00', '#FFFF1744'
TYRE_WINDOWS = "{AssettoCorsaCompetizione:[75,95,105],AssettoCorsa:[80,105,115]}"
TYRE_GENERIC = '[75,100,115]'
# SimHub reports temperatures in the user's display unit, named by this property ("Celsius" / "Fahrenheit").
TEMP_UNIT = "$prop('DataCorePlugin.GameData.NewData.TemperatureUnit')"
PANEL, LINE, GUIDE = '#F5060606', '#80A8F000', '#26FFFFFF'
LIGHT_OFF = '#FF1C211C'
SIGNAL, MAGENTA = '#FF39FF14', '#FFFF1ED2'
INDICATOR_LEFT = 'DataCorePlugin.GameData.NewData.TurnIndicatorLeft'
INDICATOR_RIGHT = 'DataCorePlugin.GameData.NewData.TurnIndicatorRight'
PIT_LIMITER = 'DataCorePlugin.GameData.NewData.PitLimiterOn'
# The seat controls were replaced (user request 2026-10-03). Its four working buttons now send the turn signals,
# pit limiter and camera; the four dormant seat layers and the seat-height pair are dropped.
# The source's brake readouts (pad images 5-12 and split <700 / >=700 texts 13-20) are replaced by a filled bar
# with the number inside (user request 2026-10-03), and its transparent tyre images 33-36 are unused.
REMOVED = {45, 46, 47, 48, 49, 50} | set(range(5, 21)) | {33, 34, 35, 36}
# Brake bar: fills 0-1000 °C; colour bands in °C, as for tyres: below 200 cold, to 650 working, to 800 warm, then hot.
BRAKE_MAX, BRAKE_WINDOW = 1000, (200, 650, 800)
# Remapped buttons (user request 2026-10-03): pit limiter P (was Numpad 8), camera Alt+C (was Numpad 2).
# SimHub 9.12 stores keys as "SimulatedKeyV2": {KeyCode (WinForms Keys), Win, Ctrl, Alt, Shift}; the legacy
# integer "SimulatedKey" carries no modifiers and, when present, overwrites V2's KeyCode on load (checked by
# deserializing ButtonItem with SimHub's own Newtonsoft), so remapped buttons carry V2 only.
REKEYED = {52: {'KeyCode': 80, 'Win': False, 'Ctrl': False, 'Alt': False, 'Shift': False},
           53: {'KeyCode': 67, 'Win': False, 'Ctrl': False, 'Alt': True, 'Shift': False}}
GAMES = ("{AssettoCorsa:'ASSETTO CORSA',AssettoCorsaCompetizione:'ACC',IRacing:'IRACING',LMU:'LE MANS ULTIMATE',"
         "RFactor2:'RFACTOR 2',Automobilista2:'AUTOMOBILISTA 2',RRRE:'RACEROOM',F12024:'F1 24',F12025:'F1 25',"
         "FH4:'FORZA HORIZON 4',FH5:'FORZA HORIZON 5',FM8:'FORZA MOTORSPORT',BeamNgDrive:'BEAMNG.DRIVE'}")
FUEL = '[DataCorePlugin.GameData.NewData.Fuel]'
FUEL_PCT = '[DataCorePlugin.Computed.Fuel_Percent]'
FUEL_LAPS = '[DataCorePlugin.Computed.Fuel_RemainingLaps]'
FUEL_PER_LAP = '[DataCorePlugin.Computed.Fuel_LitersPerLap]'
FUEL_LAST_LAP = '[DataCorePlugin.Computed.Fuel_LastLapConsumption]'
# One fat, extended face everywhere. It must be a family name both Dash Studio (the font file's own name) and the
# tablet's web client (SimHub Web/FontFaces.css) know: "Futura" and "Eurostar Black Extended" are registered there
# as "Futura Md BT" and "Eurostar", so the tablet drew them in its default serif. EurasiaEx is the same in both.
FONT, WEIGHT = 'EurasiaEx', 'Bold'
D.FONT, D.FONT_WEIGHT = FONT, WEIGHT
D.FONT_DISPLAY, D.DISPLAY_WEIGHT = FONT, WEIGHT
D.FONT_NUMBER, D.NUMBER_WEIGHT = FONT, WEIGHT


def unwrap(value):
    """Convert Newtonsoft reference metadata to ordinary JSON (source has no $ref)."""
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    if isinstance(value, dict):
        if '$ref' in value:
            raise ValueError('Resolve references before transforming this template')
        if '$values' in value:
            return unwrap(value['$values'])
        return {k: unwrap(v) for k, v in value.items() if k != '$id'}
    return value


def transparent_png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0\0\0\0\0')) + chunk(b'IEND', b''))


def position(item, x, y, w, h):
    item.update(Left=float(x), Top=float(y), Width=float(w), Height=float(h))


def label(name, x, y, w, h, value, size=14, color=LIME, align=0):
    return D.text(name, x, y, w, h, value, size, color, align)


def alpha(color, a):
    return '#' + a + color[3:]


def panel(name, x, y, w, h):
    return D.rect(name, x, y, w, h, PANEL, D.border(LINE, 1, 6))


def section(name, x, y, w, title, color=LIME, size=14):
    """Section label, top left, in the colour of the data it heads (as on the telemetry dashboard)."""
    return label(name+' title', x+16, y+12, w-32, 22, title, size, color)


def capsule(name, box, color):
    """Outlined capsule like the telemetry dashboard's SET LINE pill, sized for touch."""
    x, y, w, h = box
    return D.rect(name + ' face', x, y, w, h, alpha(color, '1A'), D.border(alpha(color, 'B3'), 1, h//2))


def sign(name, box, color, plus):
    """+ / - drawn as bars: the dash font has no minus sign, and a hyphen is too short to read as one."""
    x, y, w, h = box
    cx, cy = x + w/2, y + h/2
    out = [D.rect(name + ' bar', cx-11, cy-2.5, 22, 5, color, D.radius_only(2))]
    if plus:
        out.append(D.rect(name + ' stem', cx-2.5, cy-11, 5, 22, color, D.radius_only(2)))
    return out


def main():
    raw = json.loads((ROOT/'source/BOXV2.0/BOXV2.0.djson').read_text(encoding='utf-8-sig'))
    # Editor selection points back to Screens[0]; it is not part of the runtime.
    raw.pop('SelectedScreen', None)
    original = unwrap(raw)
    source = original['Screens'][0]['Items']
    a = copy.deepcopy(source)
    for i in a:
        i.update(IsSelected=False, EnableBlur=False, BlurRadius=0, ShadowBlur=0, ShadowDepth=0)
        i['Id'] = D.sid(NAME, i['Name'])
        if 'Font' in i:
            i.update(Font=FONT, FontWeight=WEIGHT, FontStyle='Normal', HorizontalAlignment=1, VerticalAlignment=1)
        if 'Image' in i:
            i['Image'] = 'transparent'
    position(a[0], 0, 0, 1280, 720)
    a[0]['Image'] = 'livery'
    art = [a[0], panel('Header',24,18,1232,58),
           D.rect('Header accent',40,34,5,26,LIME,D.radius_only(2)),
           label('Game',58,27,800,40,'NO GAME',18,WHITE).bind_js('Text',
               f"var names={GAMES};var code=$prop('DataCorePlugin.CurrentGame');"
               # Track as on the telemetry dashboard's top bar; empty outside a session.
               "var track=$prop('DataCorePlugin.GameData.NewData.TrackName')||'';"
               "return ((names[code]||code||'NO GAME') + (track ? '  ·  ' + track : '')).toUpperCase();"),
           # SimHub's own templates read the PC clock from this property; FormatString is .NET.
           label('Clock',996,25,240,44,'',24,WHITE,2)
               .bind('Text','[DataCorePlugin.CustomExpression.CurrentDateTime]','h:mm tt')]
    boxes = {}
    for idx, (title, readout, minus, plus, color) in enumerate([
        ('TC',28,37,38,YELLOW), ('ABS',30,39,40,CYAN),
        ('BRAKE BIAS',29,41,42,RED), ('ENGINE MAP',31,43,44,LIME)]):
        x = 24 + idx*164
        art += [panel(title+' panel',x,92,148,238),
                D.rect(title+' accent',x+16,92,40,3,color),
                section(title,x,92,148,title,color,12)]
        position(a[readout],x+4,194,140,56)
        a[readout].update(FontSize=26 if idx==2 else 34,TextColor=color)
        for n, by, is_plus in [(plus,136,True),(minus,252,False)]:
            boxes[n] = (x+22,by,104,56)
            art += [capsule(f'{title} {n}',boxes[n],color)] + sign(f'{title} {n}',boxes[n],color,is_plus)
    switches = [(55,'WIPERS',27,CYAN), (59,'IGNITION',None,YELLOW),
                (57,'ENGINE',32,RED), (58,'FLASHER',25,BLUE), (56,'LIGHTS',26,LIME)]
    for j,(n,title,led,color) in enumerate(switches):
        x, y = 24+j*130, 346
        boxes[n] = (x,y,120,156)
        art += [panel(title+' face',*boxes[n]),
                D.rect(title+' tint',x+1,y+1,118,154,alpha(color,'12'),D.radius_only(5)),
                D.image(title+' icon',x+30,y+28,60,60,title.lower()),
                label(title+' label',x+4,y+106,112,24,title,12,color,1),
                D.rect(title+' underline',x+44,y+136,32,3,color,D.radius_only(1))]
        if led is not None:
            # Unlit socket under the source LED, like the telemetry dashboard's wipers/lights lights.
            art.append(D.rect(title+' light',x+98,y+12,12,12,LIGHT_OFF,D.border(alpha(color,'80'),1,6)))
            position(a[led],x+99,y+13,10,10)
            for profile in a[led]['Settings']['Profiles']:
                for container in profile['LedContainers']:
                    container['Color'] = color.replace('#FF','#')
    art += fuel_panel(24,518,640,174)
    drive = [(54,'LEFT','indicator-left',SIGNAL,(684,92,131,190),INDICATOR_LEFT),
             (51,'RIGHT','indicator-right',SIGNAL,(831,92,131,190),INDICATOR_RIGHT),
             (53,'CAMERA','camera',MAGENTA,(684,298,278,190),None)]
    for n,title,icon,color,box,state in drive:
        x, y, w, h = box
        boxes[n] = box
        tint = D.rect(title+' tint',x+1,y+1,w-2,h-2,alpha(color,'12'),D.radius_only(5))
        art += [panel(title+' face',*box), tint,
                D.image(title+' icon',x+w/2-36,y+36,72,72,icon),
                label(title+' label',x+4,y+124,w-8,24,title,13,color,1),
                D.rect(title+' underline',x+w/2-16,y+158,32,3,color,D.radius_only(1))]
        if state:
            # The tile brightens and its light comes on while the game reports the signal on.
            tint.bind_js('BackgroundColor',f"return $prop('{state}') ? '{alpha(color,'40')}' : '{alpha(color,'12')}';")
            art.append(D.rect(title+' light',x+w-24,y+12,12,12,LIGHT_OFF,D.border(alpha(color,'80'),1,6))
                       .bind_js('BackgroundColor',f"return $prop('{state}') ? '{color}' : '{LIGHT_OFF}';"))
    # Pit limiter: amber PIT; the tile fills amber with black text while the limiter is on.
    x, y, w, h = 684,504,278,188
    boxes[52] = (x,y,w,h)
    on = f"$prop('{PIT_LIMITER}')"
    art += [panel('Pit face',x,y,w,h),
            D.rect('Pit fill',x+1,y+1,w-2,h-2,alpha(YELLOW,'12'),D.radius_only(5))
                .bind_js('BackgroundColor',f"return {on} ? '{YELLOW}' : '{alpha(YELLOW,'12')}';"),
            label('Pit text',x,y+36,w,84,'PIT',60,YELLOW,1).bind_js('TextColor',f"return {on} ? '{INK}' : '{YELLOW}';"),
            label('Pit label',x,y+124,w,24,'LIMITER',13,MUTED,1).bind_js('TextColor',f"return {on} ? '{INK}' : '{MUTED}';")]
    for n,key in REKEYED.items():
        del a[n]['SimulatedKey']
        a[n]['SimulatedKeyV2'] = dict(key)
    art += [panel('Tyres panel',980,92,276,600),
            D.rect('Tyres accent',996,92,40,3,LIME),
            section('Tyres',980,92,276,'TYRES / BRAKES'),
            label('Tyres unit',1160,104,80,22,'°C',12,MUTED,2).bind_js('Text',unit_js('')),
            D.rect('Tyres divider',996,405,244,1,GUIDE)]
    # Pressures keep the source's fixed PSI suffix. Temperatures show the number only; the unit follows SimHub's
    # display unit, in the panel header as on the telemetry dashboard.
    corners = [('FL','FrontLeft',24,4), ('FR','FrontRight',22,1), ('RL','RearLeft',23,2), ('RR','RearRight',21,3)]
    for j,(corner,wheel,temp,pressure) in enumerate(corners):
        x = 994+(j%2)*130
        y = 136+(j//2)*280
        art += [label(corner+' label',x+8,y+4,100,22,corner,12,MUTED,1),
                D.rect(corner+' tyre',x+12,y+32,92,88,TYRE_NODATA,D.radius_only(16))
                    .bind_js('BackgroundColor',tyre_color_js(wheel)),
                label(corner+' brake label',x+8,y+162,100,20,'BRAKE °C',10,MUTED,1).bind_js('Text',unit_js('BRAKE '))]
        art += brake_bar(corner,wheel,x+12,y+186,92,30)
        position(a[temp],x+12,y+32,92,88)
        a[temp].update(FontSize=22,TextColor=INK,TextAfterValue='')
        position(a[pressure],x+2,y+126,112,30)
        a[pressure].update(FontSize=14,TextColor=WHITE)
    for n,box in boxes.items():
        position(a[n],*box)
    # Put buttons above the artwork and telemetry.
    items = art + [item for n,item in enumerate(a) if n and n not in REMOVED]
    images = {'livery': (ROOT/'assets/livery.png').read_bytes(), 'transparent': transparent_png()}
    for name in ('wipers','ignition','engine','flasher','lights','fuel','indicator-left','indicator-right','camera'):
        images[name] = (ROOT/'assets'/(name+'.png')).read_bytes()
    out = ROOT/'dash'/NAME
    dash = D.write_dash(out,NAME,'Button Box Livery',
        'BOXV2.0 controls restyled to match Turn Telemetry: livery palette, black carbon, fat extended type.',
        [D.screen('Driver controls',items)],images,1280,720,'1.6.0')
    validate(source, a, dash, images)
    (ROOT/'dist').mkdir(exist_ok=True)
    package = ROOT/'dist'/f'{NAME}.simhubdash'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.glob(NAME+'.djson*')):
            z.write(f,f'{NAME}/{f.name}')
    (ROOT/'docs/control-map.json').write_text(json.dumps([
        {'name':i['Name'],'keyCode':i.get('SimulatedKey'),'key':i.get('SimulatedKeyV2'),'enabled':i['SimulateKey'],
         'simHubInput':i['TriggerSimHubInputName'],
         'bounds':[i[k] for k in ('Left','Top','Width','Height')]}
        for n,i in enumerate(a) if n >= 37 and n not in REMOVED],indent=2),encoding='utf-8')
    print(f'Validated {60-37-len(REMOVED & set(range(37,60)))} button actions, {36-len(REMOVED & set(range(1,37)))} source telemetry items, all bindings, bounds and embedded assets.')
    print('Built',package)


def unit_js(prefix):
    return f"var u={TEMP_UNIT}||''; return '{prefix}' + (/^f/i.test(u) ? '°F' : '°C');"


def tyre_color_js(wheel):
    """Telemetry dashboard tyre colour for one wheel's average temperature, converted to °C first."""
    return (f"var t=$prop('DataCorePlugin.GameData.NewData.TyreTemperature{wheel}'); if(!t) return '{TYRE_NODATA}';"
            f"var c=/^f/i.test({TEMP_UNIT}||'') ? (t-32)*5/9 : t; if(c<=0) return '{TYRE_NODATA}';"
            f"var w={TYRE_WINDOWS}[$prop('DataCorePlugin.CurrentGame')]||{TYRE_GENERIC};"
            f"return c<w[0] ? '{TYRE_COLD}' : c<=w[1] ? '{TYRE_OPTIMAL}' : c<w[2] ? '{TYRE_WARM}' : '{TYRE_HOT}';")


def brake_bar(corner, wheel, x, y, w, h):
    """Bar outlined in the brake's temperature colour, filled in a darker shade of it proportionally to the
    temperature (0-1000 °C), with the number in white inside: legible wherever the fill ends."""
    prop = f'DataCorePlugin.GameData.NewData.BrakeTemperature{wheel}'
    celsius = f"var t=$prop('{prop}')||0; var c=/^f/i.test({TEMP_UNIT}||'') ? (t-32)*5/9 : t;"
    cold, opt, hot = BRAKE_WINDOW
    def band(a):
        return (f"{celsius} return c<=0 ? '{TYRE_NODATA}' : c<{cold} ? '{alpha(TYRE_COLD,a)}' : c<={opt} ? "
                f"'{alpha(TYRE_OPTIMAL,a)}' : c<{hot} ? '{alpha(TYRE_WARM,a)}' : '{alpha(TYRE_HOT,a)}';")
    b = 2
    return [D.rect(corner+' brake outline',x,y,w,h,TYRE_NODATA,D.radius_only(7)).bind_js('BackgroundColor',band('FF')),
            D.rect(corner+' brake track',x+b,y+b,w-2*b,h-2*b,'#FF0E100E',D.radius_only(5)),
            D.rect(corner+' brake fill',x+b,y+b,w-2*b,h-2*b,alpha(TYRE_OPTIMAL,'66'),D.radius_only(5))
                .bind_js('Width',f"{celsius} return Math.max(1, Math.min({w-2*b}, c / {BRAKE_MAX} * {w-2*b}));")
                .bind_js('BackgroundColor',band('66')),
            label(corner+' brake value',x,y,w,h,'0',16,WHITE,1).bind('Text',f'isnull([{prop}],0)','0')]


def fuel_panel(x, y, w, h):
    """Fuel left, laps it covers, average and last-lap use, and a 20-segment level bar: lime, yellow below 25%,
    red below 15%."""
    out = [panel('Fuel panel',x,y,w,h), D.rect('Fuel accent',x+16,y,40,3,LIME),
           D.image('Fuel icon',x+16,y+10,26,26,'fuel'),
           label('Fuel title',x+50,y+12,200,22,'FUEL',14,LIME),
           label('Fuel percent',x+w-136,y+12,116,22,'0%',14,WHITE,2).bind('Text',f'isnull({FUEL_PCT},0)',"0'%'")]
    stats = [('Fuel amount','LITRES',FUEL,'0.0',WHITE,182),
             ('Fuel laps','LAPS LEFT',FUEL_LAPS,'0.0',LIME,140),
             ('Fuel per lap','AVG / LAP',FUEL_PER_LAP,'0.00',CYAN,140),
             ('Fuel last lap','LAST LAP',FUEL_LAST_LAP,'0.00',YELLOW,140)]
    cx = x+20
    for n,(name,caption,expr,fmt,color,cw) in enumerate(stats):
        if n:
            out.append(D.rect(name+' divider',cx-12,y+50,1,72,GUIDE))
        out.append(label(name+' caption',cx,y+48,cw-16,22,caption,11,MUTED))
        value = label(name,cx,y+74,cw-16,50,'0',30 if n == 0 else 21,color).bind('Text',f'isnull({expr},0)',fmt)
        if name == 'Fuel laps':
            value.bind('TextColor',f"if(isnull({expr},99) < 2,'{RED}','{LIME}')")
        out.append(value)
        cx += cw
    count, gap = 20, 4
    seg = (w-36-gap*(count-1))/count
    for n in range(count):
        threshold = (n+0.5)*100/count
        out.append(D.rect(f'Fuel segment {n}',x+18+n*(seg+gap),y+138,seg,18,'#26A8F000',D.radius_only(2)).bind(
            'BackgroundColor',f"if(isnull({FUEL_PCT},0) < {threshold:g},'#26A8F000',"
                              f"if({FUEL_PCT} < 15,'{RED}',if({FUEL_PCT} < 25,'{YELLOW}','{LIME}')))"))
    return out


def validate(source, transformed, dash, images):
    assert len(source) == len(transformed) == 60
    for n,(before,after) in enumerate(zip(source,transformed)):
        assert before['Bindings'] == after['Bindings'],before['Name']+' binding changed'
        if 'ButtonCommand' in before:
            if n in REKEYED:
                assert 'SimulatedKey' not in after and after['SimulatedKeyV2'] == REKEYED[n],before['Name']+' key'
            else:
                assert after['SimulatedKey'] == before['SimulatedKey'],before['Name']+' key changed'
            for key in ('SimulateKey','TriggerSimHubInputName','SimulatedKeyPressTime','ButtonCommand'):
                assert after[key] == before[key],before['Name']+' action changed'
    for item in dash['Screens'][0]['Items']:
        assert 0 <= item['Left'] <= 1280-item['Width'],item['Name']
        assert 0 <= item['Top'] <= 720-item['Height'],item['Name']
        if 'Image' in item:
            assert item['Image'] in images,item['Name']+' missing image'
        assert not item.get('EnableBlur'),item['Name']+' blur enabled'
        if 'Font' in item:
            assert item['Font'] == FONT,item['Name']+' uses '+item['Font']
    buttons = [i for n,i in enumerate(transformed) if i.get('SimulateKey') and n not in REMOVED]
    assert len(buttons) == 60-37-len(REMOVED & set(range(37,60)))
    for n,a in enumerate(buttons):
        for b in buttons[n+1:]:
            assert (a['Left']+a['Width'] <= b['Left'] or b['Left']+b['Width'] <= a['Left']
                    or a['Top']+a['Height'] <= b['Top'] or b['Top']+b['Height'] <= a['Top']), (a['Name'],b['Name'])


if __name__ == '__main__':
    main()

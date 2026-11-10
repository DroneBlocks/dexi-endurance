#!/usr/bin/env python3
"""Build the DEXI-5 endurance report (HTML) from a run's minutes.csv.

    python3 build_report.py ~/_dev/dexi-endurance/<run>        # writes <run>/report.html

Light DroneBlocks house style. Single-series charts, inline SVG, hover tooltips.
"""
import csv, html, json, math, shutil, sys
from datetime import datetime
from pathlib import Path

LOGO = Path.home() / '_dev/droneblocks-marketing/render/house-style/assets/droneblocks-logo.svg'


def f(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def load(run):
    rows = list(csv.DictReader(open(run / 'minutes.csv')))
    for r in rows:
        for k in list(r):
            if k not in ('clock', 'modes', 'pi_throttled'):
                r[k] = f(r[k])
    return rows


def fmt(v, d=1, unit=''):
    return '–' if v is None else f'{v:.{d}f}{unit}'


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def chart(cid, title, unit, pts, d=1, note=''):
    """pts = [(minute, value)]; one series, one axis."""
    pts = [(m, v) for m, v in pts if v is not None]
    data = json.dumps([[m, round(v, 3)] for m, v in pts])
    return f'''<figure class="chart" id="{cid}" data-unit="{html.escape(unit)}" data-d="{d}" data-pts='{data}'>
<figcaption><b>{html.escape(title)}</b>{f' <span class="muted">{html.escape(note)}</span>' if note else ''}</figcaption>
<svg role="img" aria-label="{html.escape(title)} by flight minute"></svg><div class="tip" hidden></div></figure>'''


def motor_minutes(run, rows):
    """Attach r['rpm_m'] = [M1..M4 mean RPM] to each minutes row from the 1 Hz samples."""
    samp = [x for x in csv.DictReader(open(run / 'samples.csv')) if x.get('rpm1') not in (None, '', '0')]
    prev = ''
    for r in rows:
        win = [x for x in samp if prev < x['clock'] <= r['clock']]
        r['rpm_m'] = [mean([f(x[f'rpm{i}']) for x in win]) for i in range(1, 5)] if win else [None] * 4
        prev = r['clock']


MOTOR_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']   # validated: CVD pass, contrast WARN -> direct labels + table


def chart_multi(cid, title, unit, series, d=0, note=''):
    """series = [(name, color, [(minute, value)])]; one axis, legend + direct labels."""
    data = json.dumps([[n, c, [[m, round(v, 1)] for m, v in pts if v is not None]] for n, c, pts in series])
    legend = ''.join(f'<span class="lg"><i style="background:{c}"></i>{html.escape(n)}</span>' for n, c, _ in series)
    return f'''<figure class="chart wide" id="{cid}" data-unit="{html.escape(unit)}" data-d="{d}" data-series='{data}'>
<figcaption><b>{html.escape(title)}</b>{f' <span class="muted">{html.escape(note)}</span>' if note else ''}<div class="legend">{legend}</div></figcaption>
<svg role="img" aria-label="{html.escape(title)} by flight minute"></svg><div class="tip" hidden></div></figure>'''


def build(run):
    rows = load(run)
    motor_minutes(run, rows)
    fl = [r for r in rows if (r['offboard_pct'] or 0) >= 90]           # full minutes holding on the tag
    if not fl:
        fl = [r for r in rows if (r['airborne_s'] or 0) > 0]
    start = rows[0]['clock'] if rows else ''
    air = rows[-1]['airborne_s'] if rows else 0
    last = fl[-5:] if fl else []
    total_resets = sum(int(r['hgt_resets'] or 0) for r in fl)
    wh = rows[-1]['wh_total'] if rows else None
    for i, r in enumerate(fl, 1):
        r['flight_min'] = i

    tiles = [
        (f'{int(air // 3600)}h {int(air % 3600 // 60):02d}m' if air else '–', 'airborne'),
        (fmt(mean([r['err_mean_cm'] for r in last])) + ' cm', 'tag error, mean (last 5 min)'),
        (fmt(max([r['err_max_cm'] or 0 for r in fl] or [0])) + ' cm', 'tag error, worst minute max'),
        ('±' + fmt(mean([r['range_std_cm'] for r in last])) + ' cm', 'altitude hold (last 5 min)'),
        (str(total_resets), 'EKF height resets in hold'),
        (fmt(mean([r['bat_w_mean'] for r in fl]), 0) + ' W', 'average power'),
        (fmt(wh, 0) + ' Wh', 'energy used'),
        (fmt(max([r['pi_temp_max'] or 0 for r in fl] or [0]), 0) + ' °C', 'CM4 peak temp'),
    ]

    # 5-minute blocks
    blocks = []
    for i in range(0, len(fl), 5):
        b = fl[i:i + 5]
        blocks.append(dict(
            span=f"{b[0]['flight_min']}–{b[-1]['flight_min']}", clock=b[-1]['clock'],
            err=mean([r['err_mean_cm'] for r in b]), p95=max([r['err_p95_cm'] or 0 for r in b]),
            tag=mean([r['tag_visible_pct'] for r in b]), alt=mean([r['range_mean_m'] for r in b]),
            altsd=mean([r['range_std_cm'] for r in b]), resets=sum(int(r['hgt_resets'] or 0) for r in b),
            hdg=b[-1]['heading_drift_deg'], w=mean([r['bat_w_mean'] for r in b]), v=min([r['bat_v_min'] or 99 for r in b]),
            rpm=mean([r['rpm_mean'] for r in b]), rpm_m=[mean([r['rpm_m'][i] for r in b]) for i in range(4)], spread=max([r['rpm_spread_pct'] or 0 for r in b]),
            esc=max([r['esc_t_max'] or 0 for r in b]), escerr=max([r['esc_err'] or 0 for r in b]),
            cpu=mean([r['pi_cpu_mean'] for r in b]), cpumax=max([r['pi_cpu_max'] or 0 for r in b]),
            mem=max([r['pi_mem_max'] or 0 for r in b]), pit=max([r['pi_temp_max'] or 0 for r in b]),
            thr=','.join(sorted({r['pi_throttled'] for r in b if r['pi_throttled']})) or '0x0',
            fc=mean([r['fc_load_pct'] for r in b])))

    def tr5(b):
        thr_ok = b['thr'] == '0x0'
        return (f"<tr><td>{b['span']}</td><td>{b['clock']}</td><td>{fmt(b['err'])} / {fmt(b['p95'])}</td><td>{fmt(b['tag'],0)}%</td>"
                f"<td>{fmt(b['alt'],2)} ±{fmt(b['altsd'])}</td><td>{b['resets']}</td><td>{fmt(b['hdg'])}°</td>"
                f"<td>{fmt(b['w'],0)} W · {fmt(b['v'],2)} V</td><td>{' / '.join(fmt(x,0) for x in b['rpm_m'])}</td>"
                f"<td>{fmt(b['esc'],0)} °C{' · err '+str(int(b['escerr'])) if b['escerr'] else ''}</td>"
                f"<td>{fmt(b['cpu'],0)}% (max {fmt(b['cpumax'],0)}) · {fmt(b['mem'],0)}% · {fmt(b['pit'],0)} °C"
                f"{'' if thr_ok else ' <span class=\"pill r\">throttled '+b['thr']+'</span>'}</td><td>{fmt(b['fc'],0)}%</td></tr>")

    def tr1(r):
        return (f"<tr><td>{r['flight_min']}</td><td>{r['clock']}</td><td>{fmt(r['err_mean_cm'])} / {fmt(r['err_p95_cm'])} / {fmt(r['err_max_cm'])}</td>"
                f"<td>{fmt(r['tag_visible_pct'],0)}%</td><td>{fmt(r['range_mean_m'],2)} ±{fmt(r['range_std_cm'])}</td><td>{int(r['hgt_resets'] or 0)}</td>"
                f"<td>{fmt(r['heading_drift_deg'])}°</td><td>{fmt(r['bat_w_mean'],0)} W</td><td>{' / '.join(fmt(x,0) for x in r['rpm_m'])}</td>"
                f"<td>{fmt(r['esc_t_max'],0)} °C</td><td>{fmt(r['pi_cpu_mean'],0)}% · {fmt(r['pi_mem_max'],0)}% · {fmt(r['pi_temp_max'],0)} °C</td></tr>")

    P = lambda k: [(r['flight_min'], r[k]) for r in fl]
    charts = ''.join([
        chart('c-err', 'Distance off tag 0, minute mean', 'cm', P('err_mean_cm'), 1, 'camera-measured, frame center to tag center'),
        chart('c-alt', 'Height above floor', 'm', P('range_mean_m'), 2, 'rangefinder, minute mean'),
        chart('c-pwr', 'Power draw from tether', 'W', P('bat_w_mean'), 0),
        chart('c-esc', 'Hottest ESC', '°C', P('esc_t_max'), 0),
        chart('c-cpu', 'CM4 CPU, minute mean', '%', P('pi_cpu_mean'), 0, 'all 4 cores'),
        chart('c-pit', 'CM4 SoC temperature, minute max', '°C', P('pi_temp_max'), 0),
        chart_multi('c-rpm', 'Motor RPM, per motor', 'rpm',
                    [(f'M{i + 1}', MOTOR_COLORS[i], [(r['flight_min'], r['rpm_m'][i]) for r in fl]) for i in range(4)],
                    0, 'minute mean from ESC telemetry; diagonal pairs M1/M3 and M2/M4 share a spin direction'),
    ])

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    extra = (run / 'log_findings.html').read_text() if (run / 'log_findings.html').exists() else ''
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
{'<meta http-equiv="refresh" content="300">' if (run / 'LIVE').exists() else ''}
<title>DEXI-5 Endurance Hold</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{{--brand:#007aff;--navy:#003A5D;--cyan:#00A7E1;--ink:#1d1d1f;--ink-soft:#424245;--ink-faint:#6e6e73;
--paper:#ffffff;--mist:#f4f7fa;--line:#e3e8ee;--grid:#eef1f5;--good:#1B9E5A;--warn:#B86400;--bad:#C62828}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 Inter,-apple-system,system-ui,sans-serif}}
.head{{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:20px 16px 12px;max-width:1080px;margin:0 auto;border-bottom:1px solid var(--line)}}
.head .brand{{display:flex;align-items:center;gap:11px}}.head img{{height:24px;display:block}}
.head .tag{{font-size:10.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--navy);padding-left:11px;border-left:1px solid var(--line)}}.head .tag b{{color:var(--cyan)}}
.head .meta{{text-align:right;font-size:10px;font-weight:700;letter-spacing:.13em;text-transform:uppercase;color:var(--ink-faint);line-height:1.5}}.head .meta b{{color:var(--navy)}}
main{{max-width:1080px;margin:0 auto;padding:24px 16px 48px}}
.kicker{{font-size:11px;font-weight:800;letter-spacing:.115em;text-transform:uppercase;color:var(--brand)}}
h1{{font-size:34px;line-height:1.05;font-weight:900;letter-spacing:-.03em;color:var(--navy);margin:4px 0 6px}}
h2{{font-size:15px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--navy);margin:36px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--cyan)}}
.sub{{color:var(--ink-faint);margin:0 0 8px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:16px}}
.tile{{border:1px solid var(--line);border-top:3px solid var(--cyan);border-radius:8px;padding:12px 14px}}
.tile b{{display:block;font-size:26px;font-weight:900;color:var(--navy);letter-spacing:-.02em;font-variant-numeric:tabular-nums}}.tile span{{color:var(--ink-faint);font-size:13px}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
.chart{{margin:0;border:1px solid var(--line);border-radius:8px;padding:12px 14px 8px;position:relative}}
.chart figcaption{{font-size:13.5px;color:var(--ink)}}.chart figcaption b{{color:var(--navy)}}
.chart svg{{width:100%;height:170px;display:block;margin-top:6px;overflow:visible}}
.chart .axis{{font:11px Inter,sans-serif;fill:var(--ink-faint)}}.chart .gl{{stroke:var(--grid);stroke-width:1}}
.chart .ln{{fill:none;stroke:var(--navy);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}
.chart .xh{{stroke:var(--ink-faint);stroke-width:1;stroke-dasharray:3 3}}.chart .dot{{fill:var(--navy);stroke:var(--paper);stroke-width:2}}
.chart.wide{{grid-column:1/-1}}.chart.wide svg{{height:220px}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:4px;font-size:12.5px;color:var(--ink-soft)}}.lg i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
.chart .dl{{font:600 11.5px Inter,sans-serif;fill:var(--ink-soft)}}
.tip{{position:absolute;pointer-events:none;background:var(--paper);border:1px solid var(--line);border-radius:6px;padding:4px 8px;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);white-space:nowrap;font-variant-numeric:tabular-nums}}
.wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:8px}}
table{{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}}
th{{background:var(--navy);color:#fff;font-weight:700;font-size:11.5px;letter-spacing:.03em}}
tr:nth-child(even) td{{background:var(--mist)}}
.pill{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:700}}.r{{background:#fde7e7;color:var(--bad)}}
details summary{{cursor:pointer;color:var(--brand);font-weight:600;margin:8px 0}}
.muted{{color:var(--ink-faint);font-size:13px}}code{{font-family:"JetBrains Mono",monospace;background:var(--mist);border:1px solid var(--line);padding:0 5px;border-radius:4px;font-size:12.5px}}
ul.setup li{{margin-bottom:4px}}
.foot{{background:var(--navy);color:#fff;font-size:12px}}.foot div{{max-width:1080px;margin:0 auto;padding:12px 16px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.foot .site{{font-weight:800}}.foot b{{color:var(--cyan)}}
</style></head><body>
<header class="head"><div class="brand"><img src="droneblocks-logo.svg" alt="DroneBlocks"><span class="tag">Elevating <b>K thru Life</b></span></div>
<div class="meta">DEXI-5 · Endurance<br><b>Updated {now}</b></div></header>
<main>
<div class="kicker">Flight test · 24 V external supply</div>
<h1>DEXI-5 holds over an AprilTag{'' if (run / 'LIVE').exists() or not air else f' for {int(air // 3600)} h {int(air % 3600 // 60):02d} min'}</h1>
<p class="sub">Autonomous position hold over tag 0 in Offboard, started from the RC switch. Run started {start}; {len(fl)} full minutes in the hold{' so far. The page refreshes every 5 minutes' if (run / 'LIVE').exists() else ''}.</p>
<div class="tiles">{''.join(f'<div class="tile"><b>{v}</b><span>{l}</span></div>' for v, l in tiles)}</div>

<h2>Over the flight</h2>
<p class="muted">x-axis: minutes in the hold. Hover a chart for each minute's value.</p>
<div class="charts">{charts}</div>

<h2>Every 5 minutes</h2>
<div class="wrap"><table><thead><tr><th>Flight min</th><th>Clock</th><th>Tag error mean / p95 (cm)</th><th>Tag seen</th><th>Height (m) ±cm</th><th>Height resets</th><th>EKF heading drift</th><th>Power · min voltage</th><th>RPM M1 / M2 / M3 / M4</th><th>ESC max</th><th>CM4 CPU · mem · temp</th><th>FC load</th></tr></thead>
<tbody>{''.join(tr5(b) for b in blocks)}</tbody></table></div>

<details><summary>Every minute ({len(fl)} rows)</summary>
<div class="wrap"><table><thead><tr><th>Min</th><th>Clock</th><th>Tag error mean / p95 / max (cm)</th><th>Tag seen</th><th>Height (m) ±cm</th><th>Resets</th><th>EKF heading drift</th><th>Power</th><th>RPM M1 / M2 / M3 / M4</th><th>ESC max</th><th>CM4 CPU · mem · temp</th></tr></thead>
<tbody>{''.join(tr1(r) for r in fl)}</tbody></table></div></details>

{extra}<h2>Setup</h2>
<ul class="setup">
<li><b>Aircraft:</b> DEXI-5 (ARK Pi6X + CM4), downward rangefinder and optical flow, no GPS, magnetometer off.</li>
<li><b>Power:</b> external power supply set to 24.0 V, tethered to the aircraft (about 23.9 V at the flight controller under load). No battery is fitted, so the voltage stays flat and the power figure is what holding a hover costs.</li>
<li><b>Hold:</b> the pilot flips CH7 to Offboard; <code>tag_nav</code> centers on tag 0, turns the nose to the tag's top edge, and holds, correcting from every detection.</li>
<li><b>Height:</b> rangefinder is the EKF height reference with the barometer as a backup (<code>EKF2_HGT_REF 2</code>, <code>EKF2_BARO_CTRL 1</code>). With the barometer off, the EKF reset its height every 5 s and the aircraft bobbed 0.2–0.3 m.</li>
<li><b>Heading:</b> the EKF heading drifts slowly without a magnetometer; the tag holds the real heading, so EKF heading drift here is not aircraft rotation.</li>
<li><b>Logging:</b> 1 Hz on the CM4, one summary per minute. Tag error is the camera-measured distance from the frame center to the tag center.</li>
</ul>
</main>
<footer class="foot"><div><span class="site">droneblocks.io</span><span>Build · Fly · <b>Code</b></span></div></footer>
<script>
for (const fig of document.querySelectorAll('.chart[data-pts]')) {{
  const pts = JSON.parse(fig.dataset.pts), unit = fig.dataset.unit, d = +fig.dataset.d;
  const svg = fig.querySelector('svg'), tip = fig.querySelector('.tip');
  if (!pts.length) {{ svg.outerHTML = '<p class="muted">No data yet.</p>'; continue; }}
  const W = svg.clientWidth || 480, H = 170, L = 40, R = 10, T = 8, B = 22;
  svg.setAttribute('viewBox', `0 0 ${{W}} ${{H}}`);
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (unit === 'cm' || unit === 'W' || unit === '%') y0 = 0;
  const pad = (y1 - y0) * 0.15 || Math.abs(y1) * 0.1 || 1; y1 += pad; if (y0 !== 0) y0 -= pad;
  const x0 = Math.min(...xs), x1 = Math.max(...xs, x0 + 1);
  const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const step = (() => {{ const r = (y1 - y0) / 4, m = Math.pow(10, Math.floor(Math.log10(r))); return [1, 2, 2.5, 5, 10].map(k => k * m).find(k => k >= r); }})();
  let g = '';
  for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step)
    g += `<line class="gl" x1="${{L}}" x2="${{W - R}}" y1="${{Y(v)}}" y2="${{Y(v)}}"/><text class="axis" x="${{L - 6}}" y="${{Y(v) + 4}}" text-anchor="end">${{+v.toFixed(2)}}</text>`;
  const xstep = Math.max(1, Math.ceil((x1 - x0) / 6 / 5) * 5);
  for (let v = Math.ceil(x0 / xstep) * xstep; v <= x1; v += xstep)
    g += `<text class="axis" x="${{X(v)}}" y="${{H - 4}}" text-anchor="middle">${{v}}</text>`;
  const path = pts.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join('');
  const last = pts[pts.length - 1];
  svg.innerHTML = g + `<path class="ln" d="${{path}}"/><circle class="dot" r="4" cx="${{X(last[0])}}" cy="${{Y(last[1])}}"/>
    <line class="xh" y1="${{T}}" y2="${{H - B}}" visibility="hidden"/><circle class="dot hv" r="4" visibility="hidden"/>
    <rect x="${{L}}" y="0" width="${{W - L - R}}" height="${{H}}" fill="transparent"/>`;
  const xh = svg.querySelector('.xh'), hv = svg.querySelector('.hv');
  svg.addEventListener('mousemove', e => {{
    const r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * W / r.width;
    let best = pts[0]; for (const p of pts) if (Math.abs(X(p[0]) - mx) < Math.abs(X(best[0]) - mx)) best = p;
    xh.setAttribute('x1', X(best[0])); xh.setAttribute('x2', X(best[0])); xh.setAttribute('visibility', 'visible');
    hv.setAttribute('cx', X(best[0])); hv.setAttribute('cy', Y(best[1])); hv.setAttribute('visibility', 'visible');
    tip.hidden = false; tip.innerHTML = `min ${{best[0]}} · <b>${{best[1].toFixed(d)}} ${{unit}}</b>`;
    const px = X(best[0]) * r.width / W; tip.style.left = Math.min(px + 14, r.width - 120) + 'px'; tip.style.top = '36px';
  }});
  svg.addEventListener('mouseleave', () => {{ xh.setAttribute('visibility', 'hidden'); hv.setAttribute('visibility', 'hidden'); tip.hidden = true; }});
}}

for (const fig of document.querySelectorAll('.chart[data-series]')) {{
  const ser = JSON.parse(fig.dataset.series).filter(s => s[2].length), unit = fig.dataset.unit;
  const svg = fig.querySelector('svg'), tip = fig.querySelector('.tip');
  if (!ser.length) {{ svg.outerHTML = '<p class="muted">No data yet.</p>'; continue; }}
  const W = svg.clientWidth || 900, H = 220, L = 48, R = 44, T = 8, B = 22;
  svg.setAttribute('viewBox', `0 0 ${{W}} ${{H}}`);
  const all = ser.flatMap(s => s[2]), xs = all.map(p => p[0]), ys = all.map(p => p[1]);
  let y0 = Math.min(...ys), y1 = Math.max(...ys); const pad = (y1 - y0) * 0.12 || 50; y0 -= pad; y1 += pad;
  const x0 = Math.min(...xs), x1 = Math.max(...xs, x0 + 1);
  const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
  const step = (() => {{ const r = (y1 - y0) / 4, m = Math.pow(10, Math.floor(Math.log10(r))); return [1, 2, 2.5, 5, 10].map(k => k * m).find(k => k >= r); }})();
  let g = '';
  for (let v = Math.ceil(y0 / step) * step; v <= y1; v += step)
    g += `<line class="gl" x1="${{L}}" x2="${{W - R}}" y1="${{Y(v)}}" y2="${{Y(v)}}"/><text class="axis" x="${{L - 6}}" y="${{Y(v) + 4}}" text-anchor="end">${{(+v).toLocaleString()}}</text>`;
  const xstep = Math.max(1, Math.ceil((x1 - x0) / 8 / 5) * 5);
  for (let v = Math.ceil(x0 / xstep) * xstep; v <= x1; v += xstep)
    g += `<text class="axis" x="${{X(v)}}" y="${{H - 4}}" text-anchor="middle">${{v}}</text>`;
  // direct labels at line ends, nudged apart so they never overlap
  const ends = ser.map(s => {{ const p = s[2][s[2].length - 1]; return {{n: s[0], y: Y(p[1])}}; }}).sort((a, b) => a.y - b.y);
  for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 13) ends[i].y = ends[i - 1].y + 13;
  for (const s of ser) {{
    const d = s[2].map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join('');
    g += `<path d="${{d}}" fill="none" stroke="${{s[1]}}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
  }}
  for (const e of ends) g += `<text class="dl" x="${{W - R + 6}}" y="${{e.y + 4}}">${{e.n}}</text>`;
  g += `<line class="xh" y1="${{T}}" y2="${{H - B}}" visibility="hidden"/><rect x="${{L}}" y="0" width="${{W - L - R}}" height="${{H}}" fill="transparent"/>`;
  svg.innerHTML = g;
  const xh = svg.querySelector('.xh');
  svg.addEventListener('mousemove', e => {{
    const r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * W / r.width;
    let best = xs[0]; for (const x of xs) if (Math.abs(X(x) - mx) < Math.abs(X(best) - mx)) best = x;
    xh.setAttribute('x1', X(best)); xh.setAttribute('x2', X(best)); xh.setAttribute('visibility', 'visible');
    tip.hidden = false;
    tip.innerHTML = `min ${{best}}<br>` + ser.map(s => {{ const p = s[2].find(q => q[0] === best); return `<i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${{s[1]}};margin-right:5px"></i>${{s[0]}} <b>${{p ? Math.round(p[1]).toLocaleString() : '–'}}</b>`; }}).join('<br>');
    const px = X(best) * r.width / W; tip.style.left = Math.min(px + 14, r.width - 130) + 'px'; tip.style.top = '40px';
  }});
  svg.addEventListener('mouseleave', () => {{ xh.setAttribute('visibility', 'hidden'); tip.hidden = true; }});
}}
</script>
</body></html>'''
    (run / 'report.html').write_text(page)
    if LOGO.exists() and not (run / 'droneblocks-logo.svg').exists():
        shutil.copy(LOGO, run / 'droneblocks-logo.svg')
    return run / 'report.html', len(fl)


if __name__ == '__main__':
    out, n = build(Path(sys.argv[1]).expanduser())
    print(out, n, 'minutes')

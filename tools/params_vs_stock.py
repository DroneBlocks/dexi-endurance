#!/usr/bin/env python3
"""List PX4 parameters in a flight log that differ from the stock airframe.

    tools/params_vs_stock.py <log.ulg> <px4-checkout> [--board ark/pi6x] [--airframe 4601_droneblocks_dexi_5]

Stock = PX4 defaults (from the log) + the board's rc.board_defaults + rc.mc_defaults + the airframe
file, all read from <px4-checkout> at the firmware commit recorded in the log. Values are at boot.
Calibration, sensor IDs and SYS_AUTOSTART are left out; radio, flight-mode and motor-output
setup is left out unless --all. Needs pyulog and git.
"""
import argparse, re, subprocess
from pyulog import ULog

SKIP = re.compile(r'^(CAL_|SENS_.*_ID$|LND_FLIGHT_T|COM_FLIGHT_UUID|SYS_AUTOCONFIG|SYS_AUTOSTART|TC_|RC\d+_(MIN|MAX|TRIM)$|SENS_BOARD_[XY]_OFF)')
# Per-aircraft QGroundControl setup (radio, flight modes, motor outputs); shown with --all.
SETUP = re.compile(r'^(RC_MAP_(?!OFFB_SW)|RC_CHAN_CNT|COM_FLTMODE|MAN_ARM_GESTURE|PWM_MAIN_(FUNC|MIN|MAX)\d)')

ap = argparse.ArgumentParser()
ap.add_argument('ulog'); ap.add_argument('px4')
ap.add_argument('--all', action='store_true', help='include radio, flight-mode and motor-output setup')
ap.add_argument('--board', default='ark/pi6x'); ap.add_argument('--airframe', default='4601_droneblocks_dexi_5')
a = ap.parse_args()

u = ULog(a.ulog, [])
commit = u.msg_info_dict.get('ver_sw', '')[:10]
files = [f'boards/{a.board}/init/rc.board_defaults', 'ROMFS/px4fmu_common/init.d/rc.mc_defaults',
         f'ROMFS/px4fmu_common/init.d/airframes/{a.airframe}']
stock = {}
for f in files:                                    # later files override earlier ones, as at boot
    text = subprocess.run(['git', '-C', a.px4, 'show', f'{commit}:{f}'], capture_output=True, text=True, check=True).stdout
    for line in text.splitlines():
        m = re.match(r'\s*param set-default\s+(\S+)\s+(\S+)', line)
        if m:
            stock[m[1]] = float(m[2])
system = u.get_default_parameters(0)

rows = []
for k, v in sorted(u.initial_parameters.items()):
    base = stock.get(k, system.get(k))
    if base is not None and abs(float(v) - float(base)) > 1e-6 and not SKIP.match(k) and (a.all or not SETUP.match(k)):
        rows.append((k, v, base, 'airframe' if k in stock else 'PX4'))

fmt = lambda x: str(int(x)) if float(x).is_integer() else f'{x:.4g}'
print(f'firmware {commit}, airframe {a.airframe}: {len(rows)} parameters differ from stock\n')
print('| Parameter | Flown | Stock | Stock from |\n|---|---|---|---|')
for k, v, b, src in rows:
    print(f'| `{k}` | {fmt(v)} | {fmt(b)} | {src} |')

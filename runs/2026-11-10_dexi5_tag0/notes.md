# 2026-11-10 · DEXI-5 · tag 0 hold · 4 h 04 min

| | |
|---|---|
| Airframe | DEXI-5, ARK Pi6X + CM4 (`sys_uuid` …0500240044) |
| PX4 firmware | `54f0455f` |
| Power | external power supply set to 24.0 V, tethered; 23.9 V at the flight controller in the hold |
| Tag | tag36h11 ID 0, 6 in print, on the floor |
| `tag_nav` | `align_yaw` on, `hold_route_altitude` on, config `airframes/tag_nav_dexi5.yaml` |
| PX4 parameters | profile values in `airframes/dexi5.yaml`, all checked `ok` by `tools/preflight.sh` before the run |
| Armed | 18:36:17 to 22:40:27 companion clock, **4 h 04 min 10 s** |
| In the Offboard hold | 18:36:31 to 22:40:17, **4 h 03 min 46 s** |
| How it ended | pilot switched CH7 back to Position and landed |

## Results

| Measure | Value |
|---|---|
| Tag error, mean / median | 8.4 / 7.8 cm |
| Tag error, p95 / p99 / max | 16.5 / 20.9 / 34.4 cm |
| Time within 10 cm / 20 cm of the tag center | 68% / 98.7% |
| Height, mean over the hold | 1.25 m, ±0.7 cm minute to minute |
| EKF height resets in the hold | 0 |
| Power, mean | 186 W |
| Energy used | 755 Wh |
| ESC temperature, max | 51 °C (first minutes), 47–49 °C settled; 0 ESC errors |
| Motor RPM | M1/M3 about 10.4k, M2/M4 about 9.8k, each within 1.5% over the run |
| CM4 | 46 °C max, 65% mean CPU (includes about 17% for the logger), 31% memory max, never throttled |

Every measure was flat from about 20 minutes in to the end of the run.

## Flight controller log

| Check | Result |
|---|---|
| Vibration | accel p95 2.2 m/s², gyro p95 0.07 rad/s, 0 clipping on both IMUs |
| Motor margin | no motor reached its limit |
| Attitude tracking | 0.5° error |
| Height estimate | innovation test ratio p95 0.01; rangefinder healthy 100% of the flight |
| Flight modes | Position, then Offboard to the end of the log; failsafe flag never set |
| Hover throttle | measured 0.16 against `MPC_THR_HOVER 0.22`; the hover-thrust estimator corrected for it |
| Accelerometer bias | X and Y at −0.34 m/s² at takeoff, 85% of the 0.4 limit; Y walked to +0.11 over the run |
| Battery estimate | reached 0% at about 45 min (26.7 Ah counted against a 4.0 Ah pack); warnings only, because `COM_LOW_BAT_ACT 0` |

## Files

- `minutes.csv`, `samples.csv`: companion logger, full flight.
- `report.html`: built with `tools/build_report.py`.
- Flight controller ULog: GitHub release `run-2026-11-10-dexi5-tag0`. It covers takeoff to
  3 h 34 min, where the file reached the 2 GB ULog size limit; the companion logger covers
  the whole flight.

## For the next run

- Recalibrate the accelerometer on a level surface: the learned bias starts at 85% of its limit.
- Set `BAT1_CAPACITY -1` for tethered runs so the battery estimate follows voltage, not counted charge.
- Set `MPC_THR_HOVER 0.16` to match the measured hover throttle.

- The ULog stops at 2 GB. For runs longer than about 3.5 h, log fewer topics
  (`SDLOG_PROFILE`) or start a new log partway through, so the flight controller covers the
  whole flight.
- `params.txt` was not captured for this run (the aircraft was powered off before the dump).
  Capture it before power-off: `tools/params.py dump airframes/dexi5.yaml > params.txt`.

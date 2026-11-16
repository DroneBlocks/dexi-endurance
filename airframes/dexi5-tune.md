# DEXI-5 tune, 2026-11-13

PX4 1.16 autotune (`MC_AT_EN 1`, `MC_AT_APPLY 1`) on a DEXI-5 (ARK Pi6X) flying a 6S 4000 mAh
Li-ion pack strapped tight, flow and rangefinder only, hovering in Position at about 1.5 m.
Only the parameters that differ from the stock `4601_droneblocks_dexi_5` airframe are listed.

## Attitude and rate gains

| Parameter | Stock 4601 | Autotuned | Change |
|---|---|---|---|
| `MC_ROLLRATE_P` | 0.095 | 0.0498 | -48% |
| `MC_ROLLRATE_I` | 0.165 | 0.0679 | -59% |
| `MC_PITCHRATE_P` | 0.105 | 0.0482 | -54% |
| `MC_PITCHRATE_I` | 0.185 | 0.0588 | -68% |
| `MC_PITCHRATE_D` | 0.0013 | 0.0005 | -62% |
| `MC_YAWRATE_P` | 0.13 | 0.0808 | -38% |
| `MC_YAWRATE_I` | 0.35 | 0.0868 | -75% |
| `MC_YAWRATE_D` | 0 | 0.0001 | new |
| `MC_ROLL_P` | 7.5 | 6.5 | PX4 default |
| `MC_PITCH_P` | 7.5 | 6.5 | PX4 default |

Unchanged: `MC_ROLLRATE_D` 0.0010, all `_FF` 0, all `_K` 1.

Result, hands-off hover, gyro standard deviation (deg/s):

| | Roll | Pitch |
|---|---|---|
| Stock gains, battery strapped | 2.0 | 3.7 |
| `MC_PITCHRATE_P` 0.09 | 2.0 | 2.8 |
| Autotuned | 1.4 | 2.0 |
| Stock gains, tethered (about 400 g lighter) | 2.7 | 1.9 |

The tag_nav hold swing (30-55 cm peak to peak over a 10 s hold) did not change with the tune; it
comes from tag_nav's hold-point nudge, not the attitude loops.

## Battery (6S Li-ion)

| Parameter | Before | Now | Why |
|---|---|---|---|
| `BAT1_V_EMPTY` | 3.30 | 3.20 | PX4's 0% point, per cell, sag-corrected. At 3.30 the pack read 0% at the 3.33 V resting stop |
| `BAT1_V_CHARGED` | 4.05 | 4.15 | A charged Li-ion pack rests near 4.15-4.2 V |

## Before these go into the airframe file

The airframe defaults live in PX4 (`ROMFS/px4fmu_common/init.d/airframes/4601_droneblocks_dexi_5`);
QGroundControl only loads them. One aircraft and one pack is not enough to change every DEXI-5:
repeat the autotune on a second DEXI-5 with the standard pack and compare first.

Not airframe settings: the RC stick centers (`RC1_TRIM` 1441, `RC2_TRIM` 1485, `RC4_TRIM` 1472)
belong to this radio. The radio had never been calibrated, and a 59 us roll offset made autotune
abort at once (it treats more than 5% stick as the pilot taking over). Calibrate the radio before
running autotune.

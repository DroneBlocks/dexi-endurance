# Test setup

## Power

- External power supply set to **24.0 V**, tethered to the aircraft. No flight battery fitted.
- The flight controller reads about 23.9 V under hover load at the DEXI-5's ~186 W draw.
- Run the tether so it hangs clear of the props and the downward sensors, with enough slack for
  the aircraft to wander ±0.3 m without pulling it.
- PX4 still runs its battery estimator on the supply. `COM_LOW_BAT_ACT 0` keeps the estimated
  charge from triggering a failsafe as consumed mAh pass the configured pack capacity.

## Tag and room

- AprilTag **tag36h11, ID 0, printed at 6 in** (the black square, edge to edge). The detector
  is configured for 0.1524 m; a different print size skews the height and distance to the tag.
- Tag flat on the floor, under even lighting with no glare on the print.
- Floor around the tag flat and plain for about 1 m, so the rangefinder and optical flow read
  the floor and not furniture or the tether.
- Hold height about 1.2 m. At that height the camera sees the tag with margin for the wander.

## Aircraft

### DEXI-5

- ARK Pi6X flight controller, CM4 companion, downward rangefinder and optical flow, no GPS.
- Camera mount: lens 105 mm ahead of the frame center on the centerline, axes aligned with the
  body (`airframes/tag_nav_dexi5.yaml`).
- Firmware and `tag_nav` version are recorded per run in `notes.md`.

### DEXI-3

Not flown yet. Before the first run, fill in the `TODO` fields in `airframes/dexi3.yaml`:
the host name, the power set point, and a `tag_nav_dexi3.yaml` with the camera mount offsets
measured on the aircraft (tape from the lens center to the frame center, then confirm that the
raw tag offset reads near zero with the tag centered in the image).

## PX4 parameters

The parameters the test depends on are listed in each airframe profile and checked by
`tools/params.py check`. Why each one matters:

| Parameter | Value | Why |
|---|---|---|
| `RC_MAP_OFFB_SW` | 7 | CH7 high enters Offboard, which starts the hold |
| `EKF2_HGT_REF` | 2 | rangefinder is the height reference: centimeter height over a flat floor |
| `EKF2_RNG_CTRL` | 2 | always fuse the rangefinder |
| `EKF2_BARO_CTRL` | 1 | barometer as a backup height source. At 0, with the rangefinder as reference, the EKF resets its height every 5 s and each reset kicks the aircraft up 0.2–0.3 m |
| `EKF2_OF_CTRL` | 1 | optical flow fusion |
| `EKF2_MAG_TYPE` | 5 | magnetometer off; the tag provides the heading |
| `COM_LOW_BAT_ACT` | 0 | battery warnings only, no failsafe action (tethered runs) |
| `COM_FLT_TIME_MAX` | -1 | no flight-time limit |

## Companion software

- DEXI OS with `dexi_apriltag`'s `tag_nav` node running from the bringup (`tag_nav.enabled`).
- `tag_nav` needs two options: yaw alignment (`align_yaw`, dexi_apriltag branch
  `feat/tag-nav-align-yaw`) and one held height for the whole hold (`hold_route_altitude`).
  Both are set in `airframes/tag_nav_dexi5.yaml`. A `tag_nav` without them ignores the keys,
  so check `ros2 param get /tag_nav align_yaw` (preflight does).
- Restarting the DEXI stack (`systemctl restart dexi`) can leave PX4's DDS client
  disconnected from the restarted micro-ROS agent: no `/fmu/out` topics, and the LED ring
  stops showing the flight mode. Power cycling the aircraft reconnects it. `tools/preflight.sh`
  checks for this.

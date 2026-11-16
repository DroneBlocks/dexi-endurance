# Test setup

## Power

- External power supply set to **24.0 V**, tethered to the aircraft. No flight battery fitted.
- The flight controller reads about 23.9 V under hover load at the DEXI-5's ~186 W draw.
- Run the tether so it hangs clear of the props and the downward sensors, with enough slack for
  the aircraft to wander ±0.3 m without pulling it.
- PX4 still runs its battery estimator on the supply. `COM_LOW_BAT_ACT 0` keeps the estimated
  charge from triggering a failsafe as consumed mAh pass the configured pack capacity.

## Tag and room

- AprilTag **tag36h11, ID 0, black square 167 mm** edge to edge (measured 2026-11-13). The
  detector's `size` in the DEXI bringup launch file must match: a wrong size scales every tag
  distance and height by the same error (the 2026-11-10 run used 0.1524 m, so its tag error
  reads about 9% low).
- Tag flat on the floor, under even lighting with no glare on the print.
- Floor around the tag flat and plain for about 1 m, so the rangefinder and optical flow read
  the floor and not furniture or the tether.
- Hold height 1.5 m, the standard for every test so runs compare. At that height the camera sees the tag with margin for the wander.

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
| `EKF2_BARO_CTRL` | 1 | keep the barometer on. At 0, with the rangefinder as the only height source, PX4 1.16 resets the height every 5 s (range height fusion does not refresh the height timeout; fixed on PX4 main in `14da9d13b5`, not in a release yet) |
| `EKF2_BARO_NOISE` | 15 | weight the barometer as little as possible. Prop wash makes it read up to 5 m high at liftoff and ~2.8 m high in hover; at the stock 3.5 the EKF height follows it and an `offboard_takeoff` to 1.5 m stopped at a real 0.8 m |
| `EKF2_TERR_NOISE` | 0.5 | keep the floor estimate steady so the rangefinder corrects the height instead of moving the floor. With this and `EKF2_BARO_NOISE 15`, an EKF replay of the 2026-11-10 log cut the takeoff height error from 1.58 m to 0.18 m, and the next flight reached 1.52 m on the rangefinder for a 1.5 m takeoff |
| `EKF2_OF_CTRL` | 1 | optical flow fusion |
| `EKF2_MAG_TYPE` | 5 | magnetometer off; the tag provides the heading |
| `COM_LOW_BAT_ACT` | 0 | battery warnings only, no failsafe action (tethered runs) |
| `COM_FLT_TIME_MAX` | -1 | no flight-time limit |
| `COM_ARM_WO_GPS` | 1 | arm without GPS. A GPS flight can leave it at 0, which denies arming ("Global position estimate required") |
| `SYS_HAS_GPS`, `EKF2_GPS_CTRL` | 0 | no GPS |
| `SDLOG_MODE` | 2 | log from boot. A log that starts at arming replays poorly, because the replayed EKF starts cold mid-flight |

## Companion software

- DEXI OS with `dexi_apriltag`'s `tag_nav` node running from the bringup (`tag_nav.enabled`).
- `tag_nav` needs two options: yaw alignment (`align_yaw`, dexi_apriltag branch
  `feat/tag-nav-align-yaw`) and one held height for the whole hold (`hold_route_altitude`).
  Both are set in `airframes/tag_nav_dexi5.yaml`. A `tag_nav` without them ignores the keys,
  so check `ros2 param get /tag_nav align_yaw` (preflight does).
- Two edits to the DEXI bringup launch file on the aircraft (`dexi_bringup_ark_cm4.launch.py`,
  originals kept beside it): the AprilTag `size` set to the tag (0.167), and the camera throttle
  that feeds the detector raised from 10 to 20 Hz, so the detector runs at ~15 Hz in flight
  (every second camera frame) instead of ~8 Hz.
- Restarting the DEXI stack (`systemctl restart dexi`) can leave PX4's DDS client
  disconnected from the restarted micro-ROS agent: no `/fmu/out` topics, and the LED ring
  stops showing the flight mode. Power cycling the aircraft reconnects it. `tools/preflight.sh`
  checks for this.

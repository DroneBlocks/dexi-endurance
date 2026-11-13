# DEXI endurance

Repeatable long-duration hover tests for DEXI aircraft. The aircraft runs on an external
power supply and holds position over an AprilTag in Offboard until the pilot takes it back.
The companion computer logs performance once a second and writes a summary every minute,
and a report is built from those summaries.

The goal of a run is time in the hold with nothing degrading: tag error, height, motor RPM,
ESC and companion temperatures, and companion CPU and memory should all stay flat.

## Results

| Run | Airframe | Power | Time in hold | Tag error mean / p95 | Height hold | Report |
|---|---|---|---|---|---|---|
| [2026-11-10](runs/2026-11-10_dexi5_tag0/) | DEXI-5 | 24 V external supply | **4 h 03 min** | 8.4 / 16.5 cm | 1.25 m ±0.7 cm, 0 resets | [report](runs/2026-11-10_dexi5_tag0/report.html) |

Next target: 6 hours on the DEXI-5.

## Running a test

Needs `sshpass`, and Python with `pymavlink` and `PyYAML` on the laptop.

1. Set up the aircraft and room as described in [SETUP.md](SETUP.md).
2. Check the PX4 parameters the test depends on, and fix any `FAIL`:
   ```bash
   tools/params.py check airframes/dexi5.yaml
   ```
3. With the aircraft on the ground and disarmed, install and start the test:
   ```bash
   drone/install.sh airframes/dexi5.yaml
   ```
4. Run the preflight. Every line must read `ok`:
   ```bash
   tools/preflight.sh airframes/dexi5.yaml
   ```
5. Take off in Position mode with tag 0 in the camera's view at 1.5 m. Flip CH7 to
   Offboard: the aircraft centers on the tag, turns its nose to the tag's top edge, and holds.
   Flip CH7 back to take control at any time; flip it again to re-engage.
6. During the run, copy the logs to the laptop and build the report:
   ```bash
   rsync -az dexi@<host>:/home/dexi/endurance/ runs/incoming/
   python3 tools/build_report.py runs/incoming/<start>
   ```
7. After landing, record the run (see [Recording a run](#recording-a-run)).

## Auto takeoff and land cycle

`drone/tag_cycle.py` flies one cycle per CH7 flip: take off to 1.5 m, center on tag 0, hover
10 s, land straight down on the tag. Install it in place of the hold hand-off:

```bash
HANDOFF=tag_cycle.py drone/install.sh airframes/dexi5.yaml
```

Arm in Position on the ground near the tag and flip CH7. For the next cycle, flip CH7 back to
Position, re-arm and flip again. Flip back at any time to take over; the sticks do not override
Offboard. It needs the EKF settings in `airframes/dexi5.yaml`: with the stock barometer weighting
the EKF height runs ~1.5 m ahead of the real height during the climb (see SETUP.md).

First cycle, 2026-11-13: takeoff 1.49 m in 6.8 s, centered within 6 cm in 4 s, 10 s hold at
2 cm, landed 6 s later, 27 s in all.

## Flight bags

`drone/flight_bag.py` records one ROS 2 bag (MCAP) per flight on the companion, from arm to 5 s
after disarm, in `/home/dexi/flight_bags/<arm time>/`: the tag camera, detections, `tag_nav`
status and setpoints, PX4 state and pilot sticks, about 2 GB per hour. A paused recorder waits
while disarmed, so the bag starts at arm with no startup delay. `tools/bag_video.py` renders a
bag's camera to MP4 with the detection and flight state drawn on.

## Recording a run

Each run gets a folder `runs/<date>_<airframe>_<name>/` with:

| File | What it is |
|---|---|
| `minutes.csv` | one row per minute: tag error, height, power, RPM, temperatures, CPU, memory |
| `samples.csv` | one row per second, every field the logger reads |
| `report.html` | built by `tools/build_report.py` |
| `params_vs_stock.md` | PX4 parameters that differ from the stock airframe, read from the flight controller log |
| `notes.md` | airframe, firmware, `tag_nav` version, power set point, room, who flew, how it ended |

The flight controller's ULog is too large for the repository. It is attached to a GitHub
release named after the run, and `notes.md` links to it.

## What is in here

| Path | Purpose |
|---|---|
| `airframes/<airframe>.yaml` | per-aircraft profile: host name, `tag_nav` config, power, required PX4 parameters |
| `airframes/tag_nav_<airframe>.yaml` | `tag_nav` parameters as flown, including the camera mount offsets |
| `drone/ch7_center_tag0.py` | waits for CH7 to enter Offboard, then centers on tag 0 and holds until Offboard is left |
| `drone/endurance_logger.py` | 1 Hz samples and a one-minute summary, written on the companion |
| `drone/flight_bag.py` | one ROS 2 bag (MCAP) per flight, arm to disarm: tag camera, detections, `tag_nav` setpoints, PX4 state, sticks, IMU |
| `drone/hgt_watch.py` | 5 Hz EKF height against the rangefinder, with every EKF height-source change logged |
| `drone/tag_cycle.py` | one auto takeoff, center, hover, land cycle per CH7 flip (`--now` runs one without CH7; not flown yet) |
| `drone/install.sh` | copies the above to the aircraft and starts them; `HANDOFF=<script>` picks the CH7 script |
| `tools/params.py` | dumps or checks PX4 parameters over MAVLink |
| `tools/params_vs_stock.py` | lists the parameters in a flight log that differ from the stock airframe (needs a PX4 checkout) |
| `tools/reboot_fc.py` | reboots the flight controller only (refuses if armed); `install.sh` runs it to reconnect PX4 to ROS |
| `tools/preflight.sh` | parameter check plus companion checks: services, PX4 data, `tag_nav` state, logger |
| `tools/bag_video.py` | camera video from a flight bag, with the tag outline and flight state drawn on |
| `tools/build_report.py` | builds `report.html` from a run's `minutes.csv` and `samples.csv` |

## Notes on the numbers

- **Tag error** is the camera-measured distance from the frame center to the tag center, so
  it is the aircraft's real position error. EKF position is logged too, but it drifts without
  an absolute reference and is not the measure of the hold.
- **EKF heading drift** grows steadily on an aircraft with the magnetometer off. The tag holds
  the real heading, so this column is not aircraft rotation.
- **CM4 CPU** is the mean across all four cores, so 100% means every core is busy. The logger
  itself uses about 17% of the CM4, which is included in the figure.
- **Height resets** counts EKF height resets per minute. It should be 0 in the hold; a reset
  every 5 s means the barometer is off with the rangefinder as height reference.
- **Flight controller logs stop at 2 GB per file.** With `SDLOG_PROFILE 2067` that is about
  3.5 h of flight: the ULog ends mid-flight and the rest goes unrecorded. The companion logger
  is not affected. For runs longer than about 3.5 h, lower `SDLOG_PROFILE` before takeoff so
  the whole flight fits in one ULog, and clear old logs from the SD card first.

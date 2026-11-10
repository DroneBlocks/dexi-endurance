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
| [2026-11-10](runs/2026-11-10_dexi5_tag0/) | DEXI-5 | 24 V external supply | in progress | 8.4 / 16.5 cm | 1.24 m ±0.6 cm | [report](runs/2026-11-10_dexi5_tag0/report.html) |

Next target: 4 hours on the DEXI-5.

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
5. Take off in Position mode with tag 0 in the camera's view at about 1.2 m. Flip CH7 to
   Offboard: the aircraft centers on the tag, turns its nose to the tag's top edge, and holds.
   Flip CH7 back to take control at any time; flip it again to re-engage.
6. During the run, copy the logs to the laptop and build the report:
   ```bash
   rsync -az dexi@<host>:/home/dexi/endurance/ runs/incoming/
   python3 tools/build_report.py runs/incoming/<start>
   ```
7. After landing, record the run (see [Recording a run](#recording-a-run)).

## Recording a run

Each run gets a folder `runs/<date>_<airframe>_<name>/` with:

| File | What it is |
|---|---|
| `minutes.csv` | one row per minute: tag error, height, power, RPM, temperatures, CPU, memory |
| `samples.csv` | one row per second, every field the logger reads |
| `report.html` | built by `tools/build_report.py` |
| `params.txt` | every PX4 parameter as flown: `tools/params.py dump airframes/<airframe>.yaml` |
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
| `drone/hgt_watch.py` | 5 Hz EKF height against the rangefinder, with every EKF height-source change logged |
| `drone/install.sh` | copies the above to the aircraft and starts them |
| `tools/params.py` | dumps or checks PX4 parameters over MAVLink |
| `tools/preflight.sh` | parameter check plus companion checks: services, PX4 data, `tag_nav` state, logger |
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

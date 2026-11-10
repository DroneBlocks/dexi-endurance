# Parameters as flown, against stock DEXI-5

Read from the flight controller log (values at boot). Stock means PX4's defaults with the ARK Pi6X board defaults and the DEXI-5 airframe file (`4601_droneblocks_dexi_5`) applied, at firmware `54f0455`. Left out: calibration values and sensor IDs, and the per-aircraft radio, flight-mode and motor-output setup that every DEXI-5 does in QGroundControl.

**14 parameters differ from the stock DEXI-5 airframe.**

`EKF2_HGT_REF 2` and `EKF2_BARO_CTRL 1` are stock DEXI-5 values, so they do not appear below. The barometer must stay on (`EKF2_BARO_CTRL 1`): with it off, the EKF resets its height every 5 s.

## Indoor flight without GPS

The navigation setup this test depends on.

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `SYS_HAS_GPS` | 0 | 1 | no GPS fitted |
| `EKF2_GPS_CTRL` | 0 | 7 | GPS fusion off |
| `EKF2_MAG_TYPE` | 5 | 0 | magnetometer off; the tag holds the heading |
| `EKF2_RNG_CTRL` | 2 | 1 | always fuse the rangefinder |
| `EKF2_MIN_RNG` | 0.15 | 0.01 | rangefinder reading on the ground |
| `EKF2_OF_QMIN` | 50 | 1 | optical-flow quality gate in the air |

## Endurance hand-off

What starts the hold.

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `RC_MAP_OFFB_SW` | 7 | 0 | CH7 high = Offboard; entering Offboard starts the tag hold |

## Logging

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `SDLOG_MODE` | 2 | 0 | log from boot until shutdown |
| `SDLOG_PROFILE` | 2067 | 1 | heavy topic set; fills the 2 GB ULog limit in about 3.5 h |

## Other

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `UXRCE_DDS_DOM_ID` | 2 | 0 | ROS 2 domain 2, matching the companion |
| `UAVCAN_ENABLE` | 2 | 0 | DroneCAN sensors and ESCs |
| `IMU_GYRO_FFT_EN` | 1 | 0 | gyro FFT notch filter |
| `MC_AT_EN` | 1 | 0 | autotune allowed |
| `SENS_IMU_AUTOCAL` | 0 | 1 | IMU auto-calibration off |

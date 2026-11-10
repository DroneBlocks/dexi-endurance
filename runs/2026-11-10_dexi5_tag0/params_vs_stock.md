# Parameters as flown, against stock DEXI-5

Read from the flight controller log (values at boot). Stock means PX4's defaults with the ARK Pi6X board defaults and the DEXI-5 airframe file (`4601_droneblocks_dexi_5`) applied, at firmware `54f0455`. Calibration values, sensor IDs and RC endpoint calibration are left out.

**39 parameters differ from stock.**

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

## Radio and modes

Transmitter setup.

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `RC_MAP_ROLL` | 1 | 0 |  |
| `RC_MAP_PITCH` | 2 | 0 |  |
| `RC_MAP_THROTTLE` | 3 | 0 |  |
| `RC_MAP_YAW` | 4 | 0 |  |
| `RC_MAP_ARM_SW` | 5 | 0 |  |
| `RC_MAP_KILL_SW` | 8 | 0 |  |
| `RC_MAP_FLTMODE` | 6 | 0 |  |
| `RC_CHAN_CNT` | 16 | 0 |  |
| `COM_FLTMODE1` | 8 | -1 |  |
| `COM_FLTMODE4` | 1 | -1 |  |
| `COM_FLTMODE6` | 2 | -1 |  |
| `MAN_ARM_GESTURE` | 0 | 1 |  |

## Motor outputs

ESC setup; the output order is rotated by one relative to motor numbering, which is correct for this frame.

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `PWM_MAIN_FUNC1` | 102 | 0 |  |
| `PWM_MAIN_FUNC2` | 103 | 0 |  |
| `PWM_MAIN_FUNC3` | 104 | 0 |  |
| `PWM_MAIN_FUNC4` | 101 | 0 |  |
| `PWM_MAIN_MIN1` | 1100 | 1000 |  |
| `PWM_MAIN_MIN2` | 1100 | 1000 |  |
| `PWM_MAIN_MIN3` | 1100 | 1000 |  |
| `PWM_MAIN_MIN4` | 1100 | 1000 |  |
| `PWM_MAIN_MAX1` | 1900 | 2000 |  |
| `PWM_MAIN_MAX2` | 1900 | 2000 |  |
| `PWM_MAIN_MAX3` | 1900 | 2000 |  |
| `PWM_MAIN_MAX4` | 1900 | 2000 |  |

## Logging

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `SDLOG_MODE` | 2 | 0 | log from boot until shutdown |
| `SDLOG_PROFILE` | 2067 | 1 | heavy topic set; fills the 2 GB ULog limit in about 3.5 h |

## Other

| Parameter | Flown | Stock | Why |
|---|---|---|---|
| `SYS_AUTOSTART` | 4601 | 0 | DEXI-5 airframe (4601) |
| `UXRCE_DDS_DOM_ID` | 2 | 0 | ROS 2 domain 2, matching the companion |
| `UAVCAN_ENABLE` | 2 | 0 | DroneCAN sensors and ESCs |
| `IMU_GYRO_FFT_EN` | 1 | 0 | gyro FFT notch filter |
| `MC_AT_EN` | 1 | 0 | autotune allowed |
| `SENS_IMU_AUTOCAL` | 0 | 1 | IMU auto-calibration off |

# PX4 EKF2 replay scripts (2026-11-12)

Replays DEXI-5 flight logs through EKF2 with changed parameters, to test height fixes without flying.

- `run_replay.sh <log.ulg> <name> [PARAM VALUE ...]`: one replay in `~/_dev/px4-replay`
- `series2.sh`, `series_stock.sh`: the 11-12 series on logs 492, 493 and the 4 h flight
- `score.py`: scores the replayed logs

Finding: `EKF2_BARO_CTRL 0` with `EKF2_HGT_REF 2` resets height every 5 s on PX4 1.16 (recorded in dexi-fc-params).

The 4 h flight log is kept compressed as `2026-11-10_183151/ulog/dexi5_2026-11-10_tag0-hold.ulg.zst`;
`zstd -d` it to `23_37_02.ulg` before running the series scripts. Paths assume the data folder
`~/_dev/dexi-endurance/`.

set -e
export LIMIT_S=660
L=$HOME/_dev/dexi-endurance/2026-11-10_183151/ulog/23_37_02.ulg
S=$HOME/_dev/dexi-endurance/2026-11-12_autotakeoff2/fc_log_493.ulg
A=$HOME/_dev/dexi-endurance/2026-11-12_autotakeoff1/fc_log_492.ulg
./run_replay.sh $L N_stock_baro0 EKF2_BARO_CTRL 0
./run_replay.sh $L N_opt1_baroweak EKF2_BARO_CTRL 1 EKF2_BARO_NOISE 15
./run_replay.sh $L N_opt1b_baroweak_terr EKF2_BARO_CTRL 1 EKF2_BARO_NOISE 15 EKF2_TERR_NOISE 0.5
LIMIT_S= ./run_replay.sh $A A_opt1_492 EKF2_BARO_CTRL 1 EKF2_BARO_NOISE 15
LIMIT_S= ./run_replay.sh $A A_opt1b_492 EKF2_BARO_CTRL 1 EKF2_BARO_NOISE 15 EKF2_TERR_NOISE 0.5
# option 2: upstream 14da9d13b5 (range height fusion refreshes the height-fusion timer)
cd $HOME/_dev/px4-replay
F=src/modules/ekf2/EKF/aid_sources/range_finder/range_height_fusion.cpp
grep -q "_time_last_hgt_fuse = _time_delayed_us" $F || perl -0pi -e 's/(\taid_src\.fused = true;\n)/$1\n\tif (update_height) {\n\t\t_time_last_hgt_fuse = _time_delayed_us;\n\t}\n/' $F
grep -n "_time_last_hgt_fuse" $F
export PATH=$PWD/.venv/bin:$PATH replay=$L replay_mode=ekf2
make px4_sitl_default > $HOME/_dev/dexi-endurance/replay-2026-11-12/fix_build.log 2>&1 < /dev/null &
B=$!; for i in $(seq 1 900); do grep -q "Linking CXX executable bin/px4\|ninja: no work" $HOME/_dev/dexi-endurance/replay-2026-11-12/fix_build.log && break; kill -0 $B 2>/dev/null || break; sleep 1; done
sleep 5; pkill -INT -f "px4_sitl_default_replay/bin/px4" || true; wait $B || true
cd $HOME/_dev/dexi-endurance/replay-2026-11-12
./run_replay.sh $L N_fix_baro0 EKF2_BARO_CTRL 0
LIMIT_S= ./run_replay.sh $S A_fix_493 EKF2_BARO_CTRL 0
LIMIT_S= ./run_replay.sh $A A_fix_492_baro0 EKF2_BARO_CTRL 0
echo SERIES_DONE

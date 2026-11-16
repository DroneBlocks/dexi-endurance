set -e
export LIMIT_S=300
L=$HOME/_dev/dexi-endurance/2026-11-10_183151/ulog/23_37_02.ulg
./run_replay.sh $L N_stock_baro1
./run_replay.sh $L N_stock_baro0 EKF2_BARO_CTRL 0
./run_replay.sh $L N_opt1_baroweak EKF2_BARO_CTRL 1 EKF2_BARO_NOISE 15
./run_replay.sh $L N_opt1b_baroweak_terr EKF2_BARO_CTRL 1 EKF2_BARO_NOISE 15 EKF2_TERR_NOISE 0.5
echo SERIES_DONE

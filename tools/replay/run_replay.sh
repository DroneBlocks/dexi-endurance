#!/usr/bin/env bash
# run_replay.sh <log.ulg> <name> [PARAM VALUE ...]  -> replay-2026-11-12/<name>.ulg
set -e
LOG=$1; NAME=$2; shift 2
OUT=$HOME/_dev/dexi-endurance/replay-2026-11-12
cd $HOME/_dev/px4-replay
export PATH=$PWD/.venv/bin:$PATH replay=$LOG replay_mode=ekf2
: > build/px4_sitl_default_replay/rootfs/replay_params.txt
while [ $# -gt 0 ]; do echo "$1 $2" >> build/px4_sitl_default_replay/rootfs/replay_params.txt; shift 2; done
make px4_sitl none < /dev/null > $OUT/$NAME.run.log 2>&1 &
MK=$!
if [ -n "$LIMIT_S" ]; then   # stop after LIMIT_S wall seconds (~6 s of log replayed per wall second)
  for i in $(seq 1 $LIMIT_S); do kill -0 $MK 2>/dev/null || break; sleep 1; done
  pkill -INT -f "px4_sitl_default_replay/bin/px4" || true; sleep 3; pkill -f "px4_sitl_default_replay/bin/px4" || true
fi
wait $MK || true
R=$(ls -t build/px4_sitl_default_replay/rootfs/log/*/*_replayed.ulg | head -1)
cp "$R" $OUT/$NAME.ulg; echo "$NAME <- $R"

#!/bin/sh

NB_MAPS=10
WIDTH=32
HEIGHT=32
for i in $( seq 0 $NB_MAPS )
do
  echo ""
  echo "Map number $i generated, size: $WIDTH * $HEIGHT, results will be generated below"
  ./halite --replay-directory replays/ -vvv --seed $i --width $WIDTH --height $HEIGHT "python3 MyBot.py" "python3 mathieuBot.py" 2>&1 >/dev/null | grep 'rank'
done

echo ""

#!/bin/bash

BENCHDIR=../../benchmarks/mem
files=(binary-search)

for i in "${files[@]}";
do
    echo "Reference"
    bril2json < $BENCHDIR/$i.bril | brili
    echo "Mine"
    bril2json < $BENCHDIR/$i.bril | python constant_folding.py | brili
done
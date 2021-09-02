#!/bin/bash

type nvidia-smi 1>/dev/null || exit 1

convert_utilization_hex() {
    declare -i ramp_size=16
    declare -i util="$1"

    printf "%X" "$((util/(100/ramp_size)))"
}
convert_utilization_hex \
    "$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)"

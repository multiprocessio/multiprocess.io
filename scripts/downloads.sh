#!/usr/bin/env bash

set -e

function count() {
    # TODO: paginate through results
    curl -s https://api.github.com/repos/multiprocessio/$1/releases?per_page=100 | jq '.[] | .assets[] | .download_count' | awk '{s+=$1} END {print s}'
}

echo "DataStation: `count datastation`"
echo "dsq: `count dsq`"

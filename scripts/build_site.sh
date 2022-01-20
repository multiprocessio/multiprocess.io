#!/usr/bin/env bash

set -e

find . -name '*~' -delete

# Grab docs repo
git clone git@github.com:multiprocessio/datastation-documentation || echo 'already exists'
( cd datastation-documentation && git fetch origin && git reset --hard origin/main)

rm -rf build && mkdir -p build/blog build/docs
python3 -m venv .env
.env/bin/pip install -r requirements.txt
.env/bin/python ./scripts/build_site.py
cp assets/* build

if [[ "$1" != "--skip-stars" ]]; then
    # Update stars count
    for starfile in $(find build/stars/*.html); do
	project="$(basename $starfile .html)"
	stars="$(curl -L https://api.github.com/repos/multiprocessio/$project | jq '.stargazers_count')"
	sed -i 's/STARS/'"$stars"'/g' "$starfile"
    done
fi

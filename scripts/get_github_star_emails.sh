#!/usr/bin/env bash
curl \
  -s \
  -u $GITHUB_USER:$GITHUB_TOKEN \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/multiprocessio/datastation/stargazers\?per_page\=100 > stars.json

cat stars.json|jq -r '.[] | .login' | xargs -I {} curl -s -u $GITHUB_USER:$GITHUB_TOKEN -H "Accept: application/vnd.github.v3+json" "https://api.github.com/users/{}" | jq -r '.email' | grep -v 'null'

rm stars.json

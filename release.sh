#!/bin/bash

version=$(jq -r ".version" package.json)

# Tag the release
git tag -a "release-v$version" -m "Release v$version"
git push -u origin main --tags

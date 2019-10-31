#!/usr/bin/env bash
set -x

pushd $PROJ_DIR/frontend/build || exit 1

rm -fr $PROJ_DIR/munggoggo/static/frontend/
cp -a . $PROJ_DIR/munggoggo/static/frontend/

popd

exit 0

#!/bin/bash

# this script should be executed from $WORKSPACE like 'cd $WORKSPACE && /bin/bash jenkins/build.sh'

set -e

# set $TAG for current build
export TAG=$(echo $PWD | cut -c 28-31)
echo $TAG

### build base images ###

/usr/local/bin/docker-compose build

# ### push images ###
/usr/local/bin/docker-compose push

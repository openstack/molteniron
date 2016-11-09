#!/bin/bash

# Copyright (c) 2016 IBM Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# $ git clone git://git.openstack.org/openstack/molteniron.git
# $ cd molteniron/
# $ ./utils/install_requirements.sh
#
# NOTE: You will be asked to provide a password for the mysql server! You
#       use that password twice during createDB.py
#

die()
{
  test -n "$@" && echo "$@" 1>&2
  exit 1
}

DIR="$(dirname $(readlink -f $0))"

sudo apt-get update
if [ $? -gt 0 ]
then
  die "apt-get update failed"
fi

PACKAGES="build-essential python-pip jq"
PACKAGES="${PACKAGES} python-dev python3-dev"
PACKAGES="${PACKAGES} python2.7 python3.5"
PACKAGES="${PACKAGES} mysql-server"

sudo apt-get install -y ${PACKAGES}
if [ $? -gt 0 ]
then
  die "apt-get install failed"
fi

sudo -H pip install --upgrade pip
if [ $? -gt 0 ]
then
  die "pip upgrade pip failed"
fi

sudo -H pip install -U --force-reinstall -r requirements.txt
if [ $? -gt 0 ]
then
  die "pip install requirements failed"
fi

${DIR}/createDB.py
if [ $? -gt 0 ]
then
  die "createDB failed"
fi

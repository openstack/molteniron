
Installation
============

With a clean installation of an Ubuntu 16.04 system, do the following::

  $ sudo apt-get install -y build-essential python-dev python3-dev
  $ sudo apt-get install -y libmysqlclient-dev tox python2.7 python3.5
  $ sudo apt-get install -y mysql-server

If you see::

  E: Unable to locate package tox

then remove tox and reinstall.  Next, do the following::

  $ sudo pip install --upgrade tox

Then, check out the MoltenIron project::

  $ git clone https://opendev.org/openstack/molteniron.git
  $ cd molteniron/

Before you can install the package requirements, you may need to install a
prerequisite (on a non-clean system)::

  $ hash mysql_config || sudo apt install -y libmysqlclient-dev

Then install the package requirements::

  $ sudo pip install -U --force-reinstall -r requirements.txt

Before starting the server for the first time, the createDB.py
script must be run as follows::

  $ createDB.py

Or with a clean installation of an Ubuntu 16.04 system, do the following::

  $ sudo apt-get update
  $ git clone https://opendev.org/openstack/molteniron.git
  $ cd molteniron/
  $ ./utils/install_requirements.sh

You can run the suite of testcases to make sure everything works::

  $ (rm -rf .tox/py27/ testenv/; tox -epy27)
  $ (rm -rf .tox/py35/ testenv/; tox -epy35)

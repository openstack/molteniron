MoltenIron overview
===================

MoltenIron maintains a pool of bare metal nodes.

Installation
------------

With a clean installation of an Ubuntu 16.04 system, do the following::

  $ sudo apt-get install -y build-essential python-dev python3-dev
  $ sudo apt-get install -y libmysqlclient-dev tox python2.7 python3.5
  $ sudo apt-get install -y mysql-server

If you see::

  E: Unable to locate package tox

then remove tox and reinstall.  Next, do the following::

  $ sudo pip install --upgrade tox

Then, check out the MoltenIron project::

  $ git clone git://git.openstack.org/openstack/molteniron.git
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
  $ git clone git://git.openstack.org/openstack/molteniron.git
  $ cd molteniron/
  $ ./utils/install_requirements.sh

You can run the suite of testcases to make sure everything works::

  $ (rm -rf .tox/py27/ testenv/; tox -epy27)
  $ (rm -rf .tox/py35/ testenv/; tox -epy35)

Starting
--------

To start the server::

    $ sudo moltenirond-helper start


To stop the server::

    $sudo moltenirond-helper stop


MoltenIron client
-----------------

Use the molteniron client (molteniron) to communicate with the server. For
usage information type::

    $ molteniron -h


For usage of a specific command use::

    $ molteniron [command] -h


MoltenIron commands
-------------------

+----------+---------------------------------------------+
|command   | description                                 |
+==========+=============================================+
|add       | Add a node                                  |
+----------+---------------------------------------------+
|allocate  | Allocate a node                             |
+----------+---------------------------------------------+
|release   | Release a node                              |
+----------+---------------------------------------------+
|get_field | Get a specific field in a node              |
+----------+---------------------------------------------+
|set_field | Set a specific field with a value in a node |
+----------+---------------------------------------------+
|status    | Return the status of every node             |
+----------+---------------------------------------------+
|delete_db | Delete every database entry                 |
+----------+---------------------------------------------+

Configuration of MoltenIron
---------------------------

Configuration of MoltenIron is specified in the file conf.yaml.

"Both" means that this configuration option is required for both the client and
the server.  "Client" means that it is required only for the client.  "Server"
means it is only required for the server.

+-------+------------+----------------------------------------------------------+
|usage  | key        | description                                              |
+=======+============+==========================================================+
|Both   | mi_port    | the port that the server uses to respond to commands.    |
+-------+------------+----------------------------------------------------------+
|Client | serverIP   | The IP address of the server.  This is only used by      |
|       |            | clients.                                                 |
+-------+------------+----------------------------------------------------------+
|Server | maxTime    | The maximum amount of time, in seconds, that a node      |
|       |            | is allowed to be allocated to a particular BM node.      |
+-------+------------+----------------------------------------------------------+
|Server | logdir     | The path to the directory where the logs should be       |
|       |            | stored.                                                  |
+-------+------------+----------------------------------------------------------+
|Server | maxLogDays | The amount of time, in days, to keep old logs.           |
+-------+------------+----------------------------------------------------------+
|Server | sqlUser    | The username to use for the MI server.  This user        |
|       |            | will automatically be generated when createDB.py is run. |
+-------+------------+----------------------------------------------------------+
|Server | sqlPass    | The password of sqlUser                                  |
+-------+------------+----------------------------------------------------------+

Running testcases
-----------------

The suite of testcases is checked by tox.  But, before you can run tox, you
need to change the local yaml configuration file to point to the log
directory.  An example::

    (LOG=$(pwd)/testenv/log; sed -i -r -e 's,^(logdir: )(.*)$,\1'${LOG}',' conf.yaml; rm -rf testenv/; tox -e testenv)

Running inside a Continuous Integration environment
---------------------------------------------------

During the creation of a job, in the pre_test_hook.sh, add the following snippet of bash code::

    # Setup MoltenIron and all necessary prerequisites.
    # And then call the MI script to allocate a node.
    (
      REPO_DIR=/opt/stack/new/molteniron
      MI_CONF_DIR=/usr/local/etc/molteniron
      MI_IP=10.1.2.3     # @TODO - Replace with your IP addr here!

      # Grab molteniron and install it
      git clone https://git.openstack.org/openstack/molteniron ${REPO_DIR} || exit 1

      cd ${REPO_DIR}

      # @BUG Install prerequisite before running pip to install the requisites
      hash mysql_config || sudo apt install -y libmysqlclient-dev

      # Install the requisites for this package
      sudo pip install --upgrade --force-reinstall --requirement requirements.txt

      # Run the python package installation program
      sudo python setup.py install

      if [ -n "${MI_IP}" ]
      then
        # Set the molteniron server IP in the conf file
        sudo sed -i "s/127.0.0.1/${MI_IP}/g" ${MI_CONF_DIR}/conf.yaml
      fi

      sudo ${REPO_DIR}/utils/test_hook_mi_ipmiblob.py \
           --hardware-info=/opt/stack/new/devstack/files/hardware_info \
           --localrc=/opt/stack/new/devstack/localrc \
           ${dsvm_uuid} \
           1
    ) || exit $?

and change the MI_IP environment variable to be your MoltenIron server!

During the destruction of a job, in the post_test_hook.sh, add the following snippet of bash code::

    DSVM_UUID="$(</etc/nodepool/uuid)"
    echo "Cleaning up resources associated with node: ${DSVM_UUID}"
    molteniron release ${DSVM_UUID}

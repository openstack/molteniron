
Usage
=====

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
      git clone https://opendev.org/openstack/molteniron ${REPO_DIR} || exit 1

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


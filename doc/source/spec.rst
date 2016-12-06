..
 This work is licensed under a Creative Commons Attribution 3.0 Unported
 License.

 http://creativecommons.org/licenses/by/3.0/legalcode

===========
Molten Iron
===========

https://bugs.launchpad.net/ironic/+bug/1633540

Running Ironic on a set of Bare Metal machines needs a database and library
to help manage the pool.


Problem description
===================

When running a Continuous Integration (CI) environment, many patches need
to be tested. While one could theoretically configure one Bare Metal machine
in an Ironic setup, you are limited to being able to test one patch at a
time.

Therefore, we need to maintain a pool of Bare Metal machines that are
available for a DSVM (DevStack Virtual Machine) to use as a target node
during Ironic's tempest tests.

We need a system to manage the pool and also to allocate and release
machines in the pool. This may sound like it is a CI pool manager on top
of Ironic. However, it does not require that Ironic perform reservations
and locking.


Proposed change
===============

We will create a new client/server tool that uses a database server as the
back end. This is intended to be lightweight and not leverage Ironic's API.

This tool is intended for Ironic CI testing environments that uses actual
baremetal hardware as target nodes rather than using libvirt guests. It
keeps track of what hardware is currently available for use as a target
node in baremetal testing, and allows a DSVM to check-out (and eventually
check back in) nodes from a database. The tool will be used by the DSVM
and will need two hook points. One that is called before DVSM is run and
one that is called after DVSM have finished.

One way to do this is in Jenkins where a builder in a job template will
call the pre_hook and a job publisher will call the post_hook during
cleanup.

In the pre_hook, you call 'molteniron allocate' to check out the node and
retrieve the information needed to use the node as a target (ie IPMI info
and hardware specs). In the post_hook, you call 'molteniron release' to
return the node to the pool.

The tool will have the following basic functionality:
    - add a node
    - allocate a node
    - release a node
    - get a field value in a node
    - set a field value in a node
    - return all of the node's status


Alternatives
------------

Just use one machine to handle the queue of patches. However, the Ironic
job is limited to 1 job at a time (with 1 Bare Metal machine). It is slow
but arguably sufficient.

We could potentially use nodepool. However, nodepool uses virtual machines
and we want a pool of bare metal machines. Also, there is no storage of
bare metal controller information such as username, password, and IP address.
Also, nodepool interfaces with jenkins or zuul after the machine has been
brought up which we do not want.


Security impact
---------------

There is no security for the MoltenIron REST api. Any security is handled
by the underlying database application. Credentials are intended to be stored
in the database and will be stored in a plain text yaml file. We do not
encrypt the information in the database or any files.


Other end user impact
---------------------

There is no other end user interaction with MoltenIron aside from the CLI.


Implementation
==============

Assignee(s)
-----------

Who is leading the writing of the code? Or is this a blueprint where you're
throwing it out there to see who picks it up?

If more than one person is working on the implementation, please designate the
primary author and contact.

Primary assignee:
  mark-hamzy

Other contributors:
  mjturek


Testing
=======

Testing is handled by tox running a set of testcases.

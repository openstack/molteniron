#! /usr/bin/env python

"""
This is the MoltenIron client class that speaks to a MoltenIron server.
"""

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

# pylint: disable-msg=C0103
# pylint: disable=redefined-outer-name

from __future__ import print_function

import argparse
import json
import sys
if sys.version_info >= (3, 0):
    import http.client  # noqa
else:
    import httplib  # noqa


# Create a decorator pattern that maintains a registry
def makeRegistrar():
    """Decorator that keeps track of tagged functions."""
    registry = {}

    def registrar(func):
        """Store the function pointer."""
        registry[func.__name__] = func
        # normally a decorator returns a wrapped function,
        # but here we return func unmodified, after registering it
        return func
    registrar.all = registry
    return registrar

# Create the decorator
command = makeRegistrar()


class MoltenIron(object):
    """This is the MoltenIron client object."""

    def __init__(self):
        self.conf = None
        self.parser = None
        self.request = None
        self.response_str = None
        self.response_json = None

    def setup_conf(self, _conf):
        """Sets the class variable to what is passed in."""
        self.conf = _conf

    def setup_parser(self, _parser):
        """Sets the class variable to what is passed in."""
        self.parser = _parser

    def call_function(self, args):
        """Calls the function supplied on the server."""
        if self.request is not None:
            return False

        # Save the previously defined function pointer
        func = args['func']

        # But delete the class function pointer. json can't serialize it!
        del args['func']

        # Call the function specified on the command line!
        self.request = func(args=args)

        # Send the request and print the response
        self.response_str = self.send(self.request)
        self.response_json = json.loads(self.response_str)

        return True

    def send(self, request):
        """Send the generated request"""
        ip = str(self.conf['serverIP'])
        port = int(self.conf['mi_port'])
        if sys.version_info > (3, 0):
            connection = http.client.HTTPConnection(ip, port)  # noqa
        else:
            connection = httplib.HTTPConnection(ip, port)  # noqa
        connection.request('POST', '/', json.dumps(request))

        response = connection.getresponse()
        data = response.read()

        if sys.version_info > (3, 0):
            # We actually receive bytes instead of a string!
            data = data.decode("utf-8")

        return data

    def get_response(self):
        """Returns the response from the server"""
        if self.request is None:
            raise Exception("Call call_function first")

        return self.response_str

    def get_response_map(self):
        """Returns the response map from the server"""
        if self.request is None:
            raise Exception("Call call_function first")

        return self.response_json

    @command
    def add_baremetal(self, args=None, subparsers=None):
        """Add a node to the MoltenIron database.

           All parameters are manditory.
        """
        if subparsers is not None:
            sp = subparsers.add_parser("add_baremetal",
                                       help="Add a node to the MoltenIron"
                                            " database.")
            sp.add_argument("name",
                            help="Name of the baremetal node")
            sp.add_argument("ipmi_ip",
                            help="IP for issuing IPMI commands to"
                                 " this node")
            sp.add_argument("ipmi_user",
                            help="IPMI username used when issuing"
                                 " IPMI commands to this node")
            sp.add_argument("ipmi_password",
                            help="IPMI password used when"
                                 " issuing IPMI commands to this node")
            sp.add_argument("allocation_pool",
                            help="Comma separated list of"
                                 " IPs to be used in deployment")
            sp.add_argument("port_hwaddr",
                            help="MAC address of port on"
                                 " machine to use during deployment")
            sp.add_argument("cpu_arch",
                            help="Architecture of the node")
            sp.add_argument("cpus",
                            type=int,
                            help="Number of CPUs on the node")
            sp.add_argument("ram_mb",
                            type=int,
                            help="Amount of RAM (in MiB)"
                                 " that the node has")
            sp.add_argument("disk_gb",
                            type=int,
                            help="Amount of disk (in GiB)"
                                 " that the node has")
            sp.add_argument("node_pool",
                            type=str,
                            default="default",
                            nargs='?',
                            help="Node pool name")
            sp.set_defaults(func=self.add_baremetal)
            return

        args['method'] = 'add_baremetal'

        return args

    @command
    def add_keyvalue_pairs(self, args=None, subparsers=None):
        """Add a node to the MoltenIron database.

           args are a list of key=value pairs.
        """
        if subparsers is not None:
            sp = subparsers.add_parser("add_keyvalue_pairs",
                                       help="Add a node to the MoltenIron"
                                            " database.")
            sp.add_argument("name",
                            help="Name of the baremetal node")
            sp.add_argument("ipmi_ip",
                            help="IP for issuing IPMI commands to"
                                 " this node")
            sp.add_argument("allocation_pool",
                            help="Comma separated list of"
                                 " IPs to be used in deployment")
            sp.add_argument("args",
                            nargs=argparse.REMAINDER,
                            help="Architecture of the node")
            sp.add_argument("node_pool",
                            type=str,
                            default="default",
                            nargs='?',
                            help="Node pool name")
            sp.set_defaults(func=self.add_keyvalue_pairs)
            return

        args['method'] = 'add_keyvalue_pairs'

        return args

    @command
    def add_json_blob(self, args=None, subparsers=None):
        """Add a node to the MoltenIron database.

           blob is a JSON encoded string.
        """
        if subparsers is not None:
            sp = subparsers.add_parser("add_json_blob",
                                       help="Add a node to the MoltenIron"
                                            " database.")
            sp.add_argument("name",
                            help="Name of the baremetal node")
            sp.add_argument("ipmi_ip",
                            help="IP for issuing IPMI commands to"
                                 " this node")
            sp.add_argument("allocation_pool",
                            help="Comma separated list of"
                                 " IPs to be used in deployment")
            sp.add_argument("blob",
                            help="JSON encoded string")
            sp.add_argument("node_pool",
                            type=str,
                            default="default",
                            nargs='?',
                            help="Node pool name")
            sp.set_defaults(func=self.add_json_blob)
            return

        args['method'] = 'add_json_blob'

        return args

    @command
    def allocate(self, args=None, subparsers=None):
        """Checkout a node from the MoltenIron database"""
        if subparsers is not None:
            sp = subparsers.add_parser("allocate",
                                       help="Checkout a node in MoltenIron."
                                            " Returns the node's info.")
            sp.add_argument("owner_name",
                            help="Name of the requester")
            sp.add_argument("number_of_nodes",
                            type=int,
                            help="How many nodes to reserve")
            sp.add_argument("node_pool",
                            type=str,
                            default="default",
                            nargs='?',
                            help="Node pool name")
            sp.set_defaults(func=self.allocate)
            return

        args['method'] = 'allocate'

        return args

    @command
    def release(self, args=None, subparsers=None):
        """Release an allocated node from the MoltenIron database."""
        if subparsers is not None:
            sp = subparsers.add_parser("release",
                                       help="Given an owner name, release the"
                                            " allocated node, returning it to"
                                            " the available state.")
            sp.add_argument("owner_name",
                            help="Name of the owner who"
                                 " currently owns the nodes to be released")
            sp.set_defaults(func=self.release)
            return

        args['method'] = 'release'

        return args

    @command
    def get_field(self, args=None, subparsers=None):
        """Return a field of data from an owned node from the MoltenIron db."""
        if subparsers is not None:
            sp = subparsers.add_parser("get_field",
                                       help="Given an owner name and the name"
                                            " of a field, get the value of"
                                            " the field.")
            sp.add_argument("owner_name",
                            help="Name of the owner who currently"
                                 " owns the nodes to get the field from")
            sp.add_argument("field_name",
                            help="Name of the field to retrieve"
                                 " the value from")
            sp.set_defaults(func=self.get_field)
            return

        args['method'] = 'get_field'

        return args

    @command
    def set_field(self, args=None, subparsers=None):
        """Set a field of data from an id in the MoltenIron database."""
        if subparsers is not None:
            sp = subparsers.add_parser("set_field",
                                       help="Given an id, set a field with a"
                                            " value.")
            sp.add_argument("id",
                            help="Id of the entry")
            sp.add_argument("key",
                            help="Field name to set")
            sp.add_argument("value",
                            help="Field value to set")
            sp.add_argument("type",
                            help="Field Python type to set")
            sp.set_defaults(func=self.set_field)
            return

        args['method'] = 'set_field'

        return args

    @command
    def status(self, args=None, subparsers=None):
        """Return the nodes as a status"""
        if subparsers is not None:
            sp = subparsers.add_parser("status",
                                       help="Return a list of current"
                                            " MoltenIron Node database"
                                            " entries.")
            sp.add_argument("-t",
                            "--type",
                            action="store",
                            type=str,
                            default="human",
                            dest="type",
                            help="Either human (the default) or csv")
            sp.set_defaults(func=self.status)
            return

        args['method'] = 'status'

        return args

    @command
    def status_baremetal(self, args=None, subparsers=None):
        """Return the nodes as a status"""
        if subparsers is not None:
            sp = subparsers.add_parser("status_baremetal",
                                       help="Return a list of current"
                                            " MoltenIron Node database"
                                            " entries.")
            sp.add_argument("-t",
                            "--type",
                            action="store",
                            type=str,
                            default="human",
                            dest="type",
                            help="Either human (the default) or csv")
            sp.set_defaults(func=self.status_baremetal)
            return

        args['method'] = 'status_baremetal'

        return args

    @command
    def delete_db(self, args=None, subparsers=None):
        """Delete all database entries"""
        if subparsers is not None:
            sp = subparsers.add_parser("delete_db",
                                       help="Delete every entry in the"
                                            " MoltenIron Node database.")
            sp.set_defaults(func=self.delete_db)
            return

        args['method'] = 'delete_db'

        return args

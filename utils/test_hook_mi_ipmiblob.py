#! /usr/bin/env python

"""
This is the MoltenIron Command Line client that speaks to
a MoltenIron server.
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
from molteniron import molteniron
import os
import sys
import yaml


if __name__ == "__main__":
    mi = molteniron.MoltenIron()

    parser = argparse.ArgumentParser(description="Molteniron test gate tool")

    parser.add_argument("-c",
                        "--conf-dir",
                        action="store",
                        type=str,
                        dest="conf_dir",
                        help="The directory where configuration is stored")
    parser.add_argument("-i",  # Stoopid -h for help
                        "--hardware-info",
                        action="store",
                        type=str,
                        dest="hardware_info",
                        required=True,
                        help="The hardware_info file")
    parser.add_argument("-l",
                        "--localrc",
                        action="store",
                        type=str,
                        dest="localrc",
                        required=True,
                        help="The localrc file")
    parser.add_argument("owner_name",
                        help="Name of the requester")
    parser.add_argument("number_of_nodes",
                        type=int,
                        help="How many nodes to reserve")

    args = parser.parse_args()

    if args.conf_dir:
        if not os.path.isdir(args.conf_dir):
            msg = "Error: %s is not a valid directory" % (args.conf_dir, )
            print(msg, file=sys.stderr)
            sys.exit(1)

        yaml_file = os.path.realpath("%s/conf.yaml" % (args.conf_dir, ))
    else:
        yaml_file = "/usr/local/etc/molteniron/conf.yaml"

    with open(yaml_file, "r") as f_obj:
        conf = yaml.load(f_obj)

        mi.setup_conf(conf)
        mi.setup_parser(parser)

        # For example:
        # args_map = {"output": "json",
        #             "type": "human",
        #             "func": getattr(mi, "status"),
        #             "conf_dir": "testenv/etc/molteniron/"}
        args_map = {"output": "json",
                    "owner_name": args.owner_name,
                    "number_of_nodes": args.number_of_nodes,
                    "func": getattr(mi, "allocate"),
                    "conf_dir": "testenv/etc/molteniron/"}

        # Call the function
        mi.call_function(args_map)

        # Get the result
        response_map = mi.get_response_map()

        try:
            rc = response_map["status"]
        except KeyError:
            msg = ("Error: Server returned: %s and we expected a status " +
                   "somewhere") % (response_map, )
            print(msg, file=sys.stderr)
            exit(444)

        if rc != 200:
            msg = "Error: Status was not 200 %s" % (response_map["message"], )
            print(msg, file=sys.stderr)
            exit(rc)

        assert response_map["status"] == 200
        assert "nodes" in response_map

        nodes = response_map["nodes"]

        assert len(nodes) == 1

        # There can only be one!
        node_key = list(nodes.keys())[0]

        # {u'status': u'dirty',
        #  u'provisioned': u'bb6141a2-3585-496a-bc02-1ef89c81e8fb',
        #  u'name': u'test2',
        #  u'timestamp': u'2016-11-30T15:50:03',
        #  u'ipmi_ip': u'10.1.2.2',
        #  u'blob': u'{"port_hwaddr": "\\"de:ad:be:ef:00:01\\"",
        #              "cpu_arch": "ppc64el",
        #              "ram_mb": "2048",
        #              "disk_gb": "32",
        #              "cpus": "8",
        #              "ipmi_user": "\\"user\\"",
        #              "ipmi_password": "\\"password\\""}',
        #  u'allocation_pool': u'10.1.2.5,10.1.2.6',
        #  u'id': 2}
        node = nodes[node_key]

        assert "blob" in node

        json_blob = node["blob"]
        blob = json.loads(json_blob)

        with open(args.hardware_info, "w") as hi_obj:
            # Write one line
            hi_obj.write(("%(ipmi_ip)s" % node) +
                         (" %(port_hwaddr)s" +
                          " %(ipmi_user)s" +
                          " %(ipmi_password)s\n") % blob)

        pool = node["allocation_pool"].split(",")

        pairs = ["start=%s,end=%s" % (x, x) for x in pool]
        allocation_pool = " --allocation-pool ".join(pairs)

        with open(args.localrc, "a") as l_obj:
            # Write multiple lines
            l_obj.write(("IRONIC_HW_ARCH=%(cpu_arch)s\n" +
                         "IRONIC_HW_NODE_CPU=%(cpus)s\n" +
                         "IRONIC_HW_NODE_RAM=%(ram_mb)s\n" +
                         "IRONIC_HW_NODE_DISK=%(disk_gb)s\n") % blob +
                        "ALLOCATION_POOL=\"%s\"\n" % (allocation_pool, ))

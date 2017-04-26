#!/usr/bin/env python

"""
Tests the MoltenIron deallocateBM command.
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

from __future__ import print_function

import argparse
import json
from molteniron import moltenirond
import os
from pkg_resources import resource_filename
import sys
import yaml


def result_to_r(res):
    """Takes a result and returns the request parameters."""

    r = res.copy()
    del r["blob"]
    return r


def result_to_n(res):
    """Takes a result and returns the node parameters."""

    n = {}
    if "blob" in res:
        blob = json.loads(res["blob"])
        n["ipmi_user"] = blob["ipmi_user"]
        n["ipmi_password"] = blob["ipmi_password"]
        n["port_hwaddr"] = blob["port_hwaddr"]
        n["cpu_arch"] = blob["cpu_arch"]
        n["cpus"] = blob["cpus"]
        n["ram_mb"] = blob["ram_mb"]
        n["disk_gb"] = blob["disk_gb"]
    return n


def compare_provisioned_nodes(lhs, rhs_r, rhs_n):
    """Specially compares lhs against the combined rhs_r and rhs_n."""

    rhs_r = rhs_r.copy()
    lhs_r = result_to_r(lhs)
    lhs_n = result_to_n(lhs)
    rhs_r['provisioned'] = 'hamzy'
    del lhs_r['status']
    del lhs_r['timestamp']
    del rhs_r['status']
    del rhs_r['timestamp']
    del lhs_r['id']
    assert lhs_r == rhs_r
    assert lhs_n == rhs_n


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Molteniron CLI tool")
    parser.add_argument("-c",
                        "--conf-dir",
                        action="store",
                        type=str,
                        dest="conf_dir",
                        help="The directory where configuration is stored")

    args = parser.parse_args(sys.argv[1:])

    if args.conf_dir:
        if not os.path.isdir(args.conf_dir):
            msg = "Error: %s is not a valid directory" % (args.conf_dir, )
            print(msg, file=sys.stderr)
            sys.exit(1)

        YAML_CONF = os.path.realpath("%s/conf.yaml" % (args.conf_dir, ))
    else:
        YAML_CONF = resource_filename("molteniron", "conf.yaml")

    with open(YAML_CONF, "r") as fobj:
        conf = yaml.load(fobj)

    request1 = {
        "name": "pkvmci816",
        "ipmi_ip": "10.228.219.134",
        "status": "ready",
        "provisioned": "",
        "timestamp": "",
        "allocation_pool": "10.228.112.10,10.228.112.11",
        "node_pool": "Default"
    }
    node1 = {
        "ipmi_user": "user",
        "ipmi_password": "e05cc5f061426e34",
        "port_hwaddr": "f8:de:29:33:a4:ed",
        "cpu_arch": "ppc64el",
        "cpus": 20,
        "ram_mb": 51000,
        "disk_gb": 500
    }
    request2 = {
        "name": "pkvmci818",
        "ipmi_ip": "10.228.219.133",
        "status": "ready",
        "provisioned": "",
        "timestamp": "",
        "allocation_pool": "10.228.112.8,10.228.112.9",
        "node_pool": "Default"
    }
    node2 = {
        "ipmi_user": "user",
        "ipmi_password": "0614d63b6635ea3d",
        "port_hwaddr": "4c:c5:da:28:2c:2d",
        "cpu_arch": "ppc64el",
        "cpus": 20,
        "ram_mb": 51000,
        "disk_gb": 500
    }
    request3 = {
        "name": "pkvmci851",
        "ipmi_ip": "10.228.118.129",
        "status": "used",
        "provisioned": "7a72eccd-3153-4d08-9848-c6d3b1f18f9f",
        "timestamp": "1460489832",
        "allocation_pool": "10.228.112.12,10.228.112.13",
        "node_pool": "Default"
    }
    node3 = {
        "ipmi_user": "user",
        "ipmi_password": "928b056134e4d770",
        "port_hwaddr": "53:76:c6:09:50:64",
        "cpu_arch": "ppc64el",
        "cpus": 20,
        "ram_mb": 51000,
        "disk_gb": 500
    }
    request4 = {
        "name": "pkvmci853",
        "ipmi_ip": "10.228.118.133",
        "status": "used",
        "provisioned": "6b8823ef-3e14-4811-98b9-32e27397540d",
        "timestamp": "1460491566",
        "allocation_pool": "10.228.112.14,10.228.112.15",
        "node_pool": "Default"
    }
    node4 = {
        "ipmi_user": "user",
        "ipmi_password": "33f448a4fc176492",
        "port_hwaddr": "85:e0:73:e9:fc:ca",
        "cpu_arch": "ppc64el",
        "cpus": 20,
        "ram_mb": 51000,
        "disk_gb": 500
    }

    # 8<-----8<-----8<-----8<-----8<-----8<-----8<-----8<-----8<-----8<-----
    database = moltenirond.DataBase(conf, moltenirond.TYPE_SQLITE_MEMORY)
    ret = database.addBMNode(request1, node1)
    print(ret)
    assert ret == {'status': 200}
    ret = database.addBMNode(request2, node2)
    print(ret)
    assert ret == {'status': 200}
    ret = database.addBMNode(request3, node3)
    print(ret)
    assert ret == {'status': 200}
    ret = database.addBMNode(request4, node4)
    print(ret)
    assert ret == {'status': 200}

    ret = database.allocateBM("hamzy", 1)
    print(ret)
    assert ret['status'] == 200
    assert len(ret["nodes"]) == 1
    compare_provisioned_nodes(ret["nodes"]["node_1"], request1, node1)

    session = database.get_session()
    n1 = session.query(moltenirond.Nodes)
    n1 = n1.filter_by(name=request1["name"])
    n1 = n1.one()
    session.close()
    ret = database.deallocateBM(n1.id)
    print(ret)
    assert ret['status'] == 200

    database.close()
    del database

    # 8<-----8<-----8<-----8<-----8<-----8<-----8<-----8<-----8<-----8<-----
    database = moltenirond.DataBase(conf, moltenirond.TYPE_SQLITE_MEMORY)
    database.delete_db()
    database.close()
    del database

    database = moltenirond.DataBase(conf, moltenirond.TYPE_SQLITE_MEMORY)
    ret = database.addBMNode(request1, node1)
    print(ret)
    assert ret == {'status': 200}
    ret = database.addBMNode(request2, node2)
    print(ret)
    assert ret == {'status': 200}
    ret = database.addBMNode(request3, node3)
    print(ret)
    assert ret == {'status': 200}
    ret = database.addBMNode(request4, node4)
    print(ret)
    assert ret == {'status': 200}

    ret = database.allocateBM("hamzy", 1)
    print(ret)
    assert ret['status'] == 200
    assert len(ret["nodes"]) == 1
    compare_provisioned_nodes(ret["nodes"]["node_1"], request1, node1)

    session = database.get_session()
    n1 = session.query(moltenirond.Nodes)
    n1 = n1.filter_by(name=request1["name"])
    n1 = n1.one()
    session.close()
    ret = database.deallocateBM(n1.ipmi_ip)
    print(ret)
    assert ret['status'] == 200

    database.close()
    del database

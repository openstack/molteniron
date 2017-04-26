#!/usr/bin/env python

"""
This is the MoltenIron server.
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

# flake8 disabling E242
# https://pep8.readthedocs.io/en/latest/intro.html
# https://gitlab.com/pycqa/flake8/issues/63
# Gah!

# pylint: disable-msg=C0103
# pylint: disable=redefined-outer-name

from __future__ import print_function

import argparse
import calendar
from datetime import datetime
import json
import os
from pkg_resources import resource_filename
import sys
import time
import traceback
import yaml

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.exc import InternalError, OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import MetaData, Table
from sqlalchemy.sql import insert, update, delete
from sqlalchemy.sql import and_
from sqlalchemy.types import TIMESTAMP

import sqlalchemy_utils

import collections  # noqa

if sys.version_info >= (3, 0):
    from http.server import HTTPServer, BaseHTTPRequestHandler  # noqa
else:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler  # noqa


DEBUG = False

metadata = MetaData()


class JSON_encoder_with_DateTime(json.JSONEncoder):
    """Special class to allow json to encode datetime objects"""
    def default(self, o):
        """Override default"""
        if isinstance(o, datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


# We need to turn BaseHTTPRequestHandler into a "new-style" class for
# Python 2.x
# NOTE: URL is over two lines :(
# http://stackoverflow.com/questions/1713038/super-fails-with-error-typeerror-
# argument-1-must-be-type-not-classobj
class OBaseHTTPRequestHandler(BaseHTTPRequestHandler, object):
    """Converts BaseHTTPRequestHandler into a new-style class"""
    pass


# We need to pass in conf into MoltenIronHandler, so make a class factory
# to do that
# NOTE: URL is over two lines :(
# http://stackoverflow.com/questions/21631799/how-can-i-pass-parameters-to-a-
# requesthandler
def MakeMoltenIronHandlerWithConf(conf):
    """Allows passing in conf to MoltenIronHandler,"""
    class MoltenIronHandler(OBaseHTTPRequestHandler):
        """HTTP handler class"""
        def __init__(self, *args, **kwargs):
            # Note this *needs* to be done before call to super's class!
            self.conf = conf
            self.data_string = None
            super(OBaseHTTPRequestHandler, self).__init__(*args, **kwargs)

        def do_POST(self):
            """HTTP POST support"""
            CL = 'Content-Length'
            data = self.rfile.read(int(self.headers[CL]))
            if sys.version_info >= (3, 0):
                # We actually received bytes instead of a string!
                data = data.decode("utf-8")
            self.data_string = data
            response = self.parse(self.data_string)
            self.send_reply(response)

        def send_reply(self, response):
            """Sends the HTTP reply"""
            if DEBUG:
                print("send_reply: response = %s" % (response,))
            # get the status code off the response json and send it
            status_code = response['status']
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            data = json.dumps(response, cls=JSON_encoder_with_DateTime)
            if sys.version_info >= (3, 0):
                # We actually need to send bytes instead of a string!
                data = data.encode()
            self.wfile.write(data)

        def parse(self, request_string):
            """Handle the request. Returns the response of the request """
            try:
                database = DataBase(self.conf)
                # Try to json-ify the request_string
                request = json.loads(request_string)
                method = request.pop('method')
                if method == 'add_baremetal':
                    node = {}
                    node['ipmi_user'] = request.pop('ipmi_user')
                    node['ipmi_password'] = request.pop('ipmi_password')
                    node['port_hwaddr'] = request.pop('port_hwaddr')
                    node['disk_gb'] = request.pop('disk_gb')
                    node['cpu_arch'] = request.pop('cpu_arch')
                    node['ram_mb'] = request.pop('ram_mb')
                    node['cpus'] = request.pop('cpus')
                    response = database.addBMNode(request, node)
                elif method == 'add_keyvalue_pairs':
                    node = {}

                    for elm in request["args"]:
                        idx = elm.find("=")
                        if idx > -1:
                            node[elm[:idx]] = elm[idx + 1:]
                    response = database.addBMNode(request, node)
                elif method == 'add_json_blob':
                    node = json.loads(request.pop("blob"))
                    response = database.addBMNode(request, node)
                elif method == 'allocate':
                    response = database.allocateBM(request['owner_name'],
                                                   request['number_of_nodes'],
                                                   request['node_pool'])
                elif method == 'release':
                    response = database.deallocateOwner(request['owner_name'])
                elif method == 'get_field':
                    response = database.get_field(request['owner_name'],
                                                  request['field_name'])
                elif method == 'set_field':
                    response = database.set_field(request['id'],
                                                  request['key'],
                                                  request['value'],
                                                  request['type'])
                elif method == 'status':
                    response = database.status(request["type"])
                elif method == 'status_baremetal':
                    response = database.status_baremetal(request["type"])
                elif method == 'delete_db':
                    response = database.delete_db()
                database.close()
                del database
            except Exception as e:
                response = {'status': 400, 'message': str(e)}

            if DEBUG:
                print("parse: response = %s" % (response,))

            return response

    return MoltenIronHandler


class Nodes(declarative_base()):
    """Nodes database class"""

    __tablename__ = 'Nodes'

    # from sqlalchemy.dialects.mysql import INTEGER

    # CREATE TABLE `Nodes` (
    #        id INTEGER NOT NULL AUTO_INCREMENT, #@TODO(hamzy) UNSIGNED
    #        name VARCHAR(50),
    #        ipmi_ip VARCHAR(50),
    #        blob VARCHAR(2000),
    #        status VARCHAR(20),
    #        provisioned VARCHAR(50),
    #        timestamp TIMESTAMP NULL,
    #        PRIMARY KEY (id)
    # )

    id = Column('id', Integer, primary_key=True)
    name = Column('name', String(50))
    ipmi_ip = Column('ipmi_ip', String(50))
    blob = Column('blob', String(2000))
    status = Column('status', String(20))
    provisioned = Column('provisioned', String(50))
    timestamp = Column('timestamp', TIMESTAMP)
    node_pool = Column('node_pool', String(20))

    __table__ = Table(__tablename__,
                      metadata,
                      id,
                      name,
                      ipmi_ip,
                      blob,
                      status,
                      provisioned,
                      timestamp,
                      node_pool)

    def map(self):
        """Returns a map of the database row contents"""
        return {key: value for key, value
                in list(self.__dict__.items())
                if not key.startswith('_') and
                not isinstance(key, collections.Callable)}

    def __repr__(self):
        fmt = """<Node(name='%s',
ipmi_ip='%s',
blob='%s',
status='%s',
provisioned='%s',
timestamp='%s',
node_pool='%s'/>"""
        fmt = fmt.replace('\n', ' ')

        return fmt % (self.name,
                      self.ipmi_ip,
                      self.blob,
                      self.status,
                      self.provisioned,
                      self.timestamp,
                      self.node_pool)


class IPs(declarative_base()):
    """IPs database class"""

    __tablename__ = 'IPs'

    # CREATE TABLE `IPs` (
    #         id INTEGER NOT NULL AUTO_INCREMENT, #@TODO(hamzy) \
    #            INTEGER(unsigned=True)
    #         node_id INTEGER, #@TODO(hamzy) UNSIGNED
    #         ip VARCHAR(50),
    #         PRIMARY KEY (id),
    #         FOREIGN KEY(node_id) REFERENCES `Nodes` (id)
    # )

    id = Column('id',
                Integer,
                primary_key=True)
    node_id = Column('node_id',
                     Integer,
                     ForeignKey("Nodes.id"))
    ip = Column('ip',
                String(50))

    __table__ = Table(__tablename__,
                      metadata,
                      id,
                      node_id,
                      ip)

    def __repr__(self):

        fmt = """<Node(id='%d',
node_id='%d',
ip='%s' />"""
        fmt = fmt.replace('\n', ' ')

        return fmt % (self.id,
                      self.node_id,
                      self.ip)

TYPE_MYSQL = 1
# Is there a mysql memory path?
TYPE_SQLITE = 3
TYPE_SQLITE_MEMORY = 4


class DataBase(object):
    """This class may be used access the molten iron database.  """

    def __init__(self,
                 config,
                 db_type=TYPE_MYSQL):
        self.conf = config

        self.user = self.conf["sqlUser"]
        self.passwd = self.conf["sqlPass"]
        self.host = "127.0.0.1"
        self.database = "MoltenIron"
        self.db_type = db_type

        engine = None
        try:
            # Does the database exist?
            engine = self.create_engine()
            c = engine.connect()
            c.close()
        except (OperationalError, InternalError) as e:
            if DEBUG:
                print("Database:__init__: Caught %s" % (e, ))
            # engine.connect will throw sqlalchemy.exc exception
            if isinstance(e, InternalError):
                (num, msg) = e.orig.args
                if DEBUG:
                    print("Database:__init__: (%d,%s)" % (num, msg, ))
                if num != 1049 or msg != "Unknown database 'MoltenIron'":
                    # If it is not the above then reraise it!
                    raise
            # It does not! Create it.
            # CREATE DATABASE MoltenIron;
            sqlalchemy_utils.create_database(engine.url)
            engine = self.create_engine()
            c = engine.connect()
            c.close()
        self.engine = engine

        self.create_metadata()

        self.blob_status = {
            "element_info": [
                # The following are returned from the query call

                # field_name length special_fmt skip
                ("id", 4, int, False),
                ("name", 6, str, False),
                ("ipmi_ip", 16, str, False),
                ("blob", 40, str, False),
                ("status", 8, str, False),
                ("provisioned", 40, str, False),
                # We add timeString
                ("time", 14, float, False),
                ("node_pool", 19, str, False),
            ]
        }
        self.baremetal_status = {
            "element_info": [
                # The following are returned from the query call

                # field_name length special_fmt skip
                ("id", 4, int, False),
                ("name", 6, str, False),
                ("ipmi_ip", 9, str, False),
                ("ipmi_user", 11, str, False),
                ("ipmi_password", 15, str, False),
                ("port_hwaddr", 19, str, False),
                ("cpu_arch", 10, str, False),
                ("cpus", 6, int, False),
                ("ram_mb", 8, int, False),
                ("disk_gb", 9, int, False),
                ("status", 8, str, False),
                ("provisioned", 40, str, False),
                # We add timeString
                ("time", 14, float, False),
                ("node_pool", 19, str, False),
            ]
        }

        # Pass map by reference but update our copy with the new information
        self.baremetal_status = self.setup_status(**self.baremetal_status)
        self.blob_status = self.setup_status(**self.blob_status)

    def create_engine(self):
        """Create the sqlalchemy database engine"""
        engine = None

        if self.db_type == TYPE_MYSQL:
            engine = create_engine("mysql+pymysql://%s:%s@%s/%s"
                                   % (self.user,
                                      self.passwd,
                                      self.host,
                                      self.database, ),
                                   echo=DEBUG)
        elif self.db_type == TYPE_SQLITE_MEMORY:
            engine = create_engine('sqlite:///:memory:',
                                   echo=DEBUG)
        elif self.db_type == TYPE_SQLITE:
            engine = create_engine("sqlite://%s:%s@%s/%s"
                                   % (self.user,
                                      self.passwd,
                                      self.host,
                                      self.database, ),
                                   echo=DEBUG)

        return engine

    def close(self):
        """Close the sqlalchemy database engine"""
        if DEBUG:
            print("close: Calling engine.dispose()")
        self.engine.dispose()
        if DEBUG:
            print("close: Finished")

    def get_session(self):
        """Get a SQL academy session from the pool """
        Session = sessionmaker(bind=self.engine)
        session = Session()

        return session

    def get_connection(self):
        """Get a SQL academy connection from the pool """
        conn = self.engine.connect()

        return conn

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations. """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            if DEBUG:
                print("Exception caught in session_scope: %s %s"
                      % (e, traceback.format_exc(4), ))
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def connection_scope(self):
        """Provide a transactional scope around a series of operations. """
        conn = self.get_connection()
        try:
            yield conn
        except Exception as e:
            if DEBUG:
                print("Exception caught in connection_scope: %s" % (e,))
            raise
        finally:
            conn.close()

    def delete_db(self):
        """Delete the sqlalchemy database"""
        # Instead of:
        #   IPs.__table__.drop(self.engine, checkfirst=True)
        #   Nodes.__table__.drop(self.engine, checkfirst=True)
        metadata.drop_all(self.engine, checkfirst=True)

        return {'status': 200}

    def create_metadata(self):
        """Create the sqlalchemy database metadata"""
        # Instead of:
        #   Nodes.__table__.create(self.engine, checkfirst=True)
        #   IPs.__table__.create(self.engine, checkfirst=True)
        if DEBUG:
            print("create_metadata: Calling metadata.create_all")
        metadata.create_all(self.engine, checkfirst=True)
        if DEBUG:
            print("create_metadata: Finished")

    def to_timestamp(self, ts):
        """Convert from a database time stamp to a Python time stamp"""
        timestamp = None
        if self.db_type == TYPE_MYSQL:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", ts)
        elif self.db_type in (TYPE_SQLITE, TYPE_SQLITE_MEMORY):
            c = calendar.timegm(ts)
            timestamp = datetime.fromtimestamp(c)
        return timestamp

    def from_timestamp(self, timestamp):
        """Convert from a Python time stamp to a database time stamp"""
        ts = None
        if self.db_type == TYPE_MYSQL:
            ts = time.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        elif self.db_type == TYPE_SQLITE:
            ts = timestamp.timetuple()
        return ts

    def allocateBM(self, owner_name, how_many, node_pool="Default"):
        """Checkout machines from the database and return necessary info """

        try:
            with self.session_scope() as session, \
                    self.connection_scope() as conn:

                count_with_pool = 0
                # Get a list of IDs for nodes that are free
                count = session.query(Nodes).filter_by(status="ready").count()
                # Get a list of IDs for nodes that are free and with specific
                # node_pool
                if node_pool != "Default":
                    count_with_pool = session.query(Nodes).filter_by(
                        status="ready", node_pool=node_pool).count()
                # If we don't have enough nodes return an error
                if count < how_many:
                    fmt = "Not enough available nodes found."
                    fmt += " Found %d, requested %d"
                    return {'status': 404,
                            'message': fmt % (count, how_many, )}

                nodes_allocated = {}

                for _ in range(how_many):
                    first_ready = session.query(Nodes)
                    if count_with_pool > 0:
                        first_ready = first_ready.filter_by(
                            status="ready", node_pool=node_pool)
                        count_with_pool = count_with_pool - 1
                    else:
                        first_ready = first_ready.filter_by(status="ready")
                    first_ready = first_ready.first()

                    node_id = first_ready.id
                    # We have everything we need from node

                    log(self.conf,
                        "allocating node id: %d for %s" % (node_id,
                                                           owner_name, ))

                    timestamp = self.to_timestamp(time.gmtime())

                    # Update the node to the in use state
                    stmt = update(Nodes)
                    stmt = stmt.where(Nodes.id == node_id)
                    stmt = stmt.values(status="dirty",
                                       provisioned=owner_name,
                                       timestamp=timestamp)
                    conn.execute(stmt)

                    # Refresh the data
                    session.close()
                    session = self.get_session()

                    first_ready = session.query(Nodes).filter_by(id=node_id)
                    first_ready = first_ready.one()

                    first_ready_node = first_ready.map()

                    # Query the associated IP table
                    ips = session.query(IPs).filter_by(node_id=first_ready.id)

                    allocation_pool = []
                    for ip in ips:
                        allocation_pool.append(ip.ip)
                    first_ready_node['allocation_pool'] \
                        = ','.join(allocation_pool)

                    # Add the node to the nodes dict
                    nodes_allocated['node_%d' % (node_id, )] = first_ready_node

        except Exception as e:

            if DEBUG:
                print("Exception caught in deallocateBM: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200, 'nodes': nodes_allocated}

    def deallocateBM(self, node_id):
        """Given the ID of a node (or the IPMI IP), de-allocate that node.

        This changes the node status of that node from "used" to "ready."
        """

        try:
            with self.session_scope() as session, \
                    self.connection_scope() as conn:

                query = session.query(Nodes.id, Nodes.ipmi_ip, Nodes.name)

# WAS:
#               if (isinstance(node_id, str) or
#                       isinstance(node_id, unicode)) \
#                  and ("." in node_id):

                check = isinstance(node_id, str)
                if sys.version_info < (3, 0):
                    check = check or isinstance(node_id, unicode)  # noqa

                if check and ("." in node_id):
                    # If an ipmi_ip was passed
                    query = query.filter_by(ipmi_ip=node_id)
                else:
                    query = query.filter_by(id=node_id)

                node = query.one()

                log(self.conf,
                    "de-allocating node (%d, %s)" % (node.id, node.ipmi_ip,))

                stmt = update(Nodes)
                stmt = stmt.where(Nodes.id == node.id)
                stmt = stmt.values(status="ready",
                                   provisioned="",
                                   timestamp=None)

                conn.execute(stmt)

        except Exception as e:

            if DEBUG:
                print("Exception caught in deallocateBM: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200}

    def deallocateOwner(self, owner_name):
        """Deallocate all nodes in use by a given BM owner.  """

        try:
            with self.session_scope() as session:
                nodes = session.query(Nodes.id)
                nodes = nodes.filter_by(provisioned=owner_name)

                if nodes.count() == 0:
                    message = "No nodes are owned by %s" % (owner_name,)

                    return {'status': 400, 'message': message}

                for node in nodes:
                    self.deallocateBM(node.id)
        except Exception as e:
            if DEBUG:
                print("Exception caught in deallocateOwner: %s" % (e,))
            message = "Failed to deallocate node with ID %d" % (node.id,)
            return {'status': 400, 'message': message}

        return {'status': 200}

    def addBMNode(self, request, data_map):
        """Add a new node to molten iron.

        ex:
        request = {u'name': u'test',
                   u'ipmi_ip': u'0.0.0.0',
                   u'status': u'',
                   u'provisioned': u'',
                   u'timestamp': u'',
                   u'allocation_pool': u'0.0.0.1,0.0.0.2'}
        data_map = {u'ipmi_user': u'user',
                    u'ipmi_password': u'password',
                    u'port_hwaddr': u'de:ad:be:ef:00:01',
                    u'disk_gb': 32,
                    u'cpu_arch': u'ppc64el',
                    u'ram_mb': 2048,
                    u'cpus': 8}
        """

        try:
            if DEBUG:
                print("addBMNode: request = %s data_map = %s"
                      % (request, data_map, ))

            with self.session_scope() as session, \
                    self.connection_scope() as conn:

                # Check if it already exists
                query = session.query(Nodes)
                query = query.filter_by(name=request['name'])
                count = query.count()

                if count == 1:
                    return {'status': 400, 'message': "Node already exists"}

                log(self.conf,
                    "adding node %(name)s ipmi_ip: %(ipmi_ip)s" % request)

                # Add Node to database
                # Note: ID is always 0 as it is an auto-incrementing field
                stmt = insert(Nodes)
                stmt = stmt.values(name=request['name'])
                stmt = stmt.values(ipmi_ip=request['ipmi_ip'])
                stmt = stmt.values(blob=json.dumps(data_map))
                stmt = stmt.values(status='ready')
                if 'status' in request:
                    stmt = stmt.values(status=request['status'])
                if 'provisioned' in request:
                    stmt = stmt.values(provisioned=request['provisioned'])
                if 'timestamp' in request:
                    timestamp_str = request['timestamp']
                    if DEBUG:
                        print("timestamp_str = %s" % (timestamp_str, ))
                    if len(timestamp_str) != 0 and timestamp_str != "-1":
                        ts = time.gmtime(float(timestamp_str))
                        timestamp = self.to_timestamp(ts)
                        if DEBUG:
                            print("timestamp = %s" % (timestamp, ))
                        stmt = stmt.values(timestamp=timestamp)
                if 'node_pool' in request:
                    stmt = stmt.values(node_pool=request['node_pool'])
                else:
                    stmt = stmt.values(node_pool="Default")
                if DEBUG:
                    print(stmt.compile().params)

                conn.execute(stmt)

                # Refresh the data
                session.close()
                session = self.get_session()

                query = session.query(Nodes).filter_by(name=request['name'])
                new_node = query.one()

                # new_node is now a proper Node with an id

                # Add IPs to database
                # Note: id is always 0 as it is an auto-incrementing field
                ips = request['allocation_pool'].split(',')
                for ip in ips:
                    stmt = insert(IPs)
                    stmt = stmt.values(node_id=new_node.id, ip=ip)

                    if DEBUG:
                        print(stmt.compile().params)

                    conn.execute(stmt)

        except Exception as e:

            if DEBUG:
                print("Exception caught in addBMNode: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200}

    def removeBMNode(self, ID, force):
        """Remove a node from molten iron

        If force is False it will not remove nodes that are in use.  If force
        is True then it will always remove the node.
        """

        try:
            with self.session_scope() as session, \
                    self.connection_scope() as conn:

                query = session.query(Nodes.id, Nodes.ipmi_ip, Nodes.name)
                query = query.filter_by(id=int(ID))
                query = query.one()

                log(self.conf,
                    ("deleting node (id=%d, ipmi_ip=%s, name=%s"
                     % (query.id, query.ipmi_ip, query.name,)))

                ips = session.query(IPs).filter_by(node_id=int(ID))
                for ip in ips:
                    stmt = delete(IPs)
                    stmt = stmt.where(IPs.id == ip.id)
                    conn.execute(stmt)

                stmt = delete(Nodes)

                if force:
                    stmt = stmt.where(and_(Nodes.id == query.id,
                                           Nodes.status != "used"))
                else:
                    stmt = stmt.where(Nodes.id == query.id)

                conn.execute(stmt)

        except Exception as e:

            if DEBUG:
                print("Exception caught in removeBMNode: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200}

    def cull(self, maxSeconds):
        """Deallocate old nodes.

        If any node has been in use for longer than maxSeconds, deallocate
        that node.  Nodes that are deallocated in this way get their state set
        to "dirty".  They are also scheduled for cleaning.
        """

        if DEBUG:
            print("cull: maxSeconds = %s" % (maxSeconds, ))

        nodes_culled = {}

        try:
            with self.session_scope() as session:

                nodes = session.query(Nodes)

                if DEBUG:
                    print("There are %d nodes" % (nodes.count(), ))

                for node in nodes:

                    if DEBUG:
                        print(node)

                    if node.timestamp in ('', '-1', None):
                        continue

                    currentTime = self.to_timestamp(time.gmtime())
                    elapsedTime = currentTime - node.timestamp
                    if DEBUG:
                        print("currentTime         = %s"
                              % (currentTime, ))
                        print("node.timestamp      = %s"
                              % (node.timestamp, ))
                        print("elapsedTime         = %s"
                              % (elapsedTime, ))
                        print("elapsedTime.seconds = %s"
                              % (elapsedTime.seconds, ))

                    if elapsedTime.seconds < int(maxSeconds):
                        continue

                    logstring = ("node %d has been allocated for too long."
                                 % (node.id,))
                    log(self.conf, logstring)

                    if DEBUG:
                        print(logstring)

                    self.deallocateBM(node.id)

                    # Add the node to the nodes dict
                    nodes_culled['node_%d' % (node.id, )] = node.map()

        except Exception as e:

            if DEBUG:
                print("Exception caught in cull: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200, 'nodes': nodes_culled}

    def doClean(self, node_id):
        """This function is used to clean a node. """

        try:
            with self.session_scope() as session, \
                    self.connection_scope() as conn:

                query = session.query(Nodes)
                query = query.filter_by(id=node_id)
                node = query.one()

                if node.status in ('ready', ''):
                    return {'status': 400,
                            'message': 'The node at %d has status %s'
                                       % (node.id, node.status,)}

                logstring = "The node at %s has been cleaned." % \
                            (node.ipmi_ip,)
                log(self.conf, logstring)

                stmt = update(Nodes)
                stmt = stmt.where(Nodes.id == node_id)
                stmt = stmt.values(status="ready")

                conn.execute(stmt)

        except Exception as e:

            if DEBUG:
                print("Exception caught in doClean: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200}

    # @TODO(hamzy) shouldn't it return allocation_pool rather than ipmi_ip?
    def get_ips(self, owner_name):
        """Return all IPs allocated to a given node owner

        IPs are returned as a list of strings
        """

        ips = []

        try:
            with self.session_scope() as session:

                query = session.query(Nodes)
                nodes = query.filter_by(provisioned=owner_name)

                for node in nodes:
                    ips.append(node.ipmi_ip)

        except Exception as e:

            if DEBUG:
                print("Exception caught in get_ips: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200, 'ips': ips}

    def get_field(self, owner_name, field):
        """Return entries list with id, field for a given owner, field.  """

        results = []

        try:
            with self.session_scope() as session:

                query = session.query(Nodes)
                nodes = query.filter_by(provisioned=owner_name)

                if DEBUG:
                    print("There are %d entries provisioned by %s"
                          % (nodes.count(), owner_name,))

                if nodes.count() == 0:
                    return {'status': 404,
                            'message': '%s does not own any nodes'
                                       % owner_name}

                for node in nodes:
                    result = {'id': node.id}

                    try:
                        result["field"] = getattr(node, field)
                    except AttributeError:
                        blob = json.loads(node.blob)
                        if field in blob:
                            result["field"] = blob[field]
                        else:
                            msg = "field %s does not exist" % (field, )
                            return {'status': 400, 'message': msg}

                    results.append(result)

        except Exception as e:

            if DEBUG:
                print("Exception caught in get_field: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200, 'result': results}

    def set_field(self, node_id, key, value, python_type):
        """Given an identifying id, set specified key to the passed value. """

        try:
            with self.session_scope() as session, \
                    self.connection_scope() as conn:

                if python_type.upper().lower() == "string":
                    pass
                elif python_type.upper().lower() == "int":
                    value = int(value)
                else:
                    return {'status': 400,
                            'message': 'Python type of %s is not supported!'
                                       % (python_type, )}

                query = session.query(Nodes)
                nodes = query.filter_by(id=node_id)

                if nodes.count() == 0:
                    return {'status': 404,
                            'message': 'Node with id of %s does not exist!'
                                       % (node_id, )}

                node = nodes.one()

                if hasattr(Nodes, key):
                    kv = {key: value}
                else:
                    blob = json.loads(node.blob)
                    if key in blob:
                        blob[key] = value
                        kv = {"blob": json.dumps(blob)}
                    else:
                        return {'status': 400,
                                'message': 'field %s does not exist' % (key,)}

                stmt = update(Nodes)
                stmt = stmt.where(Nodes.id == node_id)
                stmt = stmt.values(**kv)

                conn.execute(stmt)

        except Exception as e:

            if DEBUG:
                print("Exception caught in set_field: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200}

    def setup_status(self, **status_map):
        """Setup the status formatting strings.

        Which depends on the skipped elements, lengths, and types.
        """

        ei = status_map["element_info"]

        rs = "+"
        for (_, length, _, skip) in ei:
            if skip:
                continue
            rs += '-' * (1 + length + 1) + "+"

        dl = "+"
        for (field, length, _, skip) in ei:
            if skip:
                continue
            dl += (" " +
                   field +
                   ' ' * (length - len(field)) +
                   " +")

        index = 0
        fl = "|"
        for (_, length, special_fmt, skip) in ei:
            if skip:
                continue
            if special_fmt is int:
                fl += " {%d:<%d} |" % (index, length)
            elif special_fmt is str:
                fl += " {%d:%d} |" % (index, length)
            elif special_fmt is float:
                fl += " {%d:<%d.%d} |" \
                      % (index, length, length - 2)
            index += 1

        index = 0
        flc = ""
        for (_, length, special_fmt, skip) in ei:
            if skip:
                continue
            if special_fmt is int:
                flc += "{%d}," % (index, )
            elif special_fmt is str:
                flc += "{%d}," % (index, )
            elif special_fmt is float:
                flc += "{%d}," % (index, )
            index += 1

        status_map["result_separator"] = rs
        status_map["description_line"] = dl
        status_map["format_line"] = fl
        status_map["format_line_csv"] = flc

        return status_map

    def status(self, output_type):
        """Return a table that details the state of each bare metal node.

        Currently this table is being created manually, there is probably a
        better way to be doing this.
        """

        output_type = output_type.upper().lower()

        if output_type == "csv":
            return self.status_csv(self.blob_status_elements,
                                   **self.blob_status)
        elif output_type == "human":
            return self.status_full(self.blob_status_elements,
                                    **self.blob_status)
        else:
            return {'status': 400,
                    'message': "Unknown --type=%s" % (output_type, )}

    def status_baremetal(self, output_type):
        """Return a table that details the state of each bare metal node.

        Currently this table is being created manually, there is probably a
        better way to be doing this.
        """

        output_type = output_type.upper().lower()

        if output_type == "csv":
            return self.status_csv(self.baremetal_status_elements,
                                   **self.baremetal_status)
        elif output_type == "human":
            return self.status_full(self.baremetal_status_elements,
                                    **self.baremetal_status)
        else:
            return {'status': 400,
                    'message': "Unknown --type=%s" % (output_type, )}

    def blob_status_elements(self, node, timeString):

        blob = json.loads(node.blob)

        return (node.id,
                node.name,
                node.ipmi_ip,
                blob,
                node.status,
                node.provisioned,
                timeString,
                node.node_pool)

    def baremetal_status_elements(self, node, timeString):

        blob = json.loads(node.blob)

        return (node.id,
                node.name,
                node.ipmi_ip,
                blob["ipmi_user"],
                blob["ipmi_password"],
                blob["port_hwaddr"],
                blob["cpu_arch"],
                blob["cpus"],
                blob["ram_mb"],
                blob["disk_gb"],
                node.status,
                node.provisioned,
                timeString,
                node.node_pool)

    def status_csv(self, get_status_elements, **status_map):
        """Return a comma separated list of values"""

        result = ""

        ei = status_map["element_info"]
        flc = status_map["format_line_csv"]

        try:
            with self.session_scope() as session:

                query = session.query(Nodes)

                for node in query:

                    try:

                        timeString = ""
                        try:
                            if node.timestamp is not None:
                                et = datetime.utcnow() - node.timestamp
                                timeString = str(et)
                        except Exception:
                            pass

                        elements = get_status_elements(node, timeString)

                        new_elements = []
                        index = 0
                        for (_, _, _, skip) in ei:
                            if not skip:
                                new_elements.append(elements[index])
                            index += 1

                        result += flc.format(*new_elements) + "\n"

                    except KeyError:

                        result += "blob missing baremetal fields\n"

        except Exception as e:

            if DEBUG:
                print("Exception caught in status: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200, 'result': result}

    def status_full(self, get_status_elements, **status_map):
        """Return an ASCII table of the database entries"""

        result = ""

        ei = status_map["element_info"]
        rs = status_map["result_separator"]
        dl = status_map["description_line"]
        fl = status_map["format_line"]

        try:
            with self.session_scope() as session:

                query = session.query(Nodes)

                result += rs + "\n"
                result += dl + "\n"
                result += rs + "\n"

                for node in query:

                    try:

                        timeString = ""
                        try:
                            if node.timestamp is not None:
                                et = datetime.utcnow() - node.timestamp
                                timeString = str(et)
                        except Exception:
                            pass

                        elements = get_status_elements(node, timeString)

                        new_elements = []
                        index = 0
                        for (_, _, _, skip) in ei:
                            if not skip:
                                new_elements.append(elements[index])
                            index += 1

                        result += fl.format(*new_elements) + "\n"

                    except KeyError:

                        result += "blob missing baremetal fields\n"

                result += rs + "\n"

        except Exception as e:

            if DEBUG:
                print("Exception caught in status: %s" % (e,))

            # Don't send the exception object as it is not json serializable!
            return {'status': 400, 'message': str(e)}

        return {'status': 200, 'result': result}


def listener(conf):
    """HTTP listener"""
    mi_addr = str(conf['serverIP'])
    mi_port = int(conf['mi_port'])
    handler_class = MakeMoltenIronHandlerWithConf(conf)
    print('Listening... to %s:%d' % (mi_addr, mi_port,))
    moltenirond = HTTPServer((mi_addr, mi_port), handler_class)
    moltenirond.serve_forever()


def cleanup():
    """This function kills any running instances of molten iron.

    This should be called when starting a new instance of molten iron.
    """
    ps = os.popen("ps aux | grep python | grep moltenIronD.py").read()
    processes = ps.split("\n")
    pids = []
    for process in processes:
        if "grep" in process:
            continue
        words = process.split(" ")
        actual = []
        for word in words:
            if word != "":
                actual += [word]
        words = actual
        if len(words) > 1:
            pids += [words[1]]
    myPID = os.getpid()

    for pid in pids:
        if int(pid) == int(myPID):
            continue
        os.system("kill -9 " + pid)


def log(conf, message):
    """Write a message to the log file. """
    cleanLogs(conf)
    logdir = conf["logdir"]
    now = datetime.today()

    fname = "molteniron-%d-%d-%d.log" % (now.day,
                                         now.month,
                                         now.year, )

    timestamp = "{0:0>2}".format(str(now.hour))
    timestamp += ":{0:0>2}".format(str(now.minute))
    timestamp += ":{0:0>2}".format(str(now.second))

    message = timestamp + "  " + message + "\n"

    # check if logdir exists, if not create it
    if not os.path.isdir(logdir):
        os.popen("mkdir " + logdir)

    fobj = open(logdir + "/" + fname, "a")
    fobj.write(message)
    fobj.close()


def cleanLogs(conf):
    """Find and delete log files that have been around for too long. """
    logdir = conf["logdir"]
    maxDays = conf["maxLogDays"]
    if not os.path.isdir(logdir):
        return
    now = datetime.today()
    logs = os.popen("ls " + logdir).read().split("\n")
    for log in logs:
        if not log.startswith("molteniron-"):
            continue
        elements = log[:-1 * len(".log")].split("-")
        if len(elements) != 3:
            continue
        newDate = datetime(int(elements[2]),
                           int(elements[1]),
                           int(elements[0]))
        if (now - newDate).days > maxDays:
            os.popen("rm " + logdir + "/" + log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Molteniron daemon")
    parser.add_argument("-c",
                        "--conf-dir",
                        action="store",
                        type=str,
                        dest="conf_dir",
                        help="The directory where configuration is stored")

    args = parser.parse_args()

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

        listener(conf)

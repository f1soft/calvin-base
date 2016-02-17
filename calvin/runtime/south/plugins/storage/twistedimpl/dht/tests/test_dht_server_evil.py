# -*- coding: utf-8 -*-

# Copyright (c) 2015 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import sys
import os
import traceback
import pydot
import hashlib
import twisted
import random
import shutil

from calvin.utilities.calvin_callback import CalvinCB
from calvin.utilities import calvinlogger
from calvin.runtime.south.plugins.storage.twistedimpl.dht.append_server import *
from calvin.runtime.south.plugins.storage.twistedimpl.dht.dht_server import *
from calvin.runtime.south.plugins.storage.twistedimpl.dht.service_discovery_ssdp import *
from calvin.runtime.south.plugins.storage.twistedimpl.dht.dht_server_commons import *
from kademlia.node import Node

from calvin.runtime.south.plugins.async import threads
from calvin.utilities import calvinconfig

_conf = calvinconfig.get()
_log = calvinlogger.get_logger(__name__)

reactor.suggestThreadPoolSize(30)

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    def fin():
        reactor.callFromThread(reactor.stop)
    request.addfinalizer(fin)

@pytest.mark.interactive
@pytest.mark.slow
class TestDHT(object):
    test_nodes = 2
    _sucess_start = (True,)

    @pytest.inlineCallbacks
    def test_dht_multi(self, monkeypatch):
        iface = "0.0.0.0"
        a = None
        b = None
        q = Queue.Queue()


        def server_started(aa, *args):
            for b in args:
                if isinstance(b, twisted.python.failure.Failure):
                    b.printTraceback()
                else:
                    _log.debug("** %s" % b)
            q.put([aa,args])

        try:
            amount_of_servers = 1
            # Twisted is using 20 threads so having > 20 server
            # causes threadlocks really easily.

            servers = []
            callbacks = []
            for servno in range(0, amount_of_servers):
                a = evilAutoDHTServer()
                servers.append(a)
                callback = CalvinCB(server_started, str(servno))
                servers[servno].start(iface, network="Niklas", cb=callback, type="poison", name="evil")
                # servers[servno].start(iface, network="Hej", cb=callback, type="eclipse", name="evil")
                # servers[servno].start(iface, network="Hej", cb=callback, type="sybil")
                # servers[servno].start(iface, network="Hej", cb=callback, type="insert")
                callbacks.append(callback)
            print("Starting {}".format(servers[servno].dht_server.port.getHost().port))
                
            # Wait for start
            started = []
            while len(started) < amount_of_servers:
                try:
                    server = yield threads.defer_to_thread(q.get)
                except Queue.Empty:
                    _log.debug("Queue empty!")
                    #raise    
                if server not in started:
                    started.append(server)
                    _log.debug("DHT Servers added: {}".format(started))
                    callbacks[int(server[0][0])].func = lambda *args, **kvargs:None
                else:
                    _log.debug("Server: {} already started." \
                               " {} out of {}".format(started,
                                                     len(started),
                                                     amount_of_servers))

            _log.debug("All {} out of {} started".format(started,
                                                     len(started),
                                                     amount_of_servers))
            
            for servno in range(0, amount_of_servers):
                assert [str(servno), self._sucess_start] in started
            
            yield threads.defer_to_thread(q.queue.clear)
            yield threads.defer_to_thread(time.sleep, 15)

            evilPort = servers[0].dht_server.port.getHost().port
            drawNetworkState("start_graph.png", servers, amount_of_servers)
            servers[0].dht_server.kserver.protocol.turn_evil(evilPort)
            print("Node with port {} turned evil".format(servers[servno].dht_server.port.getHost().port))
            
            yield threads.defer_to_thread(time.sleep, 12)
            # assert get_value[0] == "banan"
            # assert get_value[1] == "bambu"
            # assert get_value[2] == "morot"
            yield threads.defer_to_thread(time.sleep, 5)
            print("Attacking node exiting")

        except AssertionError as e:
            print("Server {} with port {} got wrong value".format(servno, servers[servno].dht_server.port.getHost().port))
            pytest.fail(traceback.format_exc())

        except Exception as e:
            traceback.print_exc()
            pytest.fail(traceback.format_exc())
        finally:
            for server in servers:
                shutil.rmtree("/home/ubuntu/.calvin/security/test/{}/others".format("evil"), ignore_errors=True)
                os.mkdir("/home/ubuntu/.calvin/security/test/{}/others".format("evil"))
                server.stop()
                yield threads.defer_to_thread(time.sleep, 5)
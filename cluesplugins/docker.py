import logging
import cpyutils.eventloop
import cpyutils.oneconnect
import cpyutils.config
import clueslib.node
import clueslib.helpers
import clueslib.request
import clueslib.platform
from clueslib.node import Node, NodeInfo, NodeList
from cpyutils.evaluate import TypedClass, TypedList

import json
import subprocess

import requests

_LOGGER = logging.getLogger("[PLUGIN-Docker]")


def get_worker_nodes_list_from_docker_wrapper(ip):
    r = requests.get(ip+"/nodes/list")
    return json.loads(r.content)

def get_schedulers_list_from_docker_wrapper(ip):
    r = requests.get(ip+"/jobs/list")
    return json.loads(r.content)

# def to_BYTE(num, unidad):
#     if unidad[0] == "K":
#         num = float(num) * pow(2, 10)
#     elif unidad[0] == "M":
#         num = float(num) * pow(2, 20)
#     elif unidad[0] == "G":
#         num = float(num) * pow(2, 30)
#     return num

def run_command(command):
    try:
        p=subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        (out, err) = p.communicate()
        if p.returncode != 0:
            raise Exception("return code: %d\nError output: %s" % (p.returncode, err))
        return out
    except Exception as e:
        raise Exception("Error executing '%s': %s" % (" ".join(command), str(e)))



class lrms(clueslib.platform.LRMS):

    def __init__(self, DOCKER_SERVER = None, DMACHINE_VM_LIST = None, DMACHINE_VM_INSPECT = None, SWARM_TOKEN = None, CONTAINERS_PER_HOST = None):
        config_docker = cpyutils.config.Configuration(
            "DOCKER",
            {
                "DOCKER_SERVER": "http://127.0.0.1:8880",
                "DMACHINE_VM_LIST": "/usr/local/bin/docker-machine ls",
                "DMACHINE_VM_INSPECT":"/usr/local/bin/docker-machine inspect ",
                "SWARM_TOKEN":"0ac50ef75c9739f5bfeeaf00503d4e6e",
                "CONTAINERS_PER_HOST":"5"
            }
        )
        # config_docker = cpyutils.config.Configuration("DWRAPPER", {"DWRAPPER_SERVER": "dwrapperserver"})
        self._server_ip = clueslib.helpers.val_default(DOCKER_SERVER, config_docker.DOCKER_SERVER)
        self._vm_list = clueslib.helpers.val_default(DMACHINE_VM_LIST, config_docker.DMACHINE_VM_LIST)
        self._vm_inspect = clueslib.helpers.val_default(DMACHINE_VM_INSPECT, config_docker.DMACHINE_VM_INSPECT)
        self._swarm_token = clueslib.helpers.val_default(SWARM_TOKEN, config_docker.SWARM_TOKEN)
        self._containers_per_host = int(clueslib.helpers.val_default(CONTAINERS_PER_HOST, config_docker.CONTAINERS_PER_HOST))
        clueslib.platform.LRMS.__init__(self, "DWRAPPER_%s" % self._server_ip)

    def get_nodeinfolist(self):
        nodeinfolist = {}
        cmd = run_command(self._vm_list.split(" "))
        vm_nodes = cmd.split('\n')
        worker_nodes = get_worker_nodes_list_from_docker_wrapper(self._server_ip)
        if len(vm_nodes)>1:
            del vm_nodes[0]
            for node in vm_nodes:
                activity = ""
                name = ""
                slots = 0
                slots_free = 0
                memory = 0
                memory_free = 0
                keywords = {}
                queues = []
                if "tcp" in node or "Stopped" in node:
                    name = node[0: node.index(' ')]
                    node =node[node.index(' '):].strip()
                    node =node[node.index(' '):].strip()
                    node =node[node.index(' '):].strip()
                    activity = node[0: node.index(' ')]
                    node = run_command((self._vm_inspect+" "+name).split(" "))
                    node =json.loads(node)
                    if self._swarm_token in node["Driver"]["SwarmDiscovery"] and not node["Driver"]["SwarmMaster"]:
                        if name not in worker_nodes:
                            slots = self._containers_per_host
                            slots_free = slots
                            used_mem = 0
                            total_mem = node["Driver"]["Memory"]
                            memory_free = float(total_mem) - float(used_mem)
                        else:
                            try:
                                slots = self._containers_per_host
                                slots_free = self._containers_per_host
                            except:
                                slots = 0
                                slots_free = slots
                            try:
                                used_mem = float(worker_nodes[name]["RAM"])*float(node["Driver"]["Memory"])
                                total_mem = node["Driver"]["Memory"]
                                memory = float(total_mem)
                                memory_free = float(total_mem) - float(used_mem)
                            except:
                                memory =  0
                                memory_free = memory

                        keywords['hostname'] = TypedClass.auto(name)
                        queues = ["default"]
                        keywords['queues'] = TypedList([TypedClass.auto(q) for q in queues])
                        nodeinfolist[name] = NodeInfo(name, slots, slots_free, memory, memory_free, keywords)
                        try:
                            running_cont = worker_nodes[name]["Containers"]
                        except:
                            running_cont = 0

                        try:
                            if activity=="Running":
                                if int(running_cont) > 0:
                                    nodeinfolist[name].state = NodeInfo.USED
                                elif int(running_cont) == 0:
                                    nodeinfolist[name].state = NodeInfo.IDLE
                            else:
                                nodeinfolist[name].state = NodeInfo.OFF
                        except:
                            nodeinfolist[name].state = NodeInfo.UNKNOWN
            return nodeinfolist
        else:
            _LOGGER.warning("could not obtain information about nodes.")
            return None


    def get_jobinfolist(self):
        jobinfolist = []
        schedulers = get_schedulers_list_from_docker_wrapper(self._server_ip)
        if len(schedulers) > 0:
            for scheduler in schedulers:
                status = scheduler["Status"]
                scheduler = scheduler["Data"]

                cpus_per_task = 0.0
                try:
                    cpus_per_task = float(scheduler["HostConfig"]["CpuCount"])
                except:
                    cpus_per_task =  0.0
                memory = 0
                try:
                    memory =  float(scheduler["HostConfig"]["MemoryReservation"])
                except:
                    memory =  0
                queue = '"default" in queues'
                nodes = []
                numnodes = 0
                job_id = ""
                try:
                    image = scheduler["Image"]
                    job_id = str(image) + "." + scheduler["Id"]
                except:
                    job_id = ""
                state = ""
                if "pending" in status:
                    state = clueslib.request.Request.PENDING
                else:
                    state = clueslib.request.Request.ATTENDED

                resources = clueslib.request.ResourcesNeeded(cpus_per_task, memory, [queue], numnodes)
                j = clueslib.request.JobInfo(resources, job_id, nodes)
                j.set_state(state)
                jobinfolist.append(j)
        else:
            _LOGGER.warning("could not obtain information about jobs.")
            return None
        return jobinfolist

if __name__ == '__main__':
    pass

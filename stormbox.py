#!/bin/python

"""
Stormbox
Copyright 2019 Carnegie Mellon University.
NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.
Released under a MIT (SEI)-style license, please see license.txt or contact permission@sei.cmu.edu for full terms.
[DISTRIBUTION STATEMENT A] This material has been approved for public release and unlimited distribution.  Please see Copyright notice for non-US Government use and distribution.
Carnegie Mellon® and CERT® are registered in the U.S. Patent and Trademark Office by Carnegie Mellon University.
This Software includes and/or makes use of the following Third-Party Software subject to its own license:
1. Docker (https://www.docker.com/legal/components-licenses) Copyright 2019 Docker, Inc..
DM19-1123
"""

# WARNING - Do not have more containers than IPs
# TODO - Function to take out networks once IPs exhausted, right now will just crash

import subprocess
import random
import collections
import re
import datetime
import time
import json
import IPy
import ConfigParser
import os

# constant
sys_net = '/sys/class/net/'

class weighted_random_picker(object):
    def __init__(self, weighted_tuples):
        self.__values = []
        self.__index = []
        for value, weight in weighted_tuples:
             self.__values.append(value)
             self.__index.append(float(weight))

    def choice(self):
        random_number = random.random() * sum(self.__index)
        for index_number, weight in enumerate(self.__index):
            random_number -= weight
            if random_number < 0:
                 return self.__values[index_number]

class IP_Master(object):
    def __init__(self, ip_pools):
        self.ipam = ip_pools

    def request(self, network_name):
        if network_name in self.ipam.keys():
            choice = random.choice(self.ipam[network_name])
            self.ipam[network_name].remove(choice)
            return choice
        else:
            return None

    def return_ip(self, network_name, ipaddress):
        if network_name in self.ipam.keys():
             self.ipam[network_name].append(ipaddress)
             return 'ok'
        else:
             return 'error'

    def remove_ip(self, network_name, ipaddress):
        if network_name in self.ipam.keys():
             self.ipam[network_name].remove(ipaddress)
             return 'ok'
        else:
             return 'error'

class Control(object):
    def __init__(self, config):
        #assign control variables for type int
        self.number_of_containers_goal = config.getint('control', 'number_of_containers_goal')
        self.min_container_value = config.getint('control', 'min_container_value')
        self.sleep_floor = config.getint('control', 'sleep_floor')
        self.sleep_ceiling = config.getint('control', 'sleep_ceiling')
        #assign control variables for type float
        self.pruning_ratio = config.getfloat('control', 'pruning_ratio')
        self.churn_rate = config.getfloat('control', 'churn_rate')
        self.kill_ratio = config.getfloat('control', 'kill_ratio')
        #assign control variable for type string
        self.dns_server = config.get('control', 'dns_server')
        self.host_dir = config.get('control', 'host_dir')
        self.images = []
        image_items = config.items("images")
        for key, j in image_items:
            this = json.loads(j)
            t = (this["name"], this["weight"])
            self.images.append(t)
            
def get_config():
    # add test for file and read permissions
    config = ConfigParser.ConfigParser()
    config.read('/etc/stormbox/stormbox.conf')
    return config

def create_config_dict(config, section):
    tuples = config.items(section)
    dict_vars = {}
    for t in tuples:
        dict_vars[t[0]] = t[1]
    return dict_vars

device_t = collections.namedtuple('device', 'ifindex, name')

def get_net_devices(root):
    dirs = os.listdir(root)
    return dirs

def make_index_mapping(devices, root):
    table = {}
    for dev in devices:

        with open(root + dev + '/ifindex', 'r') as f:
            index_number = f.readlines()
            #need error checking
            ifindex = index_number[0].rstrip()
            table[ifindex] = dev
    return table

def get_sb_networks():
     sb_networks_gi = 'guestinfo.sb.networks'
     sb_networks = subprocess.check_output(['vmtoolsd', '--cmd', 'info-get %s' % sb_networks_gi]).strip()
     networks_split = sb_networks.split(' ')
     nets = []
     for net in networks_split:
         if net:
             nets.append(net)
     return nets


## takes the table-> name mapping from above and generates docker networks
def create_bridge_networks(ifindexes):
    sbnets = get_sb_networks()
    existing_networks = generate_network_list()
    for sbnet in sbnets:
        subnet_gi = 'guestinfo.%s.subnet' % sbnet
        netname_gi = 'guestinfo.%s.name' % sbnet
        index_gi = 'guestinfo.%s.index' % sbnet
        gateway_gi = 'guestinfo.%s.gateway' % sbnet

        index = subprocess.check_output(['vmtoolsd', '--cmd', 'info-get %s' % index_gi]).strip()
        ifname = ifindexes[index]
        netname = subprocess.check_output(['vmtoolsd', '--cmd', 'info-get %s' % netname_gi]).strip()
        if netname in existing_networks:
            ensure_bridge_has_interface("br-" + netname, ifname)
            make_interface_up(ifname)
            continue
        gateway = subprocess.check_output(['vmtoolsd', '--cmd', 'info-get %s' % gateway_gi]).strip()
        subnet = subprocess.check_output(['vmtoolsd', '--cmd', 'info-get %s' % subnet_gi]).strip()

        create_network_cmd = subprocess.check_output(['docker', 'network', 'create', '-o', 'com.docker.network.bridge.name=br-%s' % netname, "--subnet", "%s" % subnet, "--gateway", "%s" % gateway, "%s" % netname])
        make_interface_up(ifname)
        ensure_bridge_has_interface("br-" + netname, ifname)

def check_bridge_interface(bridgename):
    interface = os.listdir('/sys/class/net/%s/brif/' % bridgename)
    if not interface:
        return None
    else:
        return interface[0]

def ensure_bridge_has_interface(bridgename, interfacename):
    check = check_bridge_interface(bridgename)
    if check is None:
        addif = subprocess.check_output(["brctl", "addif", "%s" % bridgename,  "%s" % interfacename])
        return
    if check != interfacename:
        print("Interface mapping error - %s expects %s but using %s" % (bridgename, interfacename, check))
        exit()


def make_interface_up(interface):
    file_path = "/sys/class/net/%s/operstate" % interface
    with open(file_path, 'r') as f:
        status = f.readline().strip()
        if status == 'up':
            return
        else:
            up = subprocess.check_output(["ip", "link", "set", "dev", "%s" % interface, "up"])


def remove_all_ips_from_config(config, ipam):
    items = config.items("ipam")
    for key, j in items:
        this = json.loads(j)
        network_name = this['name']
        ip_list = this['ip']
        for ip in ip_list:
            ipam.remove_ip(network_name, ip)
       

def now():
    d = datetime.datetime.now()
    return_d = d.strftime("%Y/%m/%d-%H:%M")
    return return_d


def process_docker_ps_line(line):
   if line == '':
      return None
   container = collections.namedtuple('container', 'c_id, imagename, command, created, status, name, ports')
   c_id = None
   imagename = None
   command = None
   created = None
   status = None
   name = None
   ports = None

   try:
       c_id, imagesname, command, created, status, name = re.split('\s{2,}', line)
   except:
       try:
           c_id, imagename, command, created, status, ports, name = re.split('\s{2,}', line)
       except Exception as e:
           print('still has exception in docker ps -a processing - %s\n line: %s' % (e, line))
           return None

   if name == "registry" or name == "registry:2":
       return None
   this_container = container(c_id=c_id, imagename=imagename, command=command, created=created, status=status, name=name, ports=ports)
   return this_container

def generate_network_list():
    networks_output = subprocess.check_output(["docker", "network", "ls"])
    split_output = networks_output.split('\n')
    networks = []
    for line in split_output[1:]:
        if line:
            dockerid, name, driver = line.split()
            if driver == 'bridge' and name != 'bridge':
                networks.append(name)
    return networks

def get_existing_containers():
    containers = []
    ps_output = subprocess.check_output(["docker", "ps", "-a"])
    ps_split = ps_output.split('\n')
    for line in ps_split[1:]:

        this = process_docker_ps_line(line)
        if this is not None:
            containers.append(this)
    return containers

def get_highest_container_number(prefix):

    containers = get_existing_containers()
    if not containers or len(containers) < 2:
        return 2
    if isinstance(containers, list):
                
        list_of_numbers = map(lambda x: re.findall('\d+', x.name), containers)
        sorted_list_of_numbers = sorted([int(item[0]) for item in list_of_numbers if item]) 
        highest = int(sorted_list_of_numbers.pop())
        #print(sorted_list_of_numbers) 
        return highest
    else:
        
        return 1

def get_current_container_count():
	containers = get_existing_containers()
	not_registry = filter(lambda x: x.name != 'registry', containers)
	return len(containers)



def create_network_ip_pools(network_list):

    ipam = {}

    for network in network_list:

        raw_output = subprocess.check_output(["docker", "network", "inspect", "%s" % network])
        json_output = json.loads(raw_output)
        this_subnet = str(json_output[0]['IPAM']['Config'][0]['Subnet'])
        this_gateway = str(json_output[0]['IPAM']['Config'][0]['Gateway'])
        ipy_object = IPy.IP(this_subnet)
        this_range = map(lambda x: x.strNormal(), ipy_object)
        ipam[network] = this_range
        ipam[network].remove(this_gateway)
        #ipam[network].remove(ipy_object.broadcast())

    return ipam





def spawn_containers(howmany, name_prefix_chooser, networks, ipam_master):
    name_prefix = name_prefix_chooser.choice()
    start_number = get_highest_container_number(name_prefix)
    for number in xrange(start_number + 1, start_number + howmany + 1):
        this_network = random.choice(networks)
        this_name = name_prefix_chooser.choice() + str(number)
        ip = ipam_master.request(this_network)
        print("%s: spawning %s" % (now(),this_name))
        try: 
            this_output = subprocess.check_output(["docker", "run", "--dns=%s" % storm_control.dns_server, "-v", "%s" % storm_control.host_dir, "--name", "%s" % this_name, "--net", "%s" % this_network, "--ip", "%s" % ip, "-d", "%s" % name_prefix])
        except subprocess.CalledProcessError as e:
            print("failed to deploy container -> %s" % e)

def choose_random_containers(howmany, containers):
    return_these_containers = []
    if not containers:
        return return_these_containers
    for number in xrange(1,howmany):
        this_container = random.choice(containers)
        containers.remove(this_container)
    	return_these_containers.append(this_container)
    return return_these_containers

def kill_containers(containers, ipam_master):
    remove_these_containers = map(lambda x: x.c_id, containers)
    print("%s: killing these containers %s" % (now(), remove_these_containers))
    for container in remove_these_containers:
        try:
            this_raw_output = subprocess.check_output(["docker", "inspect", "%s" % container])
            json_config = json.loads(this_raw_output)
            this_ip = str(json_config[0]['NetworkSettings']['Networks'][json_config[0]['NetworkSettings']['Networks'].keys()[0]]['IPAddress'])
            this_network_name = str(json_config[0]['NetworkSettings']['Networks'].keys()[0])
            ipam_master.return_ip(this_network_name, this_ip)
        except Exception as e:
            print("failed to cleanup IPs %s %s" % (container, e))
    try:
        rm_output = subprocess.check_output(["docker", "rm", "-f"] + remove_these_containers)
    except Exception as e:
        print("remove failed, %s" % e)

def administer_containers(networks, name_prefix_chooser, ipam_master): 
    container_list = get_existing_containers()
    container_count = len(container_list)
    if container_count < storm_control.min_container_value:
        container_count = storm_control.min_container_value
    if container_count >= storm_control.number_of_containers_goal:
        thismany = int(storm_control.number_of_containers_goal * storm_control.pruning_ratio)
        kill_containers(choose_random_containers(thismany, container_list), ipam_master)
    elif random.random() < storm_control.churn_rate and container_count > storm_control.min_container_value + 2:
        kill_this_many = int(container_count * storm_control.kill_ratio)
        if kill_this_many > container_count:
            return 0
        kill_containers(choose_random_containers(kill_this_many, container_list), ipam_master)
    else:
        spawn_this_many = storm_control.number_of_containers_goal / container_count
        spawn_containers(spawn_this_many, name_prefix_chooser, networks, ipam_master)

### main program starts here ###
if __name__ == '__main__':
    net_devices = get_net_devices(sys_net)
    net_devices_table = make_index_mapping(net_devices, sys_net)
    create_bridge_networks(net_devices_table)
    networks = generate_network_list()
    ip_pools = create_network_ip_pools(networks)
    ipam_master = IP_Master(ip_pools)
    storm_config = get_config()
    storm_control = Control(storm_config)
    name_prefix_chooser = weighted_random_picker(storm_control.images)
    remove_all_ips_from_config(storm_config, ipam_master)
    keep_going = True
    while keep_going is True:
        try:
            #pdb.set_trace()
            administer_containers(networks, name_prefix_chooser, ipam_master)
            time.sleep(random.randint(storm_control.sleep_floor, storm_control.sleep_ceiling))
        except KeyboardInterrupt:
            print "Caught Interupt, spinning down containers and exiting"
            kill_these = get_existing_containers()
            if len(kill_these) < 1:
                exit()
            else:
                kill_containers(kill_these, ipam_master)
                keep_going = False

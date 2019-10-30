<!--
Stormbox
Copyright 2019 Carnegie Mellon University.
NO WARRANTY. THIS CARNEGIE MELLON UNIVERSITY AND SOFTWARE ENGINEERING INSTITUTE MATERIAL IS FURNISHED ON AN "AS-IS" BASIS. CARNEGIE MELLON UNIVERSITY MAKES NO WARRANTIES OF ANY KIND, EITHER EXPRESSED OR IMPLIED, AS TO ANY MATTER INCLUDING, BUT NOT LIMITED TO, WARRANTY OF FITNESS FOR PURPOSE OR MERCHANTABILITY, EXCLUSIVITY, OR RESULTS OBTAINED FROM USE OF THE MATERIAL. CARNEGIE MELLON UNIVERSITY DOES NOT MAKE ANY WARRANTY OF ANY KIND WITH RESPECT TO FREEDOM FROM PATENT, TRADEMARK, OR COPYRIGHT INFRINGEMENT.
Released under a MIT (SEI)-style license, please see license.txt or contact permission@sei.cmu.edu for full terms.
[DISTRIBUTION STATEMENT A] This material has been approved for public release and unlimited distribution.  Please see Copyright notice for non-US Government use and distribution.
Carnegie Mellon® and CERT® are registered in the U.S. Patent and Trademark Office by Carnegie Mellon University.
This Software includes and/or makes use of the following Third-Party Software subject to its own license:
1. Docker (https://www.docker.com/legal/components-licenses) Copyright 2019 Docker, Inc..
DM19-1123
-->

# Stormbox
Stormbox is an "internet user simulator" that is designed to simulate the 
transient, temporary, and anonymous nature of typical internet users during a
cyber wargame.

### Host Prequisites
Stormbox is designed to run on linux and needs the following prerequisites:

 - Python2
 - Docker
 - custom containers to perform activity 
    - currently stormbox provides:
        - a web browsing container (raindrop)
        - a botnet infected container (ambot)

### Template variables

Stormbox will use several new template variables to automatically configure
the docker networks and bridge it's physical adapters to those networks. This process
will run every time the stormbox program is started, so new networks can be added
simply by altering or appending these variables, the process is idempotent so
existing networks will not be impacted.

The new variables are defined below (set should be used in templates, but omitted if modifying notes directly):

**set.sb.networks** - This variable is a list of the variable groups that should be checked.

`Example: set.sb.networks = s1 s2 s3`

**set.s1.index** - This defines what index the network card that is associated with the s1
configuration data will use. These indexes will be in nic order starting at 2. (1 is used for lo)
(This is in place of device names like eth0 or ens33, since in some versions of centos that name
is difficult to predict)

`Example: set.s1.index = 2`

**set.s1.name** - This is the name that should be assigned to the docker network. An associated
bridge network will be created by prepending br- to this name.

`Example: set.s1.name = red1`

**set.s1.subnet** - This is the network that stormbox should use for this interface in CIDR notation.
Stormbox will use this to generate an internal IPAM system and randomly assign IP addresses from it.

`Example: set.s1.subnet = 94.228.204.0/24`

**set.s1.gateway** - This is the gateway to be used by all machines in this network.

`Example: set.s1.gateway = 94.228.204.1`

In order to keep adding networks, simply increment the s value and append to the list at sb.networks.


## Stormbox configuration file
Stormbox requires a configuration file at **/etc/stormbox/stormbox.conf**.
Please use stormbox.conf.example as an example configuration file. Many of these
values influence the rate at which containers are spawned or killed.

### Configuration variables

#### [control]

The following variables control the rate at which containers are spawned and killed.
These variables fall under the [control] section of the configuration file.

**number_of_containers_goal** [int] - This variable controls the "soft maximum" amount of containers.
As long as the current container count is less than this variable, stormbox will use randomization and
other config variables to determine if containers should be spawned or killed. Once the number of
containers meets of exceeds this value, the chance to kill containers becomes 100%.

**min_container_vale** [int] - this value will be substited for the number of active containers
anytime the true value is lower than it.

**sleep_floor** [int] - It is the lowest number of seconds stormbox will sleep after each "tick".

**sleep_ceiling** [int] - The highest number of seconds stormbox will sleep after each tick.

**spawn_divider** [int] - This variable influences the rate at which containers are spawned using this formula:
*number_of_containers_goal* / (*spawn_divider* * random(1,100))

**pruning_ratio** [float] - This variable is used to control how many containers should be killed if
the *number_of_containers_goal* value is exceeded. This percentage of active containers will be killed.

**churn_rate** [float] - This value controls what percentage of the time containers should be "randomly" killed.

**kill_ratio** [float] - This value controls how what percentage of active containers should be killed after 
a *churn_rate* triggered culling.

The following variables remain under the [control] section but are simply environmental values
used in the creation of containers.

**dns_server** [string] - The dns server that spawned containers should use.

**host_dir** [string] - The local host directory which should be mounted in the containers. (used for easily passing configuration data)

#### [images]


The next section of the config file is used to define the rate at which container types are chosen. 
The current container types provided are: *raindrop* and *ambot* but more types can be easily added.


All values in this section should be incremented using this model:
image_1
image_2
image_3
etc

The value of each incremented image should be a json formatted string giving
the name of the container type (docker image) and it's weight (liklihood of being chosen).
For example, this is what a typical "browsing only" config might look like:

```
image_1 = {"name": "raindrop", "weight": 100}
image_2 = {"name": "ambot", "weight": 0}
```

#### [ipam]

The final section of the configuration file allows certain IP addresses to be removed from stormbox's internal IPAM.

This functions in a similar manor to the [images] section and each entry should be incremented in this pattern:
remove_1
remove_2
remove_3
etc

It also expects a json formatted string containing the name of network and any IP addresses that should be removed.
An example may look like the following:

```
remove_1 = {"name": "red1", "ip": [" 94.228.204.200", "94.228.204.201", '94.228.204.210" ] }
```
### Images

#### Raindrop
The raindrop containers will simply browse (GETs. POSTs) any websites listed in the host_dir for the following files:
websites.list - contains list of sites to browse
post-strings.list - lists of paths to appends to random posts
user-agents.list - lists useragents and their percent chance to be selected

#### Ambot
Ambot specific instructions here.

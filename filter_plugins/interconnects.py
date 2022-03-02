#!/usr/bin/python
import time
import random
from collections import OrderedDict

import jinja2

class FilterModule(object):
    def filters(self):
        return {
            'all_vars': self._all_vars,
            'join_devices': self._join_devices,
            'generate_links': self._generate_links,
            'build_interconnects': self.build_interconnects,
            'build_topology': self.build_topology,
        }

    def _all_vars(self, hostnames, hostvars):
        """
        hostnames expects 'ansible_play_hosts' and hostvars expects 'hostvars' passed from ansible, these are special variables, RTFM

        returns: a list of dictionaries of all inventory items with all variables gleaned from host_vars, group_vars, etc

        """
        # We need to take in all of the hostvars and put them in a list
        all_vars = []
        for host in hostnames:
            all_vars.append(hostvars[host])
        return all_vars

    def _join_devices(self, hostnames, hostvars):
        """
        hostnames expects 'ansible_play_hosts' and hostvars expects 'hostvars' passed from ansible, these are special variables, RTFM

        uses the _all_vars method in this class to gather all of the data

        Expects these variables to be passed into ansible by host_vars, group_vars or topology file
        
        ****REQUIRED**** Inputs per device

        hostname(str): the hostname of the device
        id(int): unique id of the device in the network
        
        interfaces(list of dictionaries):
            type(str): interface type
            number(str or int): interface number
            remote_node_id(int): is the 'z' device-id this interface is connected to

        ****Optional**** Inputs per device
        rack(dictionary):
            name(str): name of the rack
            position(int): rack unit the device is installed


        Example - host_vars/core01rtr.yml
        ---
        hostname: core01rtr
        id: 30

        interfaces:
          - type: GigabitEthernet
            number: 0/0/0/1
            remote_node_id: 90
          - type: GigabitEthernet
            number: 0/0/0/2
            remote_node_id: 91

        rack:
          name: R-01-01-02
          position: 21

        returns: a list of dictionaries that figures out how devices are connected together

        """
        items = self._all_vars(hostnames, hostvars)
        # Use the hostvars from Ansible
        links = []
        link = {}

        for host in items:
            index = 0
            for interface in host["interfaces"]:
                interface["id"] = "i{}".format(index)  # For CML Topology file, needs to have a unique ID per device
                index += 1
                # Filter out any interface in CML or interconnects that doesn't have a cross-connect - i.e. Loopback Int
                if "remote_node_id" in interface:
                    link["a_id"] = host["id"]
                    link["a_hostname"] = host["hostname"]
                    link["a_type"] = interface["type"]
                    link["a_number"] = interface["number"]
                    link["z_id"] = interface["remote_node_id"]
                    link["a_link_id"] = interface["id"]
                    try:
                        link["a_rack"] = host["rack"]["name"]
                        link["a_rack_pos"] = host["rack"]["position"]
                    except KeyError:
                        link["a_rack"] = ""
                        link["a_rack_pos"] = ""
                    links.append(dict(link))

        # Join the interconnects together by matching the remote node ID from host_vars
        for link in links:
            for host in items:
                index = 0
                # Match the two devices together
                if link["z_id"] == host["id"]:
                    for interface in host["interfaces"]:
                        if "remote_node_id" in interface and interface["remote_node_id"] == link["a_id"]:
                            link["z_hostname"] = host["hostname"]
                            link["z_type"] = interface["type"]
                            link["z_number"] = interface["number"]
                            link["z_link_id"] = "i{}".format(index)
                            try:
                                link["z_rack"] = host["rack"]["name"]
                                link["z_rack_pos"] = host["rack"]["position"]
                            except KeyError:
                                link["z_rack"] = ""
                                link["z_rack_pos"] = ""
                            index += 1

        return links

    # Interconnects
    def build_interconnects(self, hostnames, hostvars):
        """
        hostnames expects 'ansible_play_hosts' and hostvars expects 'hostvars' passed from ansible, these are special variables, RTFM

        uses the _join_devices method in this class to first filter the data

        returns: a list of dictionaries that define how devices are connected together for documentation
            also writes out a csv file with the same info to ./temp/ixcs.csv

        Example Ansible task:
        - name: Generate Interconnects
          copy: 
            content: "{{ ansible_play_hosts | build_interconnects(hostvars) | to_nice_json }}"
            dest: temp/ixcs.json
        """
        ixcs = self._join_devices(hostnames, hostvars)
        final_link = {}
        final_links = []
        index = 0

        for link in ixcs:
            try:
                final_link["a_hostname"] = link["a_hostname"]
                final_link["a_interface"] = "{}{}".format(link["a_type"], link["a_number"])
                final_link["a_rack"] = link["a_rack"]
                final_link["a_rack_pos"] = link["a_rack_pos"]
                final_link["z_hostname"] = link["z_hostname"]
                final_link["z_interface"] = "{}{}".format(link["z_type"], link["z_number"])
                final_link["z_rack"] = link["z_rack"]
                final_link["z_rack_pos"] = link["z_rack_pos"]
                final_links.append(dict(final_link))
            except KeyError:
                print("build_interconnects KeyError {}".format(link))

        output = {}
        output["ixcs"] = final_links

        import csv
        header = ["a_hostname", "a_interface", "a_rack", "a_rack_pos", "z_hostname", "z_interface", "z_rack", "z_rack_pos"]
        with open("temp/ixcs.csv", "w") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames = header)
            writer.writeheader()
            writer.writerows(output["ixcs"])

        return output

    # CML Stuff
    def _generate_links(self, hostnames, hostvars):
        """
        hostnames expects 'ansible_play_hosts' and hostvars expects 'hostvars' passed from ansible, these are special variables, RTFM

        uses the _join_devices method in this class understand how things are connected

        returns: a list of dictionaries that CML uses in the topology file

        """
        # generate the links dictionary that CML expects
        links = self._join_devices(hostnames, hostvars)
        final_link = {}
        final_links = []
        index = 0

        for link in links:
            try:
                final_link["id"] = "l{}".format(index)
                final_link["i1"] = link["a_link_id"]
                final_link["n1"] = "n{}".format(link["a_id"])
                final_link["i2"] = link["z_link_id"]
                final_link["n2"] = "n{}".format(link["z_id"])
                index += 1
                final_links.append(dict(final_link))
            except KeyError:
                print("_generate_links KeyError {}".format(link))

        return final_links

    def _render_bootstrap_config(self, config_dict):
        """
        config_dict(dictionary): this is the dictionary that contains a couple variables gleaned from variables

        Expects these variables to be passed into ansible by host_vars, group_vars or topology file
        
        ****REQUIRED****
        
        render_config(dictionary):
            type(str): subfolder that exists in ./temp to look for the jinja template
            cml_template(str): jinja2 template name that will be rendered for bootstrap config in CML

        Example - group_vars/iosxe.yml
        ---
        render_config:
          type: iosxe
          cml_template: cml_bootstrap.j2

        returns: nothing useful

        """
        env = jinja2.Environment(loader=jinja2.FileSystemLoader("./templates/configs"))

        try:
            bootstrap_template = env.get_template("{}/{}".format(config_dict["version"], config_dict["template"]))
        except jinja2.TemplateNotFound as err:
            print("Template not found {}".format(err))
            return

        config = bootstrap_template.render(config_dict)
        return config

    def build_topology(self, hostnames, hostvars):
        """
        hostnames expects 'ansible_play_hosts' and hostvars expects 'hostvars' passed from ansible, these are special variables, RTFM

        uses the _all_vars method in this class to gather all of the data
        uses the _generate_links method in this class to provide link data for CML
        uses the _render_bootstrap_config method in this class to create a bootstrap config

        ****NOTE****
        in the config_dict section, make sure the variables are defined in the hostvars that you want rendered in the Jinja2 template
        
        ****REQUIRED****
        hostname(str): the hostname of the device
        id(int): unique id of the device in the network
        
        interfaces(list of dictionaries):
            type(str): interface type
            number(str or int): interface number
            remote_node_id(int): is the 'z' device-id this interface is connected to

        cml(dictionary):
            image_def(str): image definition predefined in CML server
            node_def(str): node definition predefined in CML server

        render_config(dictionary):
            type(str): subfolder that exists in ./templates to look for the jinja template
            cml_template(str): jinja2 template name that will be rendered for bootstrap config in CML

        ****Optional**** Inputs per device
        cords(dictionary): coordinates in CML, defaults to random placement
            x(str): x coordinates
            y(str): y coordinates

        Example - group_vars/iosxe.yml
        ---
        cml:
          image_def: csr1000v-170301a
          node_def: csr1000v

        render_config:
          type: iosxe
          cml_template: cml_bootstrap.j2

        Example - host_vars/core01rtr.yml
        ---
        hostname: core01rtr
        id: 30

        interfaces:
          - type: GigabitEthernet
            number: 0/0/0/1
            remote_node_id: 90
          - type: GigabitEthernet
            number: 0/0/0/2
            remote_node_id: 91
        
        cords:
          x: -250
          y: -50
        returns: a dictionary that describes what the CML topology looks like

        Example Ansible task:
        - name: Build CML Topology
          copy: 
            content: "{{ ansible_play_hosts | build_topology(hostvars) | to_nice_yaml }}"
            dest: temp/topology.yaml

        """

        # Stupid IOSvL2 definition doesn't just increment the interface numbers - smh
        iosvl2_ints = ["0/0", "0/1", "0/2", "0/3", "1/0", "1/1", "1/2", "1/3", "2/0", "2/1", "2/2", "2/3", "3/0", "3/1", "3/2", "3/3"]
        
        items = self._all_vars(hostnames, hostvars)
        topology_file = {
            "lab": {
                "description": "Test Topology generated by Ansible",
                "notes": "",
                "timestamp": int(time.time()),
                "title": "Test Topology",
                "version": "0.0.1"
            }
        }
        nodes = []
        node = {}
        for host in items:
            # Render bootstrap config
            configs_to_render = ["iosxrv9000", "iosvl2", "csr1000v"]
            if host["cml"]["node_def"].lower() in configs_to_render:
                try:
                    config_dict = {}
                    config_dict["template"] = host["render_config"]["cml_template"]
                    config_dict["version"] = host["render_config"]["type"]
                    config_dict["hostname"] = host["hostname"].upper()
                    config_dict["vrf_name"] = host["management_network"]["vrf_name"]
                    config_dict["gateway"] = host["management_network"]["gateway"]
                    config_dict["aaa_hostname"] = host["aaa_config"]["hostname"]
                    config_dict["aaa_key"] = host["aaa_config"]["key"]
                    config = self._render_bootstrap_config(config_dict)
                except KeyError as err:
                    print("Render J2 KeyError {} error {}".format(host["hostname"], err))
                    config = ""

            node["id"] = "n{}".format(host["id"])
            node["label"] = host["hostname"].upper()
            node["node_definition"] = host["cml"]["node_def"]
            try:
                node["x"] = host["cords"]["x"]
            except KeyError:
                node["x"] = random.randint(-300, 300)
            try:
                node["y"] = host["cords"]["y"]
            except KeyError:
                node["y"] = random.randint(-300, 300)

            if host["cml"]["node_def"].lower() == "external_connector":
                node["configuration"] = "bridge1"
            else:
                node["configuration"] = "|-\n{}".format(config)
            try:
                node["image_definition"] = host["cml"]["image_def"]
            except KeyError:
                pass
            node["tags"] = []

            # Interface Stuff
            index = 0
            interface = {}
            interfaces = []
            for iface in host["interfaces"]:
                try:
                    interface["id"] = "i{}".format(index)
                    interface["slot"] = index
                    if host["cml"]["node_def"] == "external_connector":
                        interface["label"] = "port"
                    elif host["cml"]["node_def"] == "iosxrv9000":
                        # We need to renumber the interfaces since iosxr9000 definition only uses GE interfaces
                        interface["label"] = "GigabitEthernet0/0/0/{}".format(index)
                    elif host["cml"]["node_def"] == "csr1000v":
                        # We need to renumber the interfaces since csr1000v definition only uses GE interfaces
                        interface["label"] = "GigabitEthernet{}".format(index + 1)
                    elif host["cml"]["node_def"] == "iosvl2":
                        # We need to renumber the interfaces since iosvl2 definition only uses GE interfaces
                        interface["label"] = "GigabitEthernet{}".format(iosvl2_ints[index])
                    else:
                        interface["label"] = "{}{}".format(iface["type"], iface["number"])
                    
                    if iface["type"].lower() == "loopback":
                        interface["type"] = "Loopback"
                    else:
                        interface["type"] = "physical"
                    index += 1
                    interfaces.append(dict(interface))
                except KeyError:
                    print("KeyError {}{}".format(host["hostname"], iface))
            node["interfaces"] = interfaces
            nodes.append(dict(node))

        topology_file["nodes"] = nodes
        topology_file["links"] = self._generate_links(hostnames, hostvars)

        return topology_file


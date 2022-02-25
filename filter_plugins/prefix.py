#!/usr/bin/python
import json
import pynetbox

class FilterModule(object):
	def filters(self):
		return {
			'build_dict': self.build_dict,
		}

	def build_dict(self, prefixes, site_slug):
		data = {}
		output = []
		for prefix in prefixes["ipv4"]:
			data["description"] = prefix["description"]
			data["family"] = 4
			data["parent"] = "172.16.0.0/12"
			data["prefix_length"] = prefix["prefix_length"]
			data["is_pool"] = False
			data["status"] = "container"
			data["prefix_role"] = prefix["prefix_role"]
			data["site"] = site_slug
			output.append(dict(data))
		for prefix in prefixes["ipv6"]:
			data["description"] = prefix["description"]
			data["family"] = 6
			data["parent"] = "fd00::/8"
			data["prefix_length"] = prefix["prefix_length"]
			data["is_pool"] = False
			data["status"] = "container"
			data["prefix_role"] = prefix["prefix_role"]
			data["site"] = site_slug
			output.append(dict(data))
		return output


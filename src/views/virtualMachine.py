from app import app
from app import DBSession
from util import multikeysort
from flask import request
from flask import jsonify
from os import system
import libvirt
import xml.etree.ElementTree as ET
import string,random

CONFIG_XML = 'views/config_new.xml'

def randomString(size=6, chars=string.ascii_uppercase + string.digits):
	return ''.join(random.choice(chars) for x in range(size))

def vmGetEmulator(sysArch):

	emulators = {}
	emulators['i386'] = "/usr/bin/qemu-system-i386"
	emulators['i686'] = "/usr/bin/qemu-system-x86_64"
	emulators['x86_64'] = "/usr/bin/qemu-system-x86_64"

	return emulators[sysArch]

def vmGetXML(xmlFile,instanceDetails,imageFile,machine):

	ram = str(int(instanceDetails['ram']) * 1024)
	cpu = str(instanceDetails['cpu'])
	disk = str(instanceDetails['disk'])
	name = instanceDetails['name']

	tree = ET.parse(xmlFile)
	root = tree.getroot()

	root.find('name').text = name
	root.find('memory').text = ram
	root.find('currentMemory').text = ram
	root.find('vcpu').text = cpu
	root.find('devices').find('disk').find('source').attrib['file'] = imageFile
	root.find('devices').find('emulator').text = machine['emulator']
	root.find('os').find('type').attrib['arch'] =  machine['arch']

	return ET.tostring(root)

def vmConnect(machine):

	conn = libvirt.open("qemu+ssh://" + machine + "/system")
	return conn

def vmDisconnect(connection):

	connection.close()

def vmGetPhysicalMachine(instanceDetails):

	memory = int(instanceDetails['ram'])
	cpu = int(instanceDetails['cpu'])

	machines = DBSession.machine_info.find()
	machines = multikeysort(machines,['cpus','memory'])
	for machine in machines:
		if cpu <= int(machine['cpus']) and memory <= int(machine['memory']):
			if memory < 2047:
				return int(machine['_id'])
			elif memory >= 2047 and machine['arch'] == 'x86_64':
				return int(machine['_id'])
	return 0

def vmUpdatePhysicalMachineInfo(pmid,memory,cpu):

	machineInfo = DBSession.machine_info.find_one({'_id':pmid})
	DBSession.machine_info.update(	{'_id':pmid},
					{'$set':{	'memory': memory,
							'cpus': cpu
						}})


def vmCreateVirtualMachine(instanceDetails,imageDetails):

	if DBSession.instances.find_one({'name':instanceDetails['name']}) != None:
		return 0

	pmid = vmGetPhysicalMachine(instanceDetails)
	if pmid == 0:
		return 0

	machine = DBSession.machines.find_one({'_id':pmid})
	machineInfo = DBSession.machine_info.find_one({'_id':pmid})

	imageFile = vmCopyVirtualImageFile(pmid,imageDetails)
	configXML = vmGetXML(CONFIG_XML,instanceDetails,imageFile,machineInfo)

	connection = vmConnect(machine['location'])
	try:
		domain = connection.createLinux(configXML,0)
	except:
		vmDeleteVirtualImageFile(pmid,imageFile)
		return 0

	tempInstance = {}
	tempInstance['name'] = domain.name()
	tempInstance['instance_type'] = instanceDetails['tid']
	tempInstance['vmid'] = domain.UUIDString()
	tempInstance['pmid'] = pmid
	tempInstance['image_file'] = imageFile

	vmDisconnect(connection)

	vmUpdatePhysicalMachineInfo(	pmid,
					int(machineInfo['memory']) - int(instanceDetails['ram']),
					int(machineInfo['cpus']) - int(instanceDetails['cpu']))
	DBSession.instances.insert(tempInstance)

	return tempInstance['vmid']

def vmDestroyVirtualMachine(vmid):

	instance = DBSession.instances.find_one({"vmid":vmid})
	if instance != None:
		pmid = int(instance['pmid'])

		machine = DBSession.machines.find_one({'_id':pmid})
		machineInfo = DBSession.machine_info.find_one({'_id':pmid})
		instanceDetails = DBSession.vmtypes.find_one({'tid':instance['instance_type']})

		connection = vmConnect(machine['location'])
		try:
			domain = connection.lookupByUUIDString(vmid)
		except:
			return 0
		domain.destroy()
		
		vmDisconnect(connection)

		DBSession.instances.remove(instance)
		vmUpdatePhysicalMachineInfo(	pmid,
						int(machineInfo['memory']) + int(instanceDetails['ram']),
						int(machineInfo['cpus']) + int(instanceDetails['cpu']))

		vmDeleteVirtualImageFile(pmid,instance['image_file'])
		return 1
	return 0

def vmCopyVirtualImageFile(pmid,image):
	
	machine = DBSession.machines.find_one({'_id':pmid})
	imageLocationOnServer = "images/" + image['name'] + "__" + str(image['_id'])
	imageName = "/" + image['name'] + "__" + str(image['_id']) + "__" + randomString(15)

	system('scp "%s" "%s":"%s" ' % (imageLocationOnServer , machine['location'] , imageName) )
	return imageName

def vmDeleteVirtualImageFile(pmid,imageFile):

	machine = DBSession.machines.find_one({'_id':pmid})

	system('ssh "%s" rm "%s"' % (machine['location'],imageFile))

def vmGetVirtualMachineInfo(vmid):

	instance = DBSession.instances.find_one({'vmid':vmid})
	if instance == None:
		instance = {}
		instance['vmid'] = None
		instance['pmid'] = None
		instance['instance_type'] = None
		instance['name'] = None
	return instance

@app.route("/vm/create",methods=['POST', 'GET'])
def vmCreate():

	name = request.args.get('name','')
	instanceType = request.args.get('instance_type','')
	imageId = request.args.get('image_id','')

	instanceDetails = DBSession.vmtypes.find_one({"tid":int(instanceType)})
	if instanceDetails == None:
		return jsonify(vmid=0)
	instanceDetails['name'] = name

	imageDetails = DBSession.images.find_one({"_id":int(imageId)})
	if imageDetails == None:
		return jsonify(vmid=0)

	vmid = vmCreateVirtualMachine(instanceDetails,imageDetails)
	return jsonify(vmid = vmid)

@app.route("/vm/query",methods=['POST', 'GET'])
def vmQuery():

	vmId = request.args.get('vmid','')

	instance = vmGetVirtualMachineInfo(vmId)

	return jsonify(	vmid=instance['vmid'],
			name=instance['name'],
			instance_type=instance['instance_type'],
			pmid=instance['pmid'])

@app.route("/vm/destroy",methods=['POST', 'GET'])
def vmDestroy():

	vmId = request.args.get('vmid','')

	status = vmDestroyVirtualMachine(vmId)

	return jsonify(status=status)

@app.route("/vm/types",methods=['POST', 'GET'])
def vmTypes():

	types = []
	for vmtype in list(DBSession.vmtypes.find()):
		tempVM = {}
		tempVM['tid'] = vmtype['tid']
		tempVM['cpu'] = vmtype['cpu']
		tempVM['ram'] = vmtype['ram']
		tempVM['disk'] = vmtype['disk']
		types.append(tempVM)

	return jsonify(types=types)


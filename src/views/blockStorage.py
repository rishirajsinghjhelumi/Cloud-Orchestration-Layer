from app import app
from app import DBSession
from mongokit import ObjectId
from flask import request
from flask import jsonify
from os import system
import libvirt
import rados
import rbd
import re
import subprocess
from random import choice
import xml.etree.ElementTree as ET
from virtualMachine import *

POOL_NAME = 'S3crEt'
CONF_FILE = '/etc/ceph/ceph.conf'
BLOCK_CONFIG_XML = 'views/block_config.xml'
HOST_NAME = 'localhost'

radosConnection = rados.Rados(conffile=CONF_FILE)
radosConnection.connect()
if POOL_NAME not in radosConnection.list_pools():                                
	radosConnection.create_pool(POOL_NAME)
ioctx = radosConnection.open_ioctx(POOL_NAME)

rbdInstance = rbd.RBD()

def getHostName():

	global HOST_NAME
	monProc = subprocess.Popen("ceph mon_status", shell=True, bufsize=0, stdout=subprocess.PIPE, universal_newlines=True) 
	monDict = eval(monProc.stdout.read())
	HOST_NAME = monDict['monmap']['mons'][0]['name']

	print HOST_NAME

getHostName()

def getDeviceName():

	alpha = choice('efghijklmnopqrstuvwxyz')
	numeric = choice([x for x in range(1,10)])

	return 'sd' + str(alpha) + str(numeric)

def blockGetXML(xmlFile,imageName,deviceName):

	tree = ET.parse(xmlFile)
	root = tree.getroot()

	imageName = POOL_NAME + '/' + imageName

	root.find('source').attrib['name'] = imageName
	root.find('source').find('host').attrib['name'] = HOST_NAME
	root.find('target').attrib['dev'] = deviceName

	return ET.tostring(root)

@app.route("/volume/create",methods=['POST', 'GET'])
def volumeCreate():

	name = str(request.args.get('name',''))
	size = int(request.args.get('size',''))

	block = DBSession.blocks.find_one({'name':name})
	if block != None:
		return jsonify(volumeid=0)

	size = (1024**3) * size
	try:
		rbdInstance.create(ioctx,name,size)
		system('sudo rbd map %s --pool %s --name client.admin'%(name,POOL_NAME))
	except:
		return jsonify(volumeid=0)	

	tempBlock = {	'name':name,
					'size':size / (1024**3),
					'status': "available",
					'vmid':None,
					'device_name':getDeviceName()
				}

	volumeId = str(DBSession.blocks.insert(tempBlock))

	return jsonify(volumeid=volumeId)


@app.route("/volume/query",methods=['POST', 'GET'])
def volumeQuery():

	volumeId = str(request.args.get('volumeid',''))
	try:
		objectId = ObjectId(volumeId)
	except:
		return jsonify(error = "volumeid : %s does not exist"%(volumeId))

	block = DBSession.blocks.find_one({'_id':objectId})
	if block == None:
		return jsonify(error = "volumeid : %s does not exist"%(volumeId))

	if block['status'] == 'attached':
		return jsonify(volumeid = volumeId,
				name = block['name'],
				size = block['size'],
				status = block['status'],
				vmid = block['vmid']
				)

	elif block['status'] == 'available':
		return jsonify(volumeid = volumeId,
				name = block['name'],
				size = block['size'],
				status = block['status'],
				)
	else:
		return jsonify(error = "volumeid : %s does not exist"%(volumeId))



@app.route("/volume/destroy",methods=['POST', 'GET'])
def volumeDestroy():

	volumeId = str(request.args.get('volumeid',''))
	try:
		objectId = ObjectId(volumeId)
	except:
		return jsonify(status=0)

	block = DBSession.blocks.find_one({'_id':objectId})
	if block == None:
		return jsonify(status=0)

	if block['status'] == 'attached':
		return jsonify(status=0)

	imageName = str(block['name'])
	
	try:
		system('sudo rbd unmap /dev/rbd/%s/%s'%(POOL_NAME,imageName))
		rbdInstance.remove(ioctx,imageName)
	except:
		return jsonify(status=0)		

	DBSession.blocks.remove(block)

	return jsonify(status=1)


@app.route("/volume/attach",methods=['POST', 'GET'])
def volumeAttach():

	vmId = str(request.args.get('vmid',''))
	volumeId = str(request.args.get('volumeid',''))

	try:
		objectId = ObjectId(volumeId)
	except:
		return jsonify(status=0)

	block = DBSession.blocks.find_one({'_id':objectId})
	if block == None:
		return jsonify(status=0)

	if block['status'] == 'attached':
		return jsonify(status=0)

	instance = DBSession.instances.find_one({'vmid':vmId})
	if instance == None:
		return jsonify(status=0)

	imageName = block['name']
	pmid = instance['pmid']

	machine = DBSession.machines.find_one({'_id':pmid})
	connection = vmConnect(machine['location'])
	domain = connection.lookupByUUIDString(vmId)

	configXML = blockGetXML(BLOCK_CONFIG_XML,imageName,block['device_name'])
	try:
		domain.attachDevice(configXML)
	except:
		return jsonify(status=0)		

	vmDisconnect(connection)

	DBSession.blocks.update(	{'_id':objectId},
								{'$set':{'status': "attached",
										 'vmid':vmId,
										}})

	return jsonify(status=1)


@app.route("/volume/detach",methods=['POST', 'GET'])
def volumeDetach():

	volumeId = str(request.args.get('volumeid',''))

	try:
		objectId = ObjectId(volumeId)
	except:
		return jsonify(status=0)

	block = DBSession.blocks.find_one({'_id':objectId})
	if block == None:
		return jsonify(status=0)

	if block['status'] == 'available':
		return jsonify(status=0)

	imageName = block['name']
	vmId = block['vmid']
	instance = DBSession.instances.find_one({'vmid':vmId})
	pmid = instance['pmid']
	machine = DBSession.machines.find_one({'_id':pmid})

	connection = vmConnect(machine['location'])
	domain = connection.lookupByUUIDString(vmId)

	configXML = blockGetXML(BLOCK_CONFIG_XML,imageName,block['device_name'])
	try:
		domain.detachDevice(configXML)
	except:
		return jsonify(status=0)

	vmDisconnect(connection)

	DBSession.blocks.update(	{'_id':objectId},
								{'$set':{'status': "available",
										'vmid':None
										}})

	return jsonify(status=1)
	
if __name__ == "__main__":

	getHostName()

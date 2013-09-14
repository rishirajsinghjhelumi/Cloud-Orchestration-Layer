from views.virtualMachine import *
from mongokit import Connection

mongoConnection = Connection()
DBSession = mongoConnection['cloudDB']

def multikeysort(items, columns):
	from operator import itemgetter
	comparers = [ ((itemgetter(col[1:].strip()), -1) if col.startswith('-') else (itemgetter(col.strip()), 1)) for col in columns]  
	def comparer(left, right):
		for fn, mult in comparers:
			result = cmp(fn(left), fn(right))
			if result:
				return mult * result
			else:
				return 0
	return sorted(items, cmp=comparer)

def savePhysicalMachinesInfo():

	machines = DBSession.machines.find()
	for machine in machines:
		connection = vmConnect(machine['location'])

		sysInfo = connection.getInfo()
		sysArch = sysInfo[0]
		sysMem = sysInfo[1]
		sysCPU = sysInfo[2]

		machineInfo = {}
		machineInfo['_id'] = machine['_id']
		machineInfo['arch'] = sysArch
		machineInfo['memory'] = sysMem
		machineInfo['cpus'] = sysCPU
		machineInfo['emulator'] = vmGetEmulator(sysArch)

		#Assuming no previous VM's are running.
		#machineInfo['memory_used'] = 0
		#machineInfo['cpus_used'] = 0

		DBSession.machine_info.insert(machineInfo)

		vmDisconnect(connection)

if __name__ == '__main__':

	savePhysicalMachinesInfo()



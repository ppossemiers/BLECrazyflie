import time
import struct
from threading import Timer
import objc
from PyObjCTools import AppHelper

objc.loadBundle("CoreBluetooth", globals(),
bundle_path=objc.pathForFramework(u'/System/Library/Frameworks/IOBluetooth.framework/Versions/A/Frameworks/CoreBluetooth.framework'))

crazyflie_service = CBUUID.UUIDWithString_(u'00000201-1C7F-4F9E-947B-43B7C00A9A08')
crtp_characteristic = CBUUID.UUIDWithString_(u'00000202-1C7F-4F9E-947B-43B7C00A9A08')

def main():
   cf = BLECrazyFlie()
   # add methods that the crazyflie executes
   cf.add_callback(hover)
   manager = CBCentralManager.alloc()
   manager.initWithDelegate_queue_options_(cf, None, None)
   
   AppHelper.runConsoleEventLoop(None, True, 'NSDefaultRunLoopMode')

def hover(cf):
	thrust = 10000
	increment = 1000
	# send thrust
	for i in range(10):
		cf.send_setpoint(0, 0, 0, thrust)
		thrust += increment
   		time.sleep(0.5)

   # stop thrust, start hover
   #cf.set_param('flightmode.althold', 'True')
   #cf.commander.send_setpoint(0, 0, 0, 32767)
   #while 1:
   #   cf.commander.send_setpoint(0,0,0,32767)
   #   time.sleep(0.5)

class BLECrazyFlie():
	def __init__(self):
		self.manager = None
		self.peripheral = None
		self.service = None
		self.crtp_characteristic = None
		self.connected = False
		self.callbacks = []

		self.init = False
   
	def send_setpoint(self, roll, pitch, yaw, thrust):
		data = struct.pack('<BfffH', 0x30, roll, -pitch, yaw, thrust)
		bytes = NSData.dataWithBytes_length_(data, len(data))
		self.peripheral.writeValue_forCharacteristic_type_(bytes, self.crtp_characteristic, 1)

	def add_callback(self, cb):
		if ((cb in self.callbacks) is False):
			self.callbacks.append(cb)

	def remove_callback(self, cb):
		self.callbacks.remove(cb)

	def call(self, *args):
		for cb in self.callbacks:
			cb(*args)
 
	def centralManagerDidUpdateState_(self, manager):
		if self.connected == False:
 			self.manager = manager
 			manager.scanForPeripheralsWithServices_options_(None, None)

	def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(self, manager, peripheral, data, rssi):
		print 'Found ' + peripheral.name()
		if peripheral.name() == 'Crazyflie':
			manager.stopScan()
 			self.peripheral = peripheral
 			manager.connectPeripheral_options_(self.peripheral, None)

	def centralManager_didConnectPeripheral_(self, manager, peripheral):
		print 'Connected to ' + peripheral.name()
  		self.connected = True
  		self.peripheral.setDelegate_(self)
  		self.peripheral.readRSSI()
  		self.peripheral.discoverServices_([crazyflie_service])

	def centralManager_didFailToConnectPeripheral_error_(self, manager, peripheral, error):
		print repr(error)

	def centralManager_didDisconnectPeripheral_error_(self, manager, peripheral, error):
		self.connected = False
		AppHelper.stopEventLoop()

	def peripheral_didDiscoverServices_(self, peripheral, error):
		if(error == None):
			self.service = self.peripheral.services()[0]
			self.peripheral.discoverCharacteristics_forService_([crtp_characteristic], self.service)
   
	def peripheral_didDiscoverCharacteristicsForService_error_(self, peripheral, service, error):
		for characteristic in self.service.characteristics():
			if characteristic.UUID().UUIDString() == crtp_characteristic.UUIDString():
				self.crtp_characteristic = characteristic
				self.peripheral.setNotifyValue_forCharacteristic_(True, self.crtp_characteristic)

	def peripheral_didWriteValueForCharacteristic_error_(self, peripheral, characteristic, error):
		if error != None:
			print repr(error)
  		else:
 			print 'Sent'

	def peripheral_didUpdateNotificationStateForCharacteristic_error_(self, peripheral, characteristic, error):
		print 'Receiving notifications'
		# unlock thrust
   		self.send_setpoint(0, 0, 0, 0)
		self.call(self)

	def peripheral_didUpdateValueForCharacteristic_error_(self, peripheral, characteristic, error):
		print repr(characteristic.value().bytes().tobytes())

	def peripheralDidUpdateRSSI_error_(self, peripheral, error):
		print peripheral.RSSI()

if __name__ == "__main__":
   main()


import select
import time
import struct
from threading import Timer
from binascii import *
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
	cf.call(cf)
	#manager = CBCentralManager.alloc()
	#manager.initWithDelegate_queue_options_(cf, None, None)
	
	AppHelper.runConsoleEventLoop(None, True, 'NSDefaultRunLoopMode')

def hover(cf):
	# sending thrust 45000
	cf.commander.send_setpoint(0, 0, 0, 45000)
	time.sleep(0.75)

	# stopping thrust, now hovering
	#cf.param.set_value("flightmode.althold", "True")
	#cf.commander.send_setpoint(0, 0, 0, 32767)
	#while 1:
	#	cf.commander.send_setpoint(0,0,0,32767)
	#	time.sleep(0.5)
	
class BLECrazyFlie():
    def __init__(self):
        self.manager = None
        self.peripheral = None
        self.service = None
        self.crtp_characteristic = None
        self.connected = False
        self.commander = BLECommander(self)
        self.callbacks = []
    
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
		if peripheral.name() == "Crazyflie":
			manager.stopScan()
			self.peripheral = peripheral
			manager.connectPeripheral_options_(peripheral, None)

    def centralManager_didConnectPeripheral_(self, manager, peripheral):
		print "Connected to " + peripheral.name()
		self.connected = True
		self.peripheral.setDelegate_(self)
		self.peripheral.discoverServices_([crazyflie_service])

    def centralManager_didFailToConnectPeripheral_error_(self, manager, peripheral, error):
        print repr(error)

    def centralManager_didDisconnectPeripheral_error_(self, manager, peripheral, error):
		self.connected = False
		print repr(error)
		AppHelper.stopEventLoop()

    def peripheral_didDiscoverServices_(self, peripheral, services):
		self.service = self.peripheral.services()[0]
		self.peripheral.discoverCharacteristics_forService_([crtp_characteristic], self.service)
        
    def peripheral_didDiscoverCharacteristicsForService_error_(self, peripheral, service, error):
		for characteristic in self.service.characteristics():
			if characteristic.UUID().UUIDString() == crtp_characteristic.UUIDString():
				self.crtp_characteristic = characteristic
				self.peripheral.setNotifyValue_forCharacteristic_(True, self.crtp_characteristic)

    def peripheral_didWriteValueForCharacteristic_error_(self, peripheral, characteristic, error):
        print repr(error)

    def peripheral_didUpdateNotificationStateForCharacteristic_error_(self, peripheral, characteristic, error):
        print "Receiving notifications"
        self.call(self)

    def peripheral_didUpdateValueForCharacteristic_error_(self, peripheral, characteristic, error):
        print repr(characteristic.value().bytes().tobytes())

    def send_packet(self, pk, expected_reply=(), resend=False, timeout=0.2):
		#test_pk = 'aaaa300e00000000000000000000000000003e'
		test_pk = 'aaaa300e00000000000000000000000000003e'
		
		sum = 0
		for ch in test_pk:
			sum += ord(ch)
			
		mod = sum % 256
		checksum = hex(mod)
		print checksum
				
		bytes = bytearray.fromhex(test_pk)
		self.peripheral.writeValue_forCharacteristic_type_(bytes, self.crtp_characteristic, 0)

    def shutdown(self):
        if self.peripheral is not None:
            self.manager.cancelPeripheralConnection_(self.peripheral)
            self.connected = False
        else:
            AppHelper.stopEventLoop()

class BLECommander():
	def __init__(self, crazyflie=None):
		self._cf = crazyflie

	def send_setpoint(self, roll, pitch, yaw, thrust):
		pk = BLEPacket()
		pk.port = 0x03
		pk.data = struct.pack('<fffH', roll, -pitch, yaw, thrust)
		self._cf.send_packet(pk)
        
class BLEPacket():
	def __init__(self, header=0, data=None):
		self.size = 0
		self._data = ""
		self.header = header | 0x3 << 2
		self._port = (header & 0xF0) >> 4
		self._channel = header & 0x03
		if data:
			self._set_data(data)

	def _get_channel(self):
		return self._channel

	def _set_channel(self, channel):
		self._channel = channel
		self._update_header()

	def _get_port(self):
		return self._port

	def _set_port(self, port):
		self._port = port
		self._update_header()

	def get_header(self):
		self._update_header()
		return self.header

	def set_header(self, port, channel):
		self._port = port
		self.channel = channel
		self._update_header()

	def _update_header(self):
		# The two bits in position 3 and 4 needs to be set for legacy
		# support of the bootloader
		self.header = ((self._port & 0x0f) << 4 | 3 << 2 | (self.channel & 0x03))

    #Some python madness to access different format of the data
	def _get_data(self):
		return self._data

	def _set_data(self, data):
		if type(data) == str:
			self._data = data
		elif type(data) == list or type(data) == tuple:
			if len(data) == 1:
				self._data = struct.pack("B", data[0])
			elif len(data) > 1:
				self._data = struct.pack("B" * len(data), *data)
			else:
				self._data = ""
		else:
			raise Exception("Data shall be of str, tuple or list type")

	def _get_data_l(self):
		return list(self._get_data_t())

	def _get_data_t(self):
		return struct.unpack("B" * len(self._data), self._data)

	def __str__(self):
		return "{}:{} {}".format(self._port, self.channel, self.datat)

	data = property(_get_data, _set_data)
	datal = property(_get_data_l, _set_data)
	datat = property(_get_data_t, _set_data)
	datas = property(_get_data, _set_data)
	port = property(_get_port, _set_port)
	channel = property(_get_channel, _set_channel)	
		
if __name__ == "__main__":
	main()


import d2xx
import struct


DEFAULT_FREQUENCY = 3000000


class DeviceNotOpened(Exception): pass


# Information about which of the 8 GPIO pins to use.
class FT232R_PortList:
	def __init__(self, tck, tms, tdi, tdo):
		self.tck = tck
		self.tms = tms
		self.tdi = tdi
		self.tdo = tdo
	
	def output_mask(self):
		return (1 << self.tck) | (1 << self.tms) | (1 << self.tdi)

	def format(self, tck, tms, tdi):
		return struct.pack('=c', chr(((tck&1) << self.tck) | ((tms&1) << self.tms) | ((tdi&1) << self.tdi)))


class FT232R:
	def __init__(self):
		self.handle = None
		self.debug = 0
		self.synchronous = None
		self.write_buffer = ""
		self.portlist = None
	
	def _log(self, msg, level=1):
		if level <= self.debug:
			print "FT232R-JTAG: " + msg
	
	def open(self, devicenum, portlist):
		if self.handle is not None:
			self.close()

		self._log("Opening device %i" % devicenum)

		self.handle = d2xx.open(devicenum)

		if self.handle is not None:
			self.portlist = portlist
			self._setBaudRate(DEFAULT_FREQUENCY)
			self._setSyncMode()
			self._purgeBuffers()
	
	def close(self):
		if self.handle is None:
			return

		self._log("Closing device...")

		try:
			self.handle.close()
		finally:
			self.handle = None

		self._log("Device closed.")
	
	# Purges the FT232R's buffers.
	def _purgeBuffers(self):
		if self.handle is None:
			raise DeviceNotOpened()

		self.handle.purge(1)
	
	def _setBaudRate(self, rate):
		self._log("Setting baudrate to %i" % rate)

		# Documentation says that we should set a baudrate 16 times lower than
		# the desired transfer speed (for bit-banging). However I found this to
		# not be the case. 3Mbaud is the maximum speed of the FT232RL
		self.handle.setBaudRate(rate)
		#self.handle.setDivisor(0)	# Another way to set the maximum speed.
	
	# Put the FT232R into Synchronous mode.
	def _setSyncMode(self):
		if self.handle is None:
			raise DeviceNotOpened()

		self._log("Device entering Synchronous mode.")

		self.handle.setBitMode(self.portlist.output_mask(), 0)
		self.handle.setBitMode(self.portlist.output_mask(), 4)
		self.synchronous = True

	
	# Put the FT232R into Asynchronous mode.
	def _setAsyncMode(self):
		if self.handle is None:
			raise DeviceNotOpened()

		self._log("Device entering Asynchronous mode.")

		self.handle.setBitMode(self.portlist.output_mask(), 0)
		self.handle.setBitMode(self.portlist.output_mask(), 1)
		self.synchronous = False
	
	def _formatJtagState(self, tck, tms, tdi):
		return self.portlist.format(tck, tms, tdi)

	def jtagClock(self, tms=0, tdi=0):
		if self.handle is None:
			raise DeviceNotOpened()
		
		self.write_buffer += self._formatJtagState(0, tms, tdi)
		self.write_buffer += self._formatJtagState(1, tms, tdi)
		self.write_buffer += self._formatJtagState(1, tms, tdi)
	
	def flush(self):
		self._setAsyncMode()
		while len(self.write_buffer) > 0:
			self.handle.write(self.write_buffer[:4096])
			self.write_buffer = self.write_buffer[4096:]
		self._setSyncMode()
		self._purgeBuffers()
	
	# Read the last num bits of TDO.
	def readTDO(self, num):
		if num == 0:
			flush()
			return []

		# Repeat the last byte so we can read the last bit of TDO.
		write_buffer = self.write_buffer[-(num*3):]
		self.write_buffer = self.write_buffer[:-(num*3)]

		# Write all data that we don't care about.
		if len(self.write_buffer) > 0:
			self.flush()
			self._purgeBuffers()

		bits = []

		while len(write_buffer) > 0:
			written = min(len(write_buffer), 3072)

			self.handle.write(write_buffer[:written])
			write_buffer = write_buffer[written:]
			read = self.handle.read(written)

			for n in range(written/3):
				bits.append((ord(read[n*3+2]) >> self.portlist.tdo)&1)

		return bits


	
	



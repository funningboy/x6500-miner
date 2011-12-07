# Copyright (C) 2011 by fpgaminer <fpgaminer@bitcoin-mining.com>
#                       fizzisist <fizzisist@fpgamining.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Parse a .BIT file generated by Xilinx's bitgen.
# That is the default file generated during ISE's compilation.
#
# FILE FORMAT:
#
# Consists of an initial 11 bytes of unknown content (???)
# Then 5 fields of the format:
#	1 byte key
#	2 byte, Big Endian Length (EXCEPT: The last field, which has a 4 byte length)
#	data (of length specified above ^)
# 
# The 5 fields have keys in the sequence a, b, c, d, e
# The data from the first 4 fields are strings:
# design name, part name, date, time
# The last field is the raw bitstream.
#

import os.path
import cPickle as pickle

# Dictionary for looking up idcodes from device names:
idcode_lut = {'6slx150fgg484': 0x401d093, '6slx45csg324': 0x4008093}

class BitFileReadError(Exception):
	_corruptFileMessage = "Unable to parse .bit file; header is malformed. Is it really a Xilinx .bit file?"

	def __init__(self, value=None):
		self.parameter = BitFileReadError._corruptFileMessage if value is None else value
	def __str__(self):
		return repr(self.parameter)
		
class BitFileMismatch(Exception):
	_mismatchMessage = "Device IDCode does not match bitfile IDCode! Was this bitstream built for this FPGA?"

	def __init__(self, value=None):
		self.parameter = BitFileReadError._mismatchMessage if value is None else value
	def __str__(self):
		return repr(self.parameter)
	
class Object(object):
	pass

class BitFile:
	"""Read a .bit file and return a BitFile object."""
	@staticmethod
	def read(name):
		with open(name, 'rb') as f:
			bitfile = BitFile()
			
			# 11 bytes of unknown data
			if BitFile._readLength(f) != 9:
				raise BitFileReadError()
			
			BitFile._readOrDie(f, 11)
			
			bitfile.designname = BitFile._readField(f, 'a').rstrip('\0')
			bitfile.part = BitFile._readField(f, 'b').rstrip('\0')
			bitfile.date = BitFile._readField(f, 'c').rstrip('\0')
			bitfile.time = BitFile._readField(f, 'd').rstrip('\0')
			bitfile.idcode = idcode_lut[bitfile.part]
			
			if BitFile._readOrDie(f, 1) != 'e':
				raise BitFileReadError()
			
			length = BitFile._readLength4(f)
			bitfile.bitstream = BitFile._readOrDie(f, length)
			
			processed_name = name.split('.')[0] + '.processed'
			if os.path.isfile(processed_name):
				bitfile.processed = True
			else:
				bitfile.processed = False
			return bitfile
	
	@staticmethod
	def pre_process(bitstream, jtag, chain_list):
		CHUNK_SIZE = 4096*4
		chunk = ["", ""]
		chunks = [[], []]

		for b in bitstream[:-1]:
			d = ord(b)
			
			for i in range(7, -1, -1):
				x = (d >> i) & 1
				for chain in chain_list:
					chunk[chain] += jtag[chain]._formatJtagClock(tdi=x)
					
					if len(chunk[chain]) >= CHUNK_SIZE:
						chunks[chain].append(chunk[chain])
						chunk[chain] = ""
		
		for chain in chain_list:
			if len(chunk[chain]) > 0:
				chunks[chain].append(chunk[chain])

		last_bits = []
		d = ord(bitstream[-1])
		for i in range(7, -1, -1):
			last_bits.append((d >> i) & 1)

		#for i in range(self.current_part):
		#	last_bits.append(0)
		
		processed_bitstreams = []
		for chain in chain_list:
			processed_bitstream = Object()
			processed_bitstream.chunks = chunks[chain]
			processed_bitstream.last_bits = last_bits
			processed_bitstreams.append(processed_bitstream)
		
		return processed_bitstreams
	
	@staticmethod
	def save_processed(processed_bitstreams, name):
		processed_name = name.split('.')[0] + ".processed"
		pickle.dump(processed_bitstreams, open(processed_name, "wb"), pickle.HIGHEST_PROTOCOL)
	
	@staticmethod
	def load_processed(name):
		processed_name = name.split('.')[0] + ".processed"
		return pickle.load(open(processed_name, "rb"))
	
	# Read a 2-byte, unsigned, Big Endian length.
	@staticmethod
	def _readLength(filestream):
		length = BitFile._readOrDie(filestream, 2)

		return (ord(length[0]) << 8) | ord(length[1])

	@staticmethod
	def _readLength4(filestream):
		length = BitFile._readOrDie(filestream, 4)

		return (ord(length[0]) << 24) | (ord(length[1]) << 16) | (ord(length[2]) << 8) | ord(length[3])

	# Read length bytes, or throw an exception
	@staticmethod
	def _readOrDie(filestream, length):
		data = filestream.read(length)

		if len(data) < length:
			raise BitFileReadError()

		return data

	@staticmethod
	def _readField(filestream, key):
		if BitFile._readOrDie(filestream, 1) != key:
			raise BitFileReadError()

		length = BitFile._readLength(filestream)
		data = BitFile._readOrDie(filestream, length)

		return data
		

	def __init__(self):
		self.designname = None
		self.part = None
		self.date = None
		self.time = None
		self.length = None
		self.idcode = None
		self.bitstream = None


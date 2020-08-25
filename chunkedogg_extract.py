# Chunked OGG Extractor v0.1
# Copyright (C) 2020 shockdude

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import os
import time
import struct

OGG_EXT = ".ogg"
OGG_MAGIC = b"OggS"
DATA_MAGIC = b"data"

def usage():
	print("Chunked OGG extractor v0.1")
	print('Get a playable OGG out of a "chunked vorbis" WAV')
	print("Usage: {} file.wav [out.ogg]".format(sys.argv[0]))
	time.sleep(3)
	sys.exit(1)

def find_ogg(in_filename, out_filename):
	print("Writing ogg {} from {}".format(out_filename, in_filename))
	with open(in_filename, "rb") as in_file:
		with open(out_filename, "wb") as out_file:
			buf = in_file.read(4)
			while len(buf) == 4:
				if buf != OGG_MAGIC:
					# look for the OggS magic keyword
					buf = buf[1:] + in_file.read(1)
				else: # found OggS
					page_data = buf
					page_data += in_file.read(2) # stream structure, header type flag
					page_data += in_file.read(8) # absolute granule position
					stream_serial_number = in_file.read(4)
					page_data += stream_serial_number
					page_data += in_file.read(8) # page sequence number, page checksum
					
					# count number of segments in oggs page
					num_segments_byte = in_file.read(1)
					page_data += num_segments_byte
					num_segments = int.from_bytes(num_segments_byte, "little")
					
					# count lengths of segments in oggs page
					total_segments_length = 0
					for i in range(num_segments):
						segment_length_byte = in_file.read(1)
						page_data += segment_length_byte
						total_segments_length += int.from_bytes(segment_length_byte, "little")
				
					page_data += in_file.read(total_segments_length)
					# skip page if the serial number is all Fs
					if stream_serial_number != b"\xff\xff\xff\xff":
						out_file.write(page_data)
					
					# move through the loop again
					buf = in_file.read(4)

def main():
	if len(sys.argv) < 2:
		usage()
	else:
		in_filename = sys.argv[1]
		in_file, in_ext = os.path.splitext(in_filename)
		if len(sys.argv) > 2:
			out_filename = sys.argv[2]
		else:
			out_filename = os.path.splitext(os.path.basename(in_file))[0] + OGG_EXT
		find_ogg(in_filename, out_filename)
		
if __name__ == "__main__":
	main()
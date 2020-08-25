# BMS to RPP v0.84
# Copyright (C) 2020 shockdude
# REAPER is property of Cockos Incorporated

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
import re
import math
from pydub import AudioSegment

def usage():
	print("BMS to RPP v0.84")
	print("Convert a BMS or DTX chart into a playable REAPER project")
	print("WAV keysounds recommended, OGG keysounds require ffmpeg/avconv and are slow to parse.")
	print("Usage: {} chart_file.bms [output_filename.rpp]".format(sys.argv[0]))
	time.sleep(3)
	sys.exit(1)

WAV_EXT = ".wav"
OGG_EXT = ".ogg"
RPP_EXT = ".rpp"

BMS_EXT = ".bms"
BME_EXT = ".bme"
DTX_EXT = ".dtx"

# measures per second = 240.0 / BPM
MPS_FACTOR = 240.0

# channel info
BMS_PLAYABLE_CHANNELS = ("01", "11", "12", "13", "14", "15", "16", "18", "19", "21", "22", "23", "24", "25", "26", "28", "29")
DTX_DRUM_CHANNELS = ("11", "12", "13", "14", "15", "16", "17", "18", "19", "1A")
DTX_GUITAR_CHANNELS = ("20", "21", "22", "23", "24", "25", "26", "27")
DTX_BASS_CHANNELS = ("A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7")
DTX_BG_CHANNELS = ("01", "61", "62", "63", "64", "65", "66", "67", "68", "69",
					"70", "71", "72", "73", "74", "75", "76", "77", "78", "79",
					"80", "81", "82", "83", "84", "85", "86", "87", "88", "89",
					"90", "91", "92")
DTX_PLAYABLE_CHANNELS = DTX_BG_CHANNELS + DTX_DRUM_CHANNELS + DTX_GUITAR_CHANNELS + DTX_BASS_CHANNELS
MEASURE_LEN_CHANNEL = "02"
BPM_CHANNEL = "03"
EXTBPM_CHANNEL = "08"
STOP_CHANNEL = "09"

# pseudoenum for DTX vs BMS parsing mode
MODE_BMS = 0
MODE_DTX = 1
parsing_mode = None

# dictionary of keysound index to wav
# e.g. #WAV1Z bass.wav --> "1Z" : "bass.wav"
keysound_dict = {}

# dictionary of keysound index to pan (dtx only)
keysoundpan_dict = {}

# dictionary of keysound index to volume (dtx only)
keysoundvol_dict = {}

# dictionary of extended bpm index to bpm values
# e.g. #BPM2Y 120.0 --> "2Y" : 120.0
extbpm_dict = {}

# dictionary of stop index to stop duration x/192
# e.g. #STOP03 192 --> "03" : 192
stop_dict = {}

# dictionary of stop position to stop length
# e.g. beat 3 : 0.5
stop_lengths = {}

# dict of beat position to bpms
# e.g. beat 2 : 120BPM
bpm_dict = {}
# dict of bpm position to time position
# e.g. beat 2 : 2.3 seconds
bpmtime_dict = {}
# sorted positions in terms of beats
bpm_positions = []

# dict of beat position to measure lengths
# e.g. beat 3 : length 1.75
measurelen_dict = {}
# dict of measure length position to time position
# e.g. beat 3 : 3.1 seconds
measurelentime_dict = {}

# dict of all bms notes
# e.g. "00601" : ["01","00","23","AZ"]
notes_dict = {}

# dictionary mapping keysound index to keysound sample positions & lengths
sample_dict = {}

# dictionary mapping channel to keysound sample positions & lengths
channelsample_dict = {}

# keep track of the largest measure in the BMS
max_measure = 0

# find a bms header tag
def find_tag(line, tag):
	if line.find(tag) == 0:
		return line[len(tag):]
	return None

# parse header value
def get_header_value(line, header):
	header_re = re.compile("#{}([\\w\\d][\\w\\d])(:\\s*|\\s+)(.+)\\s*".format(header))
	re_match = header_re.match(line)
	if re_match != None and re_match.start() == 0:
		index = re_match.group(1)
		value = re_match.group(3)
		return index, value
	return None, None

# create dictionary of keysounds
def add_keysound(line):
	index, value = get_header_value(line, "WAV")
	if index != None and value != None:
		keysound_basename = os.path.splitext(value)[0]
		keysound_filename = keysound_basename + WAV_EXT
		if os.path.isfile(keysound_filename):
			keysound_dict[index] = keysound_filename
			return True
		keysound_filename = keysound_basename + OGG_EXT
		if os.path.isfile(keysound_filename):
			keysound_dict[index] = keysound_filename
			return True
		print("Error: could not find .wav or .ogg for {}".format(keysound_origname))
		usage()
	return False

# create dictionary of keysound volume percentages
def add_keysoundvolume(line):
	index, value = get_header_value(line, "VOLUME")
	if index != None and value != None:
		keysoundvol_dict[index] = float(value) / 100.0
		return True
	return False

# create dictionary of keysound pan percentages
def add_keysoundpan(line):
	index, value = get_header_value(line, "PAN")
	if index != None and value != None:
		keysoundpan_dict[index] = float(value) / 100.0
		return True
	return False

# create dictionary of extended bpm values
def add_bpmvalue(line):
	index, value = get_header_value(line, "BPM")
	if index != None and value != None:
		extbpm_dict[index] = float(value)
		return True
	return False
		
# create dictionary of stop values
def add_stopvalue(line):
	index, value = get_header_value(line, "STOP")
	if index != None and value != None:
		stop_dict[index] = float(value)
		return True
	return False

# convert channel data to an array
def data_to_array(data):
	out = []
	for i in range(0, len(data), 2):
		out.append(data[i:i+2])
	return out

# least common multiple
def lcm(a,b):
	return int(a*b/math.gcd(a,b))

# merge the data of multiple instances of the same channel
def update_data(old_data, new_data):
	old_data_len = len(old_data)
	new_data_len = len(new_data)
	data_lcm = lcm(old_data_len, new_data_len)
	old_data_factor = data_lcm/old_data_len
	new_data_factor = data_lcm/new_data_len
	merged_data = [0]*data_lcm
	for i in range(data_lcm):
		if i % old_data_factor == 0:
			old_data_value = old_data[int(i/old_data_factor)]
		else:
			old_data_value = "00"
		if i % new_data_factor == 0:
			new_data_value = new_data[int(i/new_data_factor)]
		else:
			new_data_value = "00"
			
		# give priority to the newer data unless newer data is 00
		if new_data_value == "00":
			merged_data[i] = old_data_value
		else:
			merged_data[i] = new_data_value
	return merged_data

# identify channels & save their data
def add_channel(line):
	global max_measure
	# use regular expression to match the channel format
	note_re = re.compile("#(\\d\\d\\d[\\d\\w][\\d\\w])(:\\s*|\\s+)(\\S+)")
	re_match = note_re.match(line)
	if re_match != None and re_match.start() == 0:
		header = re_match.group(1)
		measure = int(header[0:3])
		channel = header[3:5]
		data = re_match.group(3)
		
		# set the largest measure found
		if measure > max_measure:
			max_measure = measure
		
		if parsing_mode == MODE_BMS:
			playable_channels = BMS_PLAYABLE_CHANNELS
		elif parsing_mode == MODE_DTX:
			playable_channels = DTX_PLAYABLE_CHANNELS

		# check for channel with data array
		if channel in (playable_channels + (BPM_CHANNEL, EXTBPM_CHANNEL, STOP_CHANNEL)) and data != "00":
			data_array = data_to_array(data)
			if channel == "01":
				# bgm tracks are special and shouldn't be merged
				# dictionary maps to array of arrays instead
				if header not in notes_dict:
					notes_dict[header] = []
				notes_dict[header].append(data_array)
			else:
				# merge duplicate notes
				if header in notes_dict:
					old_data = notes_dict[header]
					notes_dict[header] = update_data(old_data, data_array)
				else:
					notes_dict[header] = data_array
		# measure length channel
		elif channel == MEASURE_LEN_CHANNEL:
			measurelen_dict[measure] = float(data)

# for 1 measure, convert a beat position into a time offset within the measure
# accounting for bpms & stops
def measure_offset_seconds(start_measure, beatpos, bpmpos_array, stop_positions, measure_len):
	bpmpos = bpmpos_array[0]
	bpm = bpm_dict[bpmpos]
	if bpmpos < start_measure:
		bpmpos = start_measure
	
	# add time between bpm markers
	current_time = 0
	for i in range(1, len(bpmpos_array)):
		next_bpmpos = bpmpos_array[i]
		if beatpos > next_bpmpos:
			current_time += (next_bpmpos - bpmpos) * MPS_FACTOR * measure_len / bpm
		else:
			break
		bpmpos = next_bpmpos
		bpm = bpm_dict[bpmpos]
		
	# add stops - extra time in the measure
	# there's probably a more elegant way to add stops but w/e
	stop_bpmpos_i = 0
	for s in range(len(stop_positions)):
		current_stop_pos = stop_positions[s]
		if beatpos > current_stop_pos:
			stop_bpmpos = bpmpos_array[stop_bpmpos_i]
			stop_bpm = bpm_dict[stop_bpmpos]
			for i in range(stop_bpmpos_i + 1, len(bpmpos_array)):			
				next_bpmpos = bpmpos_array[i]
				if current_stop_pos < next_bpmpos:
					stop_bpmpos_i = i - 1
					break
				stop_bpmpos = next_bpmpos
				stop_bpm = bpm_dict[stop_bpmpos]
			current_time += stop_lengths[current_stop_pos] * MPS_FACTOR / stop_bpm
		else:
			break

	# add remaining time based on last bpm marker
	current_time += (beatpos - bpmpos) * MPS_FACTOR * measure_len / bpm
	
	return current_time

# given a channel, get keysound samples & set their time position & length
def add_keysounds_to_sample_dict(channel, keysounds, keysound_lengths, current_timepos, current_bpmpos_i, stop_positions, measure_num, measure_len):
	global sample_dict, channelsample_dict
	keysounds_len = len(keysounds)
	for k in range(len(keysounds)):
		keysound = keysounds[k]
		if keysound in keysound_lengths:
			if keysound not in sample_dict:
				sample_dict[keysound] = []
			if channel not in channelsample_dict:
				channelsample_dict[channel] = []
			sample = {}
			sample["length"] = keysound_lengths[keysound]
			sample["pos"] = current_timepos + measure_offset_seconds(measure_num, measure_num + k/keysounds_len, bpm_positions[current_bpmpos_i:], stop_positions, measure_len)
			# unused but good for debugging
			# sample["index"] = keysound
			# sample["channel"] = channel
			# TODO per-sample volume
			#sample["volume"] = 1.0
			sample_dict[keysound].append(sample)
			channelsample_dict[channel].append(sample)

# for sorting the sample array by the sample position
def sample_pos_sort_key(s):
	return s["pos"]

# primary keysound parsing & rpp generating function
def parse_keysounds(chart_file, out_file):
	global keysound_dict, extbpm_dict, bpm_dict, bpm_positions, stop_lengths, note_dict, max_measure, sample_dict, channelsample_dict
	
	# master volume of the chart, default to 100.0
	master_volume = 100.0
	
	# default 120 chart bpm
	chart_bpm = 120.0
	
	# read bms chart
	# assuming shift-jis encoding
	print("Reading {}...".format(chart_file))
	with open(chart_file, "r", encoding="shift_jis") as chart:
		for line in chart:
			if line.find("#") == 0:
				line_strip = line.strip()
				
				# locate chart bpm
				data = find_tag(line_strip, "#BPM ")
				if data != None:
					# beats (measures) start at 1, not 0
					chart_bpm = float(data)
					bpm_dict[0.0] = float(data)
					bpm_positions = [0.0]
					bpmtime_dict[0.0] = 0
					continue
				
				# locate & set master volume
				data = find_tag(line_strip, "#VOLWAV ")
				if data != None:
					master_volume = float(data)
					continue
				
				# locate other bms data
				if add_keysound(line):
					continue
				if add_bpmvalue(line):
					continue
				if parsing_mode == MODE_DTX:
					if add_keysoundvolume(line):
						continue
					if add_keysoundpan(line):
						continue
				elif parsing_mode == MODE_BMS:
					if add_stopvalue(line):
						continue
				add_channel(line)

	# increase maximum measure by 1, in case there are notes in the last measure
	max_measure += 1

	# compute lengths of each keysound
	print("Getting keysound lengths...")
	print("This will take a while if the keysounds are not WAV")
	keysound_lengths = {}
	for keysound in keysound_dict:
		keysound_file = keysound_dict[keysound]
		try:
			sound = AudioSegment.from_file(keysound_file)
		except FileNotFoundError:
			print("ERROR: Could not load keysound file {}. If not WAV, missing ffmpeg/avconv?".format(keysound_file))
			usage()
		keysound_lengths[keysound] = sound.frame_count() / sound.frame_rate
		
	# current time position in seconds, starting at 0
	current_timepos = 0
	# current bpm position index, starting at 0
	current_bpmpos_i = 0
	# read keysounds, measure by measure
	print("Processing keysounds...")
	for measure_num in range(max_measure):
		# get length of this measure
		if measure_num in measurelen_dict:
			measure_len = measurelen_dict[measure_num]
			# set initial measurelen time, if any
			if measure_num == 0:
				measurelentime_dict[0] = 0
		else:
			measure_len = 1
		
		# number of bpms in measure, including bpm from before the measure
		bpms_in_measure = 1
		
		# number of new bpms added
		num_bpms_added = 0
		
		# locate stops in the measure, get their positions & compute their lengths
		stop_header = "{:03d}{}".format(measure_num, STOP_CHANNEL)
		stop_positions = []
		if stop_header in notes_dict:
			stop_indices = notes_dict[stop_header]
			stop_arraylen = len(stop_indices)
			for s in range(stop_arraylen):
				if stop_indices[s] != "00":
					# found stop
					stop_position = measure_num + s / stop_arraylen
					stop_positions.append(stop_position)
					stop_length = stop_dict[stop_indices[s]] / 192.0
					stop_lengths[stop_position] = stop_length
		
		# locate bpms in the measure, get their positions
		bpm_header = "{:03d}{}".format(measure_num, BPM_CHANNEL)
		if bpm_header in notes_dict:
			bpm_hex = notes_dict[bpm_header]
			bpm_arraylen = len(bpm_hex)
			for b in range(bpm_arraylen):
				if bpm_hex[b] != "00":
					# found bpm, add to bpm_dict
					bpm_pos = measure_num + b/bpm_arraylen
					num_bpms_added += 1
					if b != 0: # added another bpm to measure
						bpms_in_measure += 1
					else: # b == 0, replaces the previous bpm for the measure. update current_bpmpos_i
						current_bpmpos_i += 1
					bpm_positions.append(bpm_pos)
					bpm_dict[bpm_pos] = int("0x" + bpm_hex[b],16)
		
		# locate extended bpms in the measure, get their values & positions
		extbpm_header = "{:03d}{}".format(measure_num, EXTBPM_CHANNEL)
		if extbpm_header in notes_dict:
			extbpm_indices = notes_dict[extbpm_header]
			extbpm_arraylen = len(extbpm_indices)
			for b in range(extbpm_arraylen):
				if extbpm_indices[b] in extbpm_dict:
					# found bpm, add to bpm_dict
					bpm_pos = measure_num + b/extbpm_arraylen
					if bpm_pos in bpm_dict:
						print("Warning: overwrote BPM at position {}".format(bpm_pos))
					else:
						num_bpms_added += 1
						if b != 0: # added another bpm to measure
							bpms_in_measure += 1
						else: # b == 0, replaces the previous bpm for the measure. update current_bpmpos_i
							current_bpmpos_i += 1
						bpm_positions.append(bpm_pos)
					# handle negative bpm?
					bpm_dict[bpm_pos] = abs(extbpm_dict[extbpm_indices[b]])
		
		# sort bpm positions
		bpm_positions.sort()
		
		# compute time offsets for new bpm markers in measure
		for bpmpos_i in range(len(bpm_positions) - num_bpms_added, len(bpm_positions)):
			bpm_pos = bpm_positions[bpmpos_i]
			bpmtime_dict[bpm_pos] = current_timepos + measure_offset_seconds(measure_num, bpm_pos, bpm_positions[current_bpmpos_i:], stop_positions, measure_len)
		
		# get each channel's keysounds
		if parsing_mode == MODE_BMS:
			playable_channels = BMS_PLAYABLE_CHANNELS
		elif parsing_mode == MODE_DTX:
			playable_channels = DTX_PLAYABLE_CHANNELS
		
		for channel in playable_channels:
			header = "{:03d}{}".format(measure_num, channel)
			if header in notes_dict:
				if channel == "01":
					# multiple bgm keysound arrays
					for keysounds in notes_dict[header]:
						add_keysounds_to_sample_dict(channel, keysounds, keysound_lengths, current_timepos, current_bpmpos_i, stop_positions, measure_num, measure_len)
				else:
					keysounds = notes_dict[header]
					add_keysounds_to_sample_dict(channel, keysounds, keysound_lengths, current_timepos, current_bpmpos_i, stop_positions, measure_num, measure_len)
		
		# move current time to next measure
		current_timepos += measure_offset_seconds(measure_num, measure_num + 1, bpm_positions[current_bpmpos_i:], stop_positions, measure_len)

		# if there's a next measurelen marker, set its time position
		if measure_num + 1 in measurelen_dict:
			measurelentime_dict[measure_num + 1] = current_timepos
		# if the current measure_len isn't 4/4, add a new 4/4 measurelen marker for the next measure
		elif measure_len != 1:
			measurelen_dict[measure_num + 1] = 1.0
			measurelentime_dict[measure_num + 1] = current_timepos
		current_bpmpos_i += (bpms_in_measure - 1)
	
	# sort keysounds by their index
	keysound_indices = list(keysound_dict)
	keysound_indices.sort()

	# DTX-specific overlapping sample handling
	if parsing_mode == MODE_DTX:
		guitar_samples = []
		bass_samples = []
		for channel in channelsample_dict:
			if channel in DTX_BG_CHANNELS:
				# trim overlapping samples within each background channel
				sample_array = channelsample_dict[channel]
				sample_array.sort(key=sample_pos_sort_key)
				for s in range(len(sample_array) - 1):
					sample = sample_array[s]
					next_sample = sample_array[s+1]
					if sample["pos"] + sample["length"] > next_sample["pos"]:
						sample["length"] = next_sample["pos"] - sample["pos"]
			elif channel in DTX_GUITAR_CHANNELS:
				guitar_samples += channelsample_dict[channel]
			elif channel in DTX_BASS_CHANNELS:
				bass_channels += channelsample_dict[channel]
		# trim overlapping samples in guitar
		guitar_samples.sort(key=sample_pos_sort_key)
		for s in range(len(guitar_samples) - 1):
			sample = guitar_samples[s]
			next_sample = guitar_samples[s+1]
			if sample["pos"] + sample["length"] > next_sample["pos"]:
				sample["length"] = next_sample["pos"] - sample["pos"]
		# trim overlapping samples in bass
		bass_samples.sort(key=sample_pos_sort_key)
		for s in range(len(bass_samples) - 1):
			sample = bass_samples[s]
			next_sample = bass_samples[s+1]
			if sample["pos"] + sample["length"] > next_sample["pos"]:
				sample["length"] = next_sample["pos"] - sample["pos"]
	
	# write rpp
	print("Writing {}...".format(out_file))
	with open(out_file, "w") as rpp_out:
		rpp_out.write("<REAPER_PROJECT\n")
		rpp_out.write("TEMPO {} 4 4\n".format(chart_bpm))
		rpp_out.write("MASTERTRACKVIEW 1 0.6667 0.5 0.5 0 0 0 0 0 0\n")
		rpp_out.write("MASTER_VOLUME {} 0 -1 -1 1\n".format(master_volume / 100.0))
		rpp_out.write("VIDEO_CONFIG 0 0 256\n")
		rpp_out.write("PANMODE 3\n")
		# create tempomap - bpms & time signatures
		if len(bpm_positions) or len(measurelentime_dict) > 1:
			rpp_out.write("<TEMPOENVEX\n")
			# bpm markers
			for bpm_pos in bpm_positions:
				bpmtime = bpmtime_dict[bpm_pos]
				bpm = bpm_dict[bpm_pos]
				rpp_out.write("PT {} {} 1\n".format(bpmtime, bpm))
			# time signature markers
			for measurelen_pos in measurelentime_dict:
				measurelentime = measurelentime_dict[measurelen_pos]
				measurelen = measurelen_dict[measurelen_pos]
				# convert measure length into time signature fraction
				ts_num, ts_den = measurelen.as_integer_ratio()
				# ensure denominator is a multiple of 4
				den4_factor = 4 / ts_den
				if den4_factor > 1:
					ts_num *= den4_factor
					ts_den *= den4_factor
				if ts_num > 256 or ts_den > 256:
					print("Ignoring unusual time signature {}/{} at beat {}".format(ts_num, ts_den, measurelen_pos))
				else:
					rpp_out.write("PT {} 0 1 {} 0 3\n".format(measurelentime, ts_den*65536 + ts_num))
			rpp_out.write(">\n")
		# create keysound tracks
		for i in keysound_indices:
			if i in sample_dict:
				# create a track for each keysound
				keysound_name, keysound_ext = os.path.splitext(keysound_dict[i])
				rpp_out.write("<TRACK\n")
				rpp_out.write('NAME "{}"\n'.format(keysound_name))
				if parsing_mode == MODE_BMS:
					rpp_out.write("VOLPAN {} 0 -1 -1 1\n".format(1/3.0)) # 1/3 track volume
				elif parsing_mode == MODE_DTX:
					if i in keysoundvol_dict:
						vol = keysoundvol_dict[i]
					else:
						vol = 1.0
					if i in keysoundpan_dict:
						pan = keysoundpan_dict[i]
					else:
						pan = 0.0
					rpp_out.write("VOLPAN {} {} -1 -1 1\n".format(vol / 2.0, pan)) # 1/2 track volume
				# sort samples by position
				sample_array = sample_dict[i]
				sample_array.sort(key=sample_pos_sort_key)
				for s in range(len(sample_array)):
					sample = sample_array[s]
					if parsing_mode == MODE_BMS:
						# cut the lengths of BMS samples that overlap themselves
						if s + 1 < len(sample_array):
							next_sample = sample_array[s+1]
							if sample["pos"] + sample["length"] > next_sample["pos"]:
								sample["length"] = next_sample["pos"] - sample["pos"]
					# add a keysound sample to the track
					rpp_out.write("<ITEM\n")
					rpp_out.write("POSITION {}\n".format(sample["pos"]))
					rpp_out.write("LENGTH {}\n".format(sample["length"]))
					rpp_out.write("NAME {}\n".format(keysound_dict[i]))
					# TODO per-sample volume
					# if "volume" in sample:
						# rpp_out.write("VOLPAN {} 0 1 -1\n".format(sample["volume"]))
					if keysound_ext.lower() == WAV_EXT:
						rpp_out.write("<SOURCE WAVE\n")
					elif keysound_ext.lower() == OGG_EXT:
						rpp_out.write("<SOURCE VORBIS\n")
					else:
						# unknown audio type
						rpp_out.write("<SOURCE\n")
					rpp_out.write('FILE "{}"\n'.format(keysound_dict[i]))
					rpp_out.write(">\n")
					rpp_out.write(">\n")
				rpp_out.write(">\n")
		rpp_out.write(">\n")
		
	print("Done, output to {}".format(out_file))

def main():
	global parsing_mode
	if len(sys.argv) < 2:
		usage()
	else:
		chart_file = sys.argv[1]
		chart_filename, chart_ext = os.path.splitext(chart_file)
		if chart_ext == BMS_EXT or chart_ext == BME_EXT:
			parsing_mode = MODE_BMS
		elif chart_ext == DTX_EXT:
			parsing_mode = MODE_DTX
		else:
			print("Error: Unknown chart file type: {}".format(chart_ext))
			usage()
		if len(sys.argv) > 2:
			out_file = sys.argv[2]
		else:
			out_file = os.path.splitext(os.path.basename(chart_file))[0] + RPP_EXT
		parse_keysounds(chart_file, out_file)

if __name__ == "__main__":
	main()
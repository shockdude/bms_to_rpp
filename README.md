# BMS to REAPER project (RPP) converter v0.6
Written by shockdude in Python 3.7\
REAPER is property of Cockos Incorporated: https://www.reaper.fm/ \
Uses pydub: https://github.com/jiaaro/pydub

Usage: `python bms_to_rpp.py chart_file.bms [output_file.rpp]`

Supports WAV keysounds.\
If your BMS does not include WAV keysounds, recommend converting them to WAV first.\
OGG keysounds supported only if ffmpeg is installed, and processing will be very slow.

Supports BPMs, extended BPMs, measure lengths/time signatures, and STOPs.\
Negative BPMs untested. Other BMS features may not be implemented.

Major props to the BMS command memo: http://hitkey.nekokan.dyndns.info/cmds.htm

# BMS to REAPER project (RPP) converter v0.5
Written by shockdude in Python 3.7\
REAPER is property of Cockos Incorporated: https://www.reaper.fm/ \
Uses pydub: https://github.com/jiaaro/pydub

Usage: `python bms_to_rpp.py chart_file.bms [output_file.rpp]`

Supports WAV keysounds, recommended.\
OGG keysounds supported if ffmpeg is installed, but processing will be slow.

Supports BPMs, extended BPMs, measure lengths/time signatures, and STOPs.\
Does not support negative BPMs. Other BMS features may not be implemented.

Major props to the BMS command memo: http://hitkey.nekokan.dyndns.info/cmds.htm

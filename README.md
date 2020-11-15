# BMS to REAPER project (RPP) converter
Convert BMS charts (also BME, BML, PMS, DTX) into REAPER projects.

Usage: Drag-and-drop the chart onto `bms_to_rpp.py` \
Or use the command line: `python bms_to_rpp.py chart_file.bms [output_project.rpp]`

WAV keysounds recommended. \
If your BMS does not include WAV keysounds, convert them to WAV first. \
OGG/MP3 keysounds supported only if ffmpeg is installed, and processing will be very slow.

Written by shockdude in Python 3.7 \
REAPER is property of Cockos Incorporated: https://www.reaper.fm/ \
Uses pydub: https://github.com/jiaaro/pydub \
Major props to the BMS command memo: http://hitkey.nekokan.dyndns.info/cmds.htm \
Major props to the DTX data format spec: https://ja.osdn.net/projects/dtxmania/wiki/DTX%2520data%2520format

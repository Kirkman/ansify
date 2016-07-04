#! /usr/bin/env python2
# -*- coding: utf-8 -*-
# from moviepy.editor import VideoFileClip
import argparse
import sys
import os.path
from PIL import Image, ImageChops, ImageEnhance
import av
import sauce
import datetime
import ujson as json
from ansidefs import ANSI_SHADED_BLOCKS, UNICODE_SHADED_BLOCKS, ANSI_SHADED_BLOCKS_TO_RGB, ANSI_RESET, INFINITY
from ansify import timing,foreground_code, background_code, return_ansi_code, closest_ansi_color, color_distance, print_frame, save_frame

def is_number(s):
	try:
		complex(s) # for int, long, float and complex
	except ValueError:
		return False
	return True

def get_frame_rate(stream):
	if stream.average_rate.denominator and stream.average_rate.numerator:
		return float(stream.average_rate)
	if stream.time_base.denominator and stream.time_base.numerator:
		return 1.0/float(stream.time_base)
	else:
		raise ValueError("Unable to determine FPS")

def convert_frame(frame, options):
	im = frame.to_image()
	original_width = float(im.size[0])
	original_height = float(im.size[1])

	output_max_width = float(options['output_width'] - 1)
	output_max_height = float(options['output_height'])

	# Using the typical ANSI character set, we should shrink image vertically
	# so that the tall characters don't distort the image
	if options['output_font'] == '8x16':
		aspect_ratio = 0.5
	else:
		aspect_ratio = 1
	original_height = original_height * aspect_ratio


	h_factor = output_max_width / original_width
	v_factor = output_max_height / original_height

	output_factor = min(h_factor, v_factor)

	output_width = int(original_width * output_factor)
	output_height = int(original_height * output_factor)

#  	print '\033[0m\n' + str(output_factor) + ' | ' + str(output_width) + ', ' + str(output_height)

	im = im.resize( ( output_width, output_height ) )
	# adjust brightness if needed
	if options['output_brightness'] != float(1):
		enhancer = ImageEnhance.Brightness(im)
		im = enhancer.enhance( options['output_brightness'] )
# 	im = im.convert('P', palette=Image.ADAPTIVE, colors=256)
	im = im.convert('RGB')

# 	im.save('frames/frame-%04d.png' % frame.index)

	w = im.size[0]
	# Clear screen between frames
	o = '\033[2j\033[H'
	last_char = None

	for i, p in enumerate(im.getdata()):
		if i % w == 0 and i != 0:
			# the '\033[0m' part is useful on the command line
			# to keep background from displaying if console is
			# wider than the ansi art
			o += '\033[0m\n'
			last_char = None
# 		if im.mode == 'RGBA' and p[3] == 0:
# 			o += ' '
		else:
			this_char = closest_ansi_color(p,options)
			#print str(this_char) + ' | ' + str(last_char)
			c = return_ansi_code(this_char,last_char)
			o += c
			last_char = this_char
	return o




# This function is used for writing an animation chunk by chunk.
# Appends to an existing file, which will need to have been created.
# Will NOT write SAUCE record.
def save_animation_chunk(o,options):
	if options['output_file'] is not sys.stdout:
		# Replace Unicode shaded blocks with ANSI CP437 equivalents
		o = o.encode('cp437')
		o.replace( u'\u2591'.encode('cp437'), chr(176) )
		o.replace( u'\u2592'.encode('cp437'), chr(177) )
		o.replace( u'\u2593'.encode('cp437'), chr(178) )
		o.replace( u'\u2588'.encode('cp437'), chr(219) )
		output_file = open(options['output_file'], 'ab')
		output_file.write(o)
		output_file.close()


# Append SAUCE record to existing file
def add_sauce(o,options):
	# Determine the height by counting lines in a frame
	# Determine the width by counting actual chars in a line
	frames = o.split('\033[2j\033[H');
	lines = frames[-1].splitlines()
	cols = 0
	for char in lines[1]:
		if char in [ u'\u2591', u'\u2592', u'\u2593', u'\u2588' ]:
			cols += 1
	height = len(lines)
	width = cols
# 	print 'h: ' + str(height) + ' | w: ' + str(width)
	# Add SAUCE information. Mostly important for art wider than 80px
	ansi = sauce.SAUCE( options['output_file'] )
	ansi.datatype = 'Character'
	ansi.filetype = 'Ansimation'
	ansi.date = datetime.datetime.now()
	ansi.tinfo1 = width  #TInfo1 for Character/ANSI is width
	ansi.tinfo2 = height  #TInfo2 for Character/ANSI is height
	ansi.write( ansi )



# Saves the entire animation at once, appends a SAUCE record
def save_animation(o,options):
	# Determine the height by counting lines in a frame
	# Determine the width by counting actual chars in a line
	frames = o.split('\033[2j\033[H');
	lines = frames[-1].splitlines()
	cols = 0
	for char in lines[1]:
		if char in [ u'\u2591', u'\u2592', u'\u2593', u'\u2588' ]:
			cols += 1
	height = len(lines)
	width = len(cols)

	# Replace Unicode shaded blocks with ANSI CP437 equivalents
	o = o.encode('cp437')
	o.replace( u'\u2591'.encode('cp437'), chr(176) )
	o.replace( u'\u2592'.encode('cp437'), chr(177) )
	o.replace( u'\u2593'.encode('cp437'), chr(178) )
	o.replace( u'\u2588'.encode('cp437'), chr(219) )
	# Add SAUCE information. Very important for art wider than 80px
	ansi = sauce.SAUCE( data=o )
	ansi.datatype = 'Character'
	ansi.filetype = 'Ansimation'
	ansi.date = datetime.datetime.now()
	ansi.tinfo1 = width  #TInfo1 for Character/ANSI is width
	ansi.tinfo2 = height  #TInfo2 for Character/ANSI is height
	ansi.write( options['output_file'] )





# MAIN FUNCTION
def convert_movie(options):
	print 'Loading color cache'
	options['cache'] = json.load(open('color_cache.json'))

	print 'Importing clip'
	container = av.open(options['filename'])
	stream = next(s for s in container.streams if s.type == b'video')

	# This time is in seconds
	# sw: , 0:06-1:07 
	# lotr: 1:17-2:21,  
	# empire: 0:20-1:32,  
	# matrix: 1:00-2:16
	# tfa1: 3:14-4:29, 195-269
	# tfa2: 11:10-12:40, 670-760

	startTime = options['start_time']
	fps = get_frame_rate(stream) #29.97002997
	print fps
	framesToSkip = int( startTime * fps )
# 	desiredFrameRate = 6
	duration = options['duration']
	durationFrames = duration * fps

	all_frames = ''
	last_frame = ''
	for index, packet in enumerate( container.demux(stream) ):
		for frame in packet.decode():
			if (
				index > framesToSkip and
				#(index % desiredFrameRate == 0) and
				index < (framesToSkip + durationFrames)
			):
				o = convert_frame(frame, options)
				if options['output_file'] is sys.stdout:
					print_frame(o,options)
				else:
					print_frame(o,options)
					# save_frame(o,frame.index,options)
					# This is for the build-a-giant-blob approach
# 					all_frames += o
					# This is the write-each-frame-and-flush-approach
					save_animation_chunk(o,options)
					last_frame = o
					o = ''

	add_sauce(last_frame,options)


# This is for the build-a-giant-blob approach
# 	if options['output_file'] is not sys.stdout:
# 		save_animation(all_frames,options)


# 	json.dump(options['cache'], open('color_cache.json','w'))



if __name__ == '__main__':
	options = {
		'filename': None,
		'output_file': None,
		'output_width': None,
		'output_height': None,
		'output_brightness': None,
		'output_font': None,
		'start_time': None,
		'duration': None,
		'cache': {},
	}

	parser = argparse.ArgumentParser()
	parser.add_argument(
		'filename',
		help='File to convert to ANSI'
	)
	parser.add_argument(
		'-o',
		'--output_file',
		nargs='?',
		default=sys.stdout,
		help='Path to the output file. Default: stdout'
	)
	parser.add_argument(
		'-ow',
		'--output_width',
		nargs='?',
		default=80,
		help='Maximum width of output'
	)
	parser.add_argument(
		'-oh',
		'--output_height',
		nargs='?',
		default=24,
		help='Maximum height of output'
	)
	parser.add_argument(
		'-of',
		'--output_font',
		nargs='?',
		default='8x16',
		help='ANSI font size. Either 8x16 (default) or 8x8.'
	)
	parser.add_argument(
		'-ob',
		'--output_brightness',
		nargs='?',
		default=1,
		help='Brightness adjustment'
	)

	parser.add_argument(
		'-s',
		'--start_time',
		nargs='?',
		default=0,
		help='Start time (in seconds). Default: 0'
	)

	parser.add_argument(
		'-d',
		'--duration',
		nargs='?',
		default=10,
		help='Duration (in seconds). Default: 10'
	)

	args = parser.parse_args()

	if args.filename:
		options['filename'] = args.filename
	if args.output_file:
		options['output_file'] = args.output_file
	if args.output_width:
		if is_number(args.output_width):
			options['output_width'] = int(args.output_width)
	if args.output_height:
		if is_number(args.output_height):
			options['output_height'] = int(args.output_height)
	if args.output_font:
		if args.output_font.lower() in ['8x16','8x8']:
			options['output_font'] = args.output_font.lower()
	if args.output_brightness:
		if is_number(args.output_brightness):
			options['output_brightness'] = float(args.output_brightness)
	if args.start_time:
		if is_number(args.start_time):
			options['start_time'] = float(args.start_time)
	if args.duration:
		if is_number(args.duration):
			options['duration'] = float(args.duration)

	print 'Running'
	extension = os.path.splitext(args.filename)[1].replace('.','')
	print extension


	if extension.lower() in ['gif','png','jpg','jpeg','tif','tiff']:
		convert_image(options)
	elif extension.lower() in ['mov','mpg','mpeg','mp2','mp4','m4v','mkv','avi','wmv','flv','ogg','webm']:
		convert_movie(options)


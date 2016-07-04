#! /usr/bin/env python2
# -*- coding: utf-8 -*-
#
# This routine is adapted from: https://gist.github.com/jdiaz5513/9218791
#
# Things I changed:
# * Cache the results of color_distance() lookups, for a big speed-up.
# * Adjusted the RGB values for ANSI_COLORS to match original CGA values
# * Changed default fill character to a PC-ANSI shaded block character
# * Added some timer code to help with optimizing the conversion routine

from PIL import Image, ImageChops, ImageEnhance
import math
import argparse
import sys
import os.path
import datetime
import time
import functools
import ujson as json
import av
import sauce
from ansidefs import ANSI_SHADED_BLOCKS, UNICODE_SHADED_BLOCKS, ANSI_SHADED_BLOCKS_TO_RGB, ANSI_RESET, INFINITY


def timing(f):
	def wrap(*args):
		time1 = time.time()
		ret = f(*args)
		time2 = time.time()
		print '%s function took %0.3f ms' % (f.func_name, (time2-time1)*1000.0)
		return ret
	return wrap



def foreground_code(x):
	return {
		'black':        '30',
		'red':          '31',
		'green':        '32',
		'yellow':       '33',
		'blue':         '34',
		'magenta':      '35',
		'cyan':         '36',
		'white':        '37',
    }[x]

def background_code(x):
    return {
		'black':        '40',
		'red':          '41',
		'green':        '42',
		'yellow':       '43',
		'blue':         '44',
		'magenta':      '45',
		'cyan':         '46',
		'white':        '47',
    }[x]

def return_ansi_code(this_char,last_char):
	# This version keeps track of the previous character.
	# It tries to streamline the CSI sequences by avoiding
	# repetition when successive characters have similar attributes.

	this_char_obj = ANSI_SHADED_BLOCKS_TO_RGB[this_char]
	this_fg = foreground_code( this_char_obj['fg'] )
	this_bg = background_code( this_char_obj['bg'] )
	this_bold = this_char_obj['bold']
	this_block = UNICODE_SHADED_BLOCKS[ int(this_char_obj['gradient']) - 1 ]

# 	print '\033[0m============================================='
# 	print str(this_char_obj['fg']) + ' | ' + str(this_fg) + ' | ' + str(this_char_obj['bg']) + ' | ' + str(this_bg) + ' | ' + str(this_bold) + ' | '

	if last_char is not None:
		last_char_obj = ANSI_SHADED_BLOCKS_TO_RGB[last_char]
		last_fg = foreground_code( last_char_obj['fg'] )
		last_bg = background_code( last_char_obj['bg'] )
		last_bold = last_char_obj['bold']

		if ( this_fg == last_fg and this_bg == last_bg and this_bold == last_bold ):
# 			print 'this_fg == last_fg and this_bg == last_bg and this_bold == last_bold'
			return this_block

		elif ( this_fg == last_fg and this_bg == last_bg ):
# 			print 'this_fg == last_fg and this_bg == last_bg'
# 			print '\033[' + this_bold + ';' + this_fg + ';' + this_bg + 'm' + this_block
			return '\033[' + this_bold + ';' + this_fg + ';' + this_bg + 'm' + this_block

		elif ( this_bg == last_bg and this_bold == last_bold ):
# 			print 'this_bg == last_bg and this_bold == last_bold'
# 			print '\033[' + this_fg + 'm' + this_block
			return '\033[' + this_fg + 'm' + this_block

		elif ( this_bg == last_bg and this_bold == '1' ):
# 			print 'this_bg == last_bg and this_bold == 1'
# 			print '\033[1;' + this_fg + 'm' + this_block
			return '\033[1;' + this_fg + 'm' + this_block

		elif ( this_bg == last_bg and this_bold == '0' ):
# 			print 'this_bg == last_bg and this_bold == 0'
# 			print '\033[0;' + this_fg + ';' + this_bg + 'm' + this_block
			return '\033[0;' + this_fg + ';' + this_bg + 'm' + this_block

		elif ( this_fg == last_fg and this_bold == last_bold ):
# 			print 'this_fg == last_fg and this_bold == last_bold'
# 			print '\033[' + this_bg + 'm' + this_block
			return '\033[' + this_bg + 'm' + this_block

		# This one is pointless. If you have to change bold, 
		# then you have to reset the foreground color too.
# 		elif ( this_fg == last_fg ):
# 			print 'this_fg == last_fg'
# 			print '\033[' + this_bold + ';' + this_bg + 'm' + this_block
# 			return '\033[' + this_bold + ';' + this_bg + 'm' + this_block

# 	print 'FAILED ALL TESTS'
# 	print '\033[' + this_bold + ';' + this_fg + ';' + this_bg + 'm' + this_block
	return '\033[' + this_bold + ';' + this_fg + ';' + this_bg + 'm' + this_block


def return_ansi_names(index):
	ansiObj = ANSI_SHADED_BLOCKS_TO_RGB[index]
	fg = ansiObj['fg']
	bg = ansiObj['bg']
	blockChar = ANSI_SHADED_BLOCKS[ int(ansiObj['gradient']) - 1 ]
	return fg + ' | ' + bg + ' | ' + ansiObj['gradient']

# This is for creating a huge cache file with every possible color combination
def cache_all_colors():
	options = {}
	options['cache'] = json.load(open('color_cache.json'))

	for r in range(255):
		for g in range(255):
			for b in range(255):
				print 'r: ' + str(r) + ' | g: ' + str(g) + ' | b: ' + str(b)
				desired_color = { 
					'r': r, 
					'g': g, 
					'b': b, 
				}
				color_id = str(r).zfill(3) + str(g).zfill(3) + str(b).zfill(3)
				closest_dist = INFINITY
				closest_color_index = 0
				for i, block_char in enumerate(ANSI_SHADED_BLOCKS_TO_RGB):
					block_char_color = {
						'r': int( block_char['r'] ), 
						'g': int( block_char['g'] ), 
						'b': int( block_char['b'] ), 
					}
					d = color_distance(block_char_color, desired_color)
					if d < closest_dist:
						closest_dist = d
						closest_color_index = i
				# Add this index to our color cache so we don't have to look it up again
				options['cache'][color_id] = closest_color_index

	json.dump(options['cache'], open('color_cache.json','w'))


#@timing
def closest_ansi_color(desired_color,options):
	# Change RGB color value into a string we can use as a dict key
	desired_color = { 
		'r': desired_color[0], 
		'g': desired_color[1], 
		'b': desired_color[2], 
	}
	color_id = str(desired_color['r']).zfill(3) + str(desired_color['g']).zfill(3) + str(desired_color['b']).zfill(3)
	# If we've calculated color_distance for this color before, it will be cached.
	# Use cached value instead of performing color_distance again.

	if color_id in options['cache']:
		return options['cache'][color_id]

	# Look up the closest ANSI color
	else:
		closest_dist = INFINITY
		closest_color_index = 0
		for i, block_char in enumerate(ANSI_SHADED_BLOCKS_TO_RGB):
			block_char_color = {
				'r': int( block_char['r'] ), 
				'g': int( block_char['g'] ), 
				'b': int( block_char['b'] ), 
			}
			d = color_distance(block_char_color, desired_color)
			if d < closest_dist:
				closest_dist = d
				closest_color_index = i
		# Add this index to our color cache so we don't have to look it up again
# 		options['cache'][color_id] = closest_color_index
		return closest_color_index


# New algorithm for calculating color distance
# Much faster, and much better color matching.
# Adapted from this stackoverflow answer: http://stackoverflow.com/a/2103422/566307
def color_distance( e1, e2 ):
	rmean = ( e1['r'] + e2['r'] ) / 2;
	r = e1['r'] - e2['r'];
	g = e1['g'] - e2['g'];
	b = e1['b'] - e2['b'];
# 	return math.sqrt((((512+rmean)*r*r)>>8) + 4*g*g + (((767-rmean)*b*b)>>8));
	# omitting square root gives slight speed increase
	return (((512+rmean)*r*r)>>8) + 4*g*g + (((767-rmean)*b*b)>>8);



# Print single frame/image to console
def print_frame(o,options):
	# Output to console (unicode)
	print o
	#print get_frame_rate(stream)



# Save single frame/image to ANSI file 
def save_frame(o,options):
	if options['output_file'] is not sys.stdout:
		# Replace Unicode shaded blocks with ANSI CP437 equivalents
		o = o.encode('cp437')
		o.replace( u'\u2591'.encode('cp437'), chr(176) )
		o.replace( u'\u2592'.encode('cp437'), chr(177) )
		o.replace( u'\u2593'.encode('cp437'), chr(178) )
		o.replace( u'\u2588'.encode('cp437'), chr(219) )
		output_file = open(options['output_file'], 'wb')
		output_file.write(o)
		output_file.close()



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


def convert_frame(im, options):
	original_width = float(im.size[0])
	original_height = float(im.size[1])

	output_max_width = float(options['output_width'] - 1)
	output_max_height = float(options['output_height'])

	# Using the typical 8x16 ANSI character set, we should shrink image vertically
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
	ansi.filetype = options['output_format']
	ansi.date = datetime.datetime.now()
	ansi.tinfo1 = width  #TInfo1 for Character/ANSI is width
	ansi.tinfo2 = height  #TInfo2 for Character/ANSI is height
	ansi.write( options['output_file'] )





#@timing
def convert_image(options):
	print 'loading cache'
	options['cache'] = json.load(open('color_cache.json'))
	print 'beginning conversion'

	im = Image.open( options['filename'] )
	o = convert_frame(im, options)
	o += ANSI_RESET + '\n\n'

	# Save to ANSI file and add SAUCE record
	if options['output_file'] is not sys.stdout:
		save_frame(o,options)
		add_sauce(o,options)

	# Output to console (unicode)
	else:
		print_frame(o,options)

# 	json.dump(options['cache'], open('color_cache.json','w'))



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
				im = frame.to_image()
				o = convert_frame(im, options)
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









if __name__ == '__main__':
	options = {
		'filename': None,
		'output_file': None,
		'output_width': None,
		'output_height': None,
		'output_brightness': None,
		'output_font': None,
		'output_format': None,
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
		options['output_format'] = 'Ansi'
		convert_image(options)
	elif extension.lower() in ['mov','mpg','mpeg','mp2','mp4','m4v','mkv','avi','wmv','flv','ogg','webm']:
		options['output_format'] = 'Ansimation'
		convert_movie(options)


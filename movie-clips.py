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
from ansify import timing,foreground_code, background_code, return_ansi_code, closest_ansi_color_new, color_distance_new

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
	if options['output_width'] == 80:
		aspect_ratio = 0.5
	else:
		aspect_ratio = 1
	original_height = original_height * aspect_ratio


	h_factor = output_max_width / original_width
	v_factor = output_max_height / original_height

	output_factor = min(h_factor, v_factor)

	output_width = int(original_width * output_factor)
	output_height = int(original_height * output_factor)

#  	print '\033[0m\n'
# 	print 'orig_w: ' + str(original_width)
# 	print 'orig_h: ' + str(original_height)
# 	print 'out_max_w: ' + str(output_max_width)
# 	print 'out_max_h: ' + str(output_max_height)
# 	print 'h_factor: ' + str(h_factor)
# 	print 'v_factor: ' + str(v_factor)
# 	print 'out_factor: ' + str(output_factor)
# 	print 'out_w: ' + str(output_width)
# 	print 'out_h: ' + str(output_height)


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
			this_char = closest_ansi_color_new(p,options)
			#print str(this_char) + ' | ' + str(last_char)
			c = return_ansi_code(this_char,last_char)
			o += c
			last_char = this_char
	return o

#@timing
def print_frame(o,options):
	# Output to console (unicode)
	print o
	#print get_frame_rate(stream)

# def write_animation_frame(o,options):
# 	if options['output_file'] is not sys.stdout:
# 		# Replace Unicode shaded blocks with ANSI CP437 equivalents
# 		o = o.encode('cp437')
# 		o.replace( u'\u2591'.encode('cp437'), chr(176) )
# 		o.replace( u'\u2592'.encode('cp437'), chr(177) )
# 		o.replace( u'\u2593'.encode('cp437'), chr(178) )
# 		o.replace( u'\u2588'.encode('cp437'), chr(219) )
# 		output_file = open(options['output_file'], 'ab')
# 		output_file.write(o)
# 		output_file.close()


def write_animation_frame(o,i,options):
	if options['output_file'] is not sys.stdout:
		# Replace Unicode shaded blocks with ANSI CP437 equivalents
		lines = o.splitlines()
		height = len(lines)
		o = o.encode('cp437')
		o.replace( u'\u2591'.encode('cp437'), chr(176) )
		o.replace( u'\u2592'.encode('cp437'), chr(177) )
		o.replace( u'\u2593'.encode('cp437'), chr(178) )
		o.replace( u'\u2588'.encode('cp437'), chr(219) )
		output_file = 'frames/frame-%04d.ans' % i
		nfo = sauce.SAUCE(data=o)
		nfo.datatype = 'Character'
		nfo.filetype = 'Ansi'
		nfo.date = datetime.datetime.now()
		nfo.tinfo1 = options['output_width']  #TInfo1 for Character/ANSI is width
		nfo.tinfo2 = height  #TInfo2 for Character/ANSI is height
# 		nfo.tinfo2 = options['output_height']  #TInfo2 for Character/ANSI is height
		nfo.write( output_file )





def save_animation(o,options):
	# Save to ANSI file
	if options['output_file'] is not sys.stdout:
# 		first_line = o.splitlines()[0]
# 		width = len(first_line)
# 		print width
		# Replace Unicode shaded blocks with ANSI CP437 equivalents
		o = o.encode('cp437')
		o.replace( u'\u2591'.encode('cp437'), chr(176) )
		o.replace( u'\u2592'.encode('cp437'), chr(177) )
		o.replace( u'\u2593'.encode('cp437'), chr(178) )
		o.replace( u'\u2588'.encode('cp437'), chr(219) )
		# Add SAUCE information. Mostly important for art wider than 80px
		nfo = sauce.SAUCE(data=o)
		nfo.datatype = 'Character'
		nfo.filetype = 'Ansimation'
		nfo.date = datetime.datetime.now()
		nfo.tinfo1 = options['output_width']  #TInfo1 for Character/ANSI is width
		nfo.tinfo2 = options['output_height']  #TInfo2 for Character/ANSI is height
		nfo.write(options['output_file'])
# 		output_file = open(options['output_file'], 'ab')
# 		output_file.write(o)
# 		output_file.close()

def convert_movie(options):
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

	skipToTime = 696
	fps = get_frame_rate(stream) #29.97002997
	print fps
	framesToSkip = int( skipToTime * fps )
# 	desiredFrameRate = 6
	duration = 10
	durationFrames = duration * fps

	all_frames = ''
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
# 					print_frame(o,options)
					write_animation_frame(o,frame.index,options)
					# This is for the build-a-giant-blob approach
					all_frames += o
					# This is the write-each-frame-and-flush-approach
# 					write_animation_frame(o,options)
# 					o = ''



# This is for the build-a-giant-blob approach
	if options['output_file'] is not sys.stdout:
		save_animation(all_frames,options)


# 	json.dump(options['cache'], open('color_cache.json','w'))



if __name__ == '__main__':
	options = {
		'filename': None,
		'output_file': None,
		'output_width': None,
		'output_height': None,
		'cache': {},
	}

	parser = argparse.ArgumentParser()
	parser.add_argument(
		'filename',
		help='File to convert to ASCII art'
	)
	parser.add_argument(
		'-o',
		'--output_file',
		nargs='?',
		default=sys.stdout,
		help='Path to the output file, defaults to stdout'
	)
	parser.add_argument(
		'-ow',
		'--output_width',
		nargs='?',
		default=80,
		help='Width of output'
	)
	parser.add_argument(
		'-oh',
		'--output_height',
		nargs='?',
		default=24,
		help='Height of output'
	)
	parser.add_argument(
		'-ob',
		'--output_brightness',
		nargs='?',
		default=1,
		help='Brightness adjustment'
	)



	args = parser.parse_args()

	if args.filename:
		options['filename'] = args.filename
	if args.output_file:
		options['output_file'] = args.output_file
	if args.output_width:
		options['output_width'] = int(args.output_width)
	if args.output_height:
		options['output_height'] = int(args.output_height)
	if args.output_brightness:
		options['output_brightness'] = float(args.output_brightness)

	print 'Running'
	extension = os.path.splitext(args.filename)[1].replace('.','')
	print extension


	if extension.lower() in ['gif','png','jpg','jpeg','tif','tiff']:
		convert_image(options)
	elif extension.lower() in ['mov','mpg','mpeg','mp2','mp4','m4v','mkv','avi','wmv','flv','ogg','webm']:
		convert_movie(options)


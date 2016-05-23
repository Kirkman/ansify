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
import datetime
import time
import functools
import ujson as json
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
					d = color_distance_new(block_char_color, desired_color)
					if d < closest_dist:
						closest_dist = d
						closest_color_index = i
				# Add this index to our color cache so we don't have to look it up again
				options['cache'][color_id] = closest_color_index

	json.dump(options['cache'], open('color_cache.json','w'))


#@timing
def closest_ansi_color_new(desired_color,options):
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
			d = color_distance_new(block_char_color, desired_color)
			if d < closest_dist:
				closest_dist = d
				closest_color_index = i
		# Add this index to our color cache so we don't have to look it up again
# 		options['cache'][color_id] = closest_color_index
		return closest_color_index

# New algorithm for calculating color distance
# Much faster, and much better color matching.
# Adapted from this stackoverflow answer: http://stackoverflow.com/a/2103422/566307
def color_distance_new( e1, e2 ):
	rmean = ( e1['r'] + e2['r'] ) / 2;
	r = e1['r'] - e2['r'];
	g = e1['g'] - e2['g'];
	b = e1['b'] - e2['b'];
# 	return math.sqrt((((512+rmean)*r*r)>>8) + 4*g*g + (((767-rmean)*b*b)>>8));
	# omitting square root gives slight speed increase
	return (((512+rmean)*r*r)>>8) + 4*g*g + (((767-rmean)*b*b)>>8);


#@timing
def convert_image(options):

# 	options['cache'] = json.load(open('color_cache.json'))

	# render an image as ASCII by converting it to RGBA then using the
	# color lookup table to find the closest colors, then filling with 
	# fill_char
	# TODO: use a set of fill characters and choose among them based on
	# color value
	im = Image.open( options['filename'] )
	if im.mode != 'RGB':
		im = im.convert('RGB')

	original_width = float(im.size[0])
	original_height = float(im.size[1])

	output_max_width = float(options['output_width'] - 1)
	output_max_height = float(options['output_height'])

	# Using the typical ANSI character set, we should shrink image vertically
	# so that the tall characters don't distort the image
	if options['output_width'] == 80:
		aspect_ratio = 0.5
	else:
		aspect_ratio = 0.5
	original_height = original_height * aspect_ratio


	h_factor = output_max_width / original_width
	v_factor = output_max_height / original_height

	output_factor = min(h_factor, v_factor)

	output_height = int(original_height * output_factor)
	output_width = int(original_width * output_factor)

	im = im.resize( ( output_width, output_height ) )
	# Reduce color palette to speed things up
# 	im = im.convert('P', palette=Image.ADAPTIVE, colors=256)
# 	im.save('converted.png') # Save copy of shrunk image for debugging
# 	im = im.convert('RGB')

	w = im.size[0]
	o = ''
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
			this_char = closest_ansi_color_new( p, options )
			#print str(this_char) + ' | ' + str(last_char)
			c = return_ansi_code( this_char, last_char )
			o += c
			last_char = this_char

	o += ANSI_RESET + '\n\n'

	# Save to ANSI file
	if options['output_file'] is not sys.stdout:
		# Replace Unicode shaded blocks with ANSI CP437 equivalents
		o = o.encode('cp437')
		o.replace( u'\u2591'.encode('cp437'), chr(176) )
		o.replace( u'\u2592'.encode('cp437'), chr(177) )
		o.replace( u'\u2593'.encode('cp437'), chr(178) )
		o.replace( u'\u2588'.encode('cp437'), chr(219) )
		# Add SAUCE information. Mostly important for art wider than 80px
		nfo = sauce.SAUCE(data=o)
		nfo.datatype = 'Character'
		nfo.filetype = 'Ansi'
		nfo.date = datetime.datetime.now()
		nfo.tinfo1 = options['output_width']  #TInfo1 for Character/ANSI is width
		nfo.tinfo2 = options['output_height']  #TInfo2 for Character/ANSI is height
		nfo.write( options['output_file'] )
		#output_file = open(output_file, 'wb')
		#output_file.write(o)
		#output_file.close()

	# Output to console (unicode)
	else:
		print o

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



	args = parser.parse_args()

	if args.filename:
		options['filename'] = args.filename
	if args.output_file:
		options['output_file'] = args.output_file
	if args.output_width:
		options['output_width'] = int(args.output_width)
	if args.output_height:
		options['output_height'] = int(args.output_height)

	convert_image(options)

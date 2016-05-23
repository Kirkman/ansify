Ansify
============

This is an experimental Python system for converting images and videos into ANSI and ANSImation files.

There are other (superior) textmode converters out there, particularly libcaca. Ansify is tightly focused on producing ANSI that can be displayed on BBSes. It is restricted to the classic 8 CGA colors in the foreground and 16 in the background. Color "blends" are achieved using the CP437 shaded block characters. 


Not a release
---------------

* The code in this repository is very messy, and is not really meant for public consumption. Future versions will be cleaner and have some documentation.


Pre-requisites
---------------

Ansify requires the following libraries:
* [Pillow](https://python-pillow.org) for image and video conversion
* [ffmpeg](https://ffmpeg.org) for video conversion
* [PyAV](https://mikeboers.github.io/PyAV/) for video conversion
* [ujson](https://pypi.python.org/pypi/ujson) for caching colors
* My [modified version](https://github.com/Kirkman/sauce) of [Sauce](https://github.com/tehmaze/sauce) for writing SAUCE records

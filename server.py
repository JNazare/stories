import sys
from os import system
import subprocess
import cv2
import numpy as np
import cv2.cv as cv
import tesseract
from skimage import filter
import json

def removeNonAscii(s): return "".join(i for i in s if ord(i)<128)

def flag_lang(abbr):
	"""Converts different language abbreviations to a standard"""
	pass

def process_image(im):
	"""Removes background, etc. from images"""
	pass

def run_ocr(img):
	"""Generates text from image"""
	# top, left, width, height = set_bounds(bounds)
	# CROP IMAGE BEFORE RUNNING OCR
	api = tesseract.TessBaseAPI()
	api.Init("/usr/local/share/","eng",tesseract.OEM_DEFAULT)
	api.SetPageSegMode(tesseract.PSM_AUTO)
	
	tesseract.SetCvImage(img, api)
	txt=api.GetUTF8Text()
	conf=api.MeanTextConf()
	api.End()
	
	if conf > 50:
		return clean_text(removeNonAscii(txt))
	else:
		return False
	
def clean_text(txt):
	txt = txt.strip().replace('\n', ' ')
	return txt

def set_bounds(bounds):
	scale_factor = 10.88
	bounds = json.loads(bounds)
	top = float(bounds['top'])*scale_factor
	left = float(bounds['left'])*scale_factor
	width = float(bounds['width'])*scale_factor
	height = float(bounds['height'])*scale_factor
	return top, left, width, height

def inpaint_image(img, bounds):
	top, left, width, height = set_bounds(bounds)
	pt1 = [left, top]
	pt2 = [left, top+height]
	pt3 = [left+width, top+height]
	pt4 = [left+width, top]
	text_area = np.array([ pt2, pt3, pt4, pt1 ], np.int32)
	neg_mask = np.zeros(img.shape, dtype=np.uint8)
	cv2.fillConvexPoly(neg_mask, text_area, (255,255,255))
	neg_mask = np.invert(neg_mask)
	mask = np.bitwise_or(img, neg_mask)
	gray = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
	ret, thresh = cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
	blank = cv2.inpaint(img,thresh,3,cv2.INPAINT_TELEA)
	return blank

def main(img_file):
	txt = run_ocr(img_file)
	txt = clean_text(txt)
	blank_image_file = inpaint_image(img_file)
	return txt, blank_image_file

if __name__ == "__main__":
	main(sys.argv[1])
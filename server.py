import sys
from os import system
import subprocess
import cv2
import numpy as np
import cv2.cv as cv
import tesseract
from skimage import filter
import json
from scipy.stats import mode
from sklearn.cluster import KMeans

# Global Vars
TMP_FOLDER = "tmp/"
TMP_PAGE_FILEPATH = TMP_FOLDER+"page.jpg"
TMP_TEXT_FILEPATH = TMP_FOLDER+"text.jpg"

def removeNonAscii(s): return "".join(i for i in s if ord(i)<128)

def flag_lang(abbr):
	"""Converts different language abbreviations to a standard"""
	pass

def run_ocr(img):
	"""Generates text from image"""
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
	return [top, left, width, height]

def save_text_area(img, bounds):
	top, left, width, height = set_bounds(bounds)
	top, left, width, height = int(top), int(left), int(width), int(height)
	crop_img = img[top:top+height, left:left+width]
	imgray = cv2.cvtColor(crop_img,cv2.COLOR_BGR2GRAY)
	blur = cv2.GaussianBlur(imgray,(5,5),0)
	ret,thresholded_image = cv2.threshold(blur,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
	cv2.imwrite(TMP_TEXT_FILEPATH, thresholded_image)
	text = run_ocr(cv.LoadImage(TMP_TEXT_FILEPATH))
	return True

def main(img_file):
	txt = run_ocr(img_file)
	txt = clean_text(txt)
	blank_image_file = inpaint_image(img_file)
	return txt, blank_image_file

if __name__ == "__main__":
	main(sys.argv[1])
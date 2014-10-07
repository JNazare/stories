from flask import Flask, url_for, request, session, redirect, escape, render_template
from flask.ext.pymongo import PyMongo
import base64
from werkzeug import secure_filename
import datetime
from bson.objectid import ObjectId
import urllib
from PIL import Image
from StringIO import StringIO
import server as server
import cv2
import numpy as np
import tesseract
import ast

import sys
from os import system
import subprocess
import cv2.cv as cv
from skimage import filter
import json

app = Flask(__name__)
mongo = PyMongo(app)

TMP_FILEPATH = "tmp/page.jpg"
# set the secret key.  keep this really secret:

ALLOWED_EXTENSIONS = set(['jpg', 'jpeg'])

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def import_binary_image(file_object):
    raw_data = file_object.read()
    data = StringIO(raw_data)
    im = Image.open(data)
    return im, raw_data

def export_binary_image_to_buffer(im, quality=None):
    export = StringIO()
    if quality:
        im.save(export, format='JPEG', quality=quality)
    else:
        im.save(export, format='JPEG')
    binary_data = export.getvalue().encode('base64')
    return binary_data

def start_new_book(cover_page):
    books = mongo.db.books
    im, raw_data = import_binary_image(cover_page)
    compressed_binary_data = export_binary_image_to_buffer(im, quality=20)
    # tmp_page.save(TMP_FILEPATH)
    raw_binary_data = export_binary_image_to_buffer(im)
    book_details = {'compressed_pages':[], 'blank_pages':[], "bounding_boxes":[], "text":[]}
    # book_details['raw_pages'].append(raw_binary_data)
    book_details['compressed_pages'].append(compressed_binary_data)
    book_details['created_at']=datetime.datetime.utcnow()
    book_details['last_opened']=datetime.datetime.utcnow()
    book_id = books.insert(book_details, manipulate=True)
    with open(TMP_FILEPATH, 'wb') as f:
        f.write(raw_data)
    return book_id, len(book_details['compressed_pages'])-1

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'email' in session:
        if request.method == 'POST':
            page = request.files['page']
            if page and allowed_file(page.filename):
                filename = secure_filename(page.filename)
                book_id, page_id = start_new_book(page)
                if book_id:
                    process_url = 'process/'+str(book_id)+"/"+str(page_id)
                    return redirect(process_url)
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        search = users.find_one({"email":request.form['email']})
        if search:
            user = search
            if user['password'] == request.form['password']:
                session['email']=user['email']
                session['nativelang']=user['nativelang']
                return redirect(url_for('index'))
            else:
                error = 'Invalid credentials'
        else: 
            error = 'No user found'
        return render_template('login.html', error=error)
    return render_template('login.html')

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('email', None)
    session.pop('nativelang', None)
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        users = mongo.db.users
        user_details = {}
        user_details['email'] = request.form['email']
        user_details['password'] = request.form['password']
        user_details['nativelang'] = request.form['nativelang']
        users.insert(user_details, manipulate=True)
        session['email']=user_details['email']
        session['nativelang']=user_details['nativelang']
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/process/<book_id>/<page_id>', methods=['GET', 'POST'])
def process(book_id, page_id):
    if 'email' in session:
        books = mongo.db.books
        book = books.find_one({"_id":ObjectId(book_id)})
        page_to_process=book['compressed_pages'][int(page_id)]
        return render_template('process_image.html', img_tag=urllib.quote(page_to_process.rstrip('\n')), book_id=book_id, page_id=page_id)
    return redirect(url_for('login'))

@app.route('/erase/<book_id>/<page_id>', methods=['GET', 'POST'])
def erase(book_id, page_id):
    if 'email' in session:
        bounds = request.form['bounds']
        books = mongo.db.books
        book = books.find_one({"_id":ObjectId(book_id)})
        img = cv2.imread(TMP_FILEPATH)
        # buf = np.fromstring(base64.b64decode(page_to_process), dtype=np.uint8)
        # img = cv2.imdecode(buf, cv2.CV_LOAD_IMAGE_UNCHANGED)
        blank_image = server.inpaint_image(img, bounds)
        binary_blank_image = base64.encodestring(cv2.imencode('*.jpg', blank_image)[1]) #export_binary_image_to_buffer(Image.fromarray(blank_image), quality=30)
        blank_pages = book['blank_pages']
        bounding_boxes = book['bounding_boxes']
        blank_pages.append(binary_blank_image)
        bounding_boxes.append(bounds)
        books.update({'_id':ObjectId(book_id)}, {"$set": {'blank_pages': blank_pages, 'bounding_boxes': bounding_boxes}})
        return redirect("/extract_text/"+book_id+"/"+page_id)
    return redirect(url_for('login'))
    
@app.route('/extract_text/<book_id>/<page_id>', methods=['GET', 'POST'])
def extract_text(book_id, page_id):
    books = mongo.db.books
    book = books.find_one({"_id":ObjectId(book_id)})
    img = cv.LoadImage(TMP_FILEPATH)
    text = server.run_ocr(img)
    texts = book['text']
    texts.append(text)
    # texts.append(text)
    books.update({'_id':ObjectId(book_id)}, {"$set": {'text': texts}})
    return redirect('/read/'+book_id+"/"+page_id)

@app.route('/read/<book_id>/<page_id>')
def read(book_id, page_id):
    books = mongo.db.books
    book = books.find_one({"_id":ObjectId(book_id)})
    blank_page = book["blank_pages"][int(page_id)]
    text = book['text'][int(page_id)]
    text = str(text)
    print text
    bounds = book['bounding_boxes'][int(page_id)]
    bounds = json.loads(bounds)
    return render_template('blank_image.html', img_tag=urllib.quote(blank_page.rstrip('\n')), book_id=book_id, page_id=page_id, text=text, bounds=bounds)

@app.route('/original_image/<int:book>/<int:page>')
def original_image(book, page):
    return 'Show original image'

@app.route('/blank_image/read/<int:book>/<int:page>')
def blank_image(book, page):
    return 'Show blank image'

@app.route('/settings')
def settings():
    return 'Settings page'

@app.errorhandler(404)
def page_not_found(error):
    return '404'
    # return render_template('page_not_found.html'), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)



    # buf = np.fromstring(base64.b64decode(page_to_process), dtype=np.uint8)
    # img = cv2.imdecode(buf, cv2.CV_LOAD_IMAGE_UNCHANGED)
    # text = server.run_ocr(img)
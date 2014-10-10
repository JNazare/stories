from flask import Flask, url_for, request, session, redirect, render_template
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
import cv2.cv as cv
import json
import secrets

app = Flask(__name__)
mongo = PyMongo(app)
app.secret_key = secrets.db_secret()

# Global Vars
TMP_FOLDER = "tmp/"
TMP_PAGE_FILEPATH = TMP_FOLDER+"page.jpg"
TMP_TEXT_FILEPATH = TMP_FOLDER+"text.jpg"
ALLOWED_EXTENSIONS = set(['jpg', 'jpeg'])

def logged_in(session):
    return True if 'email' in session else False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def init_new_book():
    books = mongo.db.books
    book_details = {'compressed_pages':[], 'background_pages':[], "bounding_boxes":[], "text":[]}
    book_details['created_at']=datetime.datetime.utcnow()
    book_details['last_opened']=datetime.datetime.utcnow()
    book_id = books.insert(book_details, manipulate=True)
    return str(book_id)

def save_tmp_page(raw_data):
    with open(TMP_PAGE_FILEPATH, 'wb') as f:
        f.write(raw_data)
    f.close()
    return True

def compress_image(im, quality):
    export = StringIO()
    im.save(export, format='JPEG', quality=quality)
    binary_data = export.getvalue().encode('base64')
    return binary_data

def update_book(books, book_id, book_fields, book_values):
    updates = {}
    book = books.find_one({"_id":ObjectId(book_id)})
    for index in range(len(book_fields)):
        tmp = book[book_fields[index]]
        tmp.append(book_values[index])
        updates[book_fields[index]]= tmp
    books.update({'_id':ObjectId(book_id)}, {"$set": updates})
    return True

def make_and_save_new_page(book_id, page):
    books = mongo.db.books
    book = books.find_one({"_id":ObjectId(book_id)})
    if page and allowed_file(page.filename):
        raw_data = page.read()
        save_tmp_page(raw_data)

        data = StringIO(raw_data)
        im = Image.open(data)
        compressed_binary_data = compress_image(im, quality=20)
        html_ready_compressed_image = urllib.quote(compressed_binary_data.rstrip('\n'))
        
        # original_im = cv2.imread(TMP_PAGE_FILEPATH)
        # binary_image = base64.encodestring(cv2.imencode('*.jpg', original_im)[1])
        binary_image = compress_image(im, quality=50)
        html_ready_image = urllib.quote(binary_image.rstrip('\n'))

        update_book(books, book_id, ['compressed_pages', 'background_pages'], [html_ready_compressed_image, html_ready_image])
        return html_ready_compressed_image, html_ready_image
    return False

##############

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = mongo.db.users
        search = users.find_one({"email":request.form['email']})
        if search:
            user = search
            if user['password'] == request.form['password']:
                session['user_id']=str(user['_id'])
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
        user_id = users.insert(user_details, manipulate=True)
        session['user_id']=str(user_id)
        session['email']=user_details['email']
        session['nativelang']=user_details['nativelang']
        return redirect(url_for('index'))
    return render_template('signup.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if logged_in(session):
        if request.method == 'POST':
            users = mongo.db.users
            updated_lang = request.form['nativelang']
            users.update({'_id':ObjectId(session['user_id'])}, {"$set": {"nativelang": updated_lang}})
            session['nativelang']=updated_lang
        return render_template('settings.html', nativelang=session['nativelang'])
    return redirect(url_for('login'))

##############

@app.route('/', methods=['GET', 'POST'])
def index():
    if logged_in(session):
        if request.method == 'POST':
            cover_page = request.files['page']
            book_id = init_new_book()
            page_id = str(0)
            make_and_save_new_page(book_id, cover_page)
            if book_id and page_id: return redirect(url_for('select', book_id=book_id, page_id=page_id))
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/select/<book_id>/<page_id>', methods=['GET', 'POST'])
def select(book_id, page_id):
    if logged_in(session):
        books = mongo.db.books
        book = books.find_one({"_id":ObjectId(book_id)})
        page_to_process=book['compressed_pages'][int(page_id)]
        return render_template('process_image.html', 
            process=True,
            img_tag=page_to_process, 
            book_id=book_id, 
            page_id=page_id)
    return redirect(url_for('login'))

# This neds to be changed so that it is only saving to compressed pages
# once... when the page is made, not in / or /add and it is not re-pull
@app.route('/add/<book_id>/<page_id>', methods=['GET', 'POST'])
def add(book_id, page_id):
    if logged_in(session):
        books = mongo.db.books
        book = books.find_one({"_id":ObjectId(book_id)})
        compressed_page, background_page = make_and_save_new_page(book_id, request.files['page'])
        return render_template('process_image.html', 
            process=True,
            img_tag=background_page, 
            book_id=book_id, 
            page_id=page_id)
    return redirect(url_for('login'))

@app.route('/process/<book_id>/<page_id>', methods=['GET', 'POST'])
def process(book_id, page_id):
    if logged_in(session):
        books = mongo.db.books
        bounds = request.form['bounds']

        img = cv2.imread(TMP_PAGE_FILEPATH)
        server.save_text_area(img, bounds)
        
        img = cv.LoadImage(TMP_TEXT_FILEPATH)
        text = server.run_ocr(img)
        
        update_book(books, book_id, ['bounding_boxes', 'text'], [bounds, text])
        
        return redirect(url_for('read', 
            book_id=book_id, 
            page_id=page_id))
    return redirect(url_for('login'))

@app.route('/read/<book_id>/<page_id>')
def read(book_id, page_id):
    if logged_in(session):
        books = mongo.db.books
        book = books.find_one({"_id":ObjectId(book_id)})
        compressed_pages = book["compressed_pages"]
        text = str(book['text'][int(page_id)])
        bounds = book['bounding_boxes'][int(page_id)]
        return render_template('read_page.html', 
            read=True,
            book_id=book_id,
            page_id=page_id,
            text=text,
            bounds=json.loads(bounds),
            thumbnails=compressed_pages)
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html', error=error), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

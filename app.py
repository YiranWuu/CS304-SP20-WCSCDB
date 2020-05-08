from flask import (Flask, render_template, make_response, url_for, request,
                   redirect, flash, session, send_from_directory, jsonify
                   )
from werkzeug.utils import secure_filename
from datetime import datetime
from threading import Lock
import cs304dbi as dbi
app = Flask(__name__)

import random
import cs304dbi as dbi
import sqlOperations
import bcrypt

app.secret_key = 'your secret here'
# replace that with a random key
app.secret_key = ''.join([ random.choice(('ABCDEFGHIJKLMNOPQRSTUVXYZ' +
                                          'abcdefghijklmnopqrstuvxyz' +
                                          '0123456789'))
                           for i in range(20) ])

from flask_cas import CAS
from flask_cas import login_required
from flask_cas import logout

CAS(app)

app.config['CAS_SERVER'] = 'https://login.wellesley.edu:443'
app.config['CAS_LOGIN_ROUTE'] = '/module.php/casserver/cas.php/login'
app.config['CAS_LOGOUT_ROUTE'] = '/module.php/casserver/cas.php/logout'
app.config['CAS_VALIDATE_ROUTE'] = '/module.php/casserver/serviceValidate.php'
app.config['CAS_AFTER_LOGIN'] = 'logged_in'
# the following doesn't work :-(
# app.config['CAS_AFTER_LOGOUT'] = 'after_logout'


# This gets us better error messages for certain common request errors
app.config['TRAP_BAD_REQUEST_ERRORS'] = True

nameDB = 'wcscdb_db'

'''Login route for CAS.'''
@app.route('/logged_in/')
def logged_in():
    flash('Wellesley credentials successfully verified')
    if '_CAS_TOKEN' in session:
        token = session['_CAS_TOKEN']
    if 'CAS_ATTRIBUTES' in session:
        attribs = session['CAS_ATTRIBUTES']
        # print('CAS_attributes: ')
        # for k in attribs:
        #     print('\t',k,' => ',attribs[k])
    if 'CAS_USERNAME' in session:
        is_logged_in = True
        username = session['CAS_USERNAME']
        conn = dbi.connect()
        print(sqlOperations.checkDuplicate(conn,username))
        if sqlOperations.checkDuplicate(conn,username)!=None:
            flash('You already have a registered account on WCSCDB.')
            return redirect(url_for('index'))
        # print(('CAS_USERNAME is: ',username))
    else:
        is_logged_in = False
        username = None
        print('CAS_USERNAME is not in the session')
    return render_template('register.html',
                           cas_attributes = session.get('CAS_ATTRIBUTES'))

'''URL for main page. 
User will see the login form only if they are not logged in.'''
@app.route('/', methods=["GET","POST"])
def index():
    if request.method=="GET":
        if 'userID' in session:
            return render_template('main.html')
        else: # not logged in
            return render_template('login.html')
    else: # POST
        # if request.form.get('submit')=="Login":
        try:
            userID = request.form['userID']
            password = request.form['password'] # the user's input as is
            conn = dbi.connect()
            userInfo = sqlOperations.login(conn,userID)
            if userInfo is None:
                # Same response as wrong password,
                # so no information about what went wrong
                flash('Login information incorrect. Try again or register')
                return redirect(url_for('index'))
            hashed = userInfo['hashed'] # hashed password stored in database
            a = password.encode('utf-8')
            b = hashed.encode('utf-8')
            hashed2 = bcrypt.hashpw(password.encode('utf-8'),hashed.encode('utf-8'))
            hashed2_str = hashed2.decode('utf-8')
            if hashed2_str == hashed:
                flash('successfully logged in as '+userID)
                session['userID'] = userID
                session['logged_in'] = True
                return redirect(url_for('index'))
            else:
                flash('Login incorrect. Try again or register')
                return redirect(url_for('index'))
        except Exception as err:
            flash('form submission error '+str(err))
            return redirect(url_for('index'))

'''URL for registering new account, 
after users have been verified as a Wellesley student.'''
@app.route("/register/", methods=["POST"])
def register():
    try:
        password = request.form['password']
        confirmPassword = request.form['confirmPassword']
        if password!=confirmPassword:
            flash('Passwords do not match. Try again.')
            return redirect(url_for('logged_in'))
        name = request.form['name']
        year = request.form['year']
        email = request.form['email']
        userID = request.form['userID']
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_str = hashed.decode('utf-8')
        conn = dbi.connect()
        curs = dbi.cursor(conn)
        try:
            sqlOperations.registerUser(conn,userID,hashed,name,year,email)
        except Exception as err:
            flash('User already registered: {}'.format(repr(err)))
            return redirect(url_for('index'))
        flash('Successfully registered')
        return redirect(url_for('index'))
    except Exception as err:
        flash('form submission error '+str(err))
        return redirect(url_for('index'))

'''URL for viewing and editing user's personal profile.'''
@app.route("/profile/", methods=["GET","POST"])
def profile():
    try:
        if 'userID' in session:
            userID = session['userID']
            conn = dbi.connect()
            if request.method=="POST":
                visibility = request.form.get('visibility')
                interests = request.form.get('interests')
                if interests==None:
                    interests = ""
                introduction = request.form.get('introduction')
                if introduction==None:
                    introduction = ""
                career = request.form.get('career')
                if career==None:
                    career = ""
                sqlOperations.updateProfile(conn,userID,visibility,interests,introduction,career)
            # both POST and GET
            profileInfo = sqlOperations.profileInfo(conn,userID)
            if profileInfo['visibility']=='Y':
                visibleY = "checked"
                visibleN = ""
            else:
                visibleY = ""
                visibleN = "checked"
            for key in profileInfo:
                value = profileInfo[key]
                if value==None:
                    profileInfo[key] = ""

            return render_template('profile.html',result=profileInfo,visible=visibleY,invisible=visibleN)

        else:
            flash('you are not logged in. Please login or join')
            return redirect( url_for('index') )
    except Exception as err:
        flash('some kind of error '+str(err))
        return redirect(url_for('index'))

'''URL for logout.
Logs out of WCSCDB account, not CAS.'''
@app.route('/log_out/')
def log_out():
    try:
        if 'userID' in session:
            session.pop('userID')
            session.pop('logged_in')
            flash('You are logged out')
            return redirect(url_for('index'))
        else:
            flash('You are not logged in. Please log in or register')
            return redirect(url_for('index'))
    except Exception as err:
        flash('some kind of error '+str(err))
        return redirect(url_for('index'))

'''URL for network page.'''
@app.route("/network/", methods=["GET","POST"])
def network():
    if request.method =='GET':
        try:
            if 'userID' in session:
                conn = dbi.connect()
                profileNetwork = sqlOperations.profileNetwork(conn)
                print(profileNetwork)
                return render_template("network.html", result=profileNetwork) 
            else:
                flash('You are not logged in. Please log in or register')
                return redirect(url_for('index'))
        except Exception as err:
            flash('some kind of error '+str(err))
            return redirect(url_for('index'))
    else: 
        try:
            conn = dbi.connect()
            form_data = request.form
            searchType = form_data['kind']
            searchWord = form_data['keyword']
            if searchType =='name':
                profileNetwork = sqlOperations.searchProfileByName(conn,searchWord) 
            elif searchType == "year":
                profileNetwork = sqlOperations.searchProfileByYear(conn,searchWord)
            elif searchType == 'interest':
                profileNetwork = sqlOperations.searchProfileByInterest(conn,searchWord)
            return render_template("network.html", result=profileNetwork) 
        except Exception as err:
            flash('some kind of error '+str(err))
            return redirect(url_for('network'))
                    
'''URL for posts on tips.'''
@app.route("/tips/",methods=["GET","POST"])
def tips():
    if request.method == 'GET':
        try:
            if 'userID' in session:   
                conn = dbi.connect() 
                posts = sqlOperations.getAllPosts(conn)
                return render_template('tips.html',posts=posts) 
            else:
                flash('You are not logged in. Please log in or register')
                return redirect(url_for('index'))
        except Exception as err:
            flash('some kind of error '+str(err))
            return redirect(url_for('index'))
    elif request.method == 'POST':
        if "userID" in session:
            userID = session['userID']
            form_data = request.form
            conn = dbi.connect()
            if form_data.get('kind')==None: #submit a post
                print("here",form_data)
                title = form_data["postTitle"]
                content =form_data['article']
                timeNow = datetime.now() 
                authorID = userID
                testPostID = random.randint(1, 100) #need to fix later
                print(title,content,timeNow,authorID,testPostID)
                try:
                    sqlOperations.addPost(conn,authorID,content,title,testPostID,timeNow)
                    posts = sqlOperations.getAllPosts(conn)
                    #currently, once the user submit a post, they will not be able to edit it
                    return redirect(url_for('tips',posts=posts))
                    flash('Successfully submitted your post!')
                except Exception as err:
                    flash('Some kind of post submission error: {}'.format(repr(err)))
                    posts = sqlOperations.getAllPosts(conn)
                    return redirect(url_for('tips',posts=posts))

            else:#search for posts
                try:
                    if form_data['kind'] =='author':
                        authorName= form_data['searchWord']
                        posts = sqlOperations.searchPostbyAuthor(conn,authorName)
                        return render_template('tips.html',posts=posts)
                    elif form_data['kind'] =='keyword':
                        keyword = form_data['searchWord']
                        posts = sqlOperations.searchPostbyKeyword(conn,keyword) 
                        return render_template('tips.html',posts=posts)
                except Exception as err:
                    flash('Post submission error: {}'.format(repr(err)))
                    posts = sqlOperations.getAllPosts(conn)
                    return redirect(url_for('tips',posts=posts))      
        else:
            flash('You are not logged in. Please log in or register')
            return redirect(url_for('index'))

'''URL for profiles on network, visible to other users.'''
@app.route("/profile/<userID>")
def alumnusPage(userID):
    profileInfo = sqlOperations.profileInfo(conn,userID)    
    print("profileInfo is", profileInfo)
    return render_template("alumnus.html",result = profileInfo)


if __name__ == '__main__':
    
    import sys, os
    if len(sys.argv) > 1:
        # arg, if any, is the desired port number
        print(sys.argv[1])
        port = int(sys.argv[1])
        
        assert(port>1024)
        if not(1943 <= port <= 1950):
            print('For CAS, choose a port from 1943 to 1950')
            sys.exit()
    else:
        port = os.getuid()
        cnf = dbi.cache_cnf()   # defaults to ~/.my.cnf
        dbi.use(nameDB)
        conn = dbi.connect()
    app.debug = True
    app.run('0.0.0.0',port) 
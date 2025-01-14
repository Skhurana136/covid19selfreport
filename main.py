import sys
import random
from flask import Flask, render_template, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
from flask import request, flash
from flask_bootstrap import Bootstrap
from models import QuizForm, DeleteForm
import json
from copy import deepcopy
import firebase_admin
import urllib
import datetime
from firebase_admin import credentials, firestore
from itsdangerous import URLSafeTimedSerializer, Signer
from plz.plz2kreis import plz2kreis, plz2longlat

testing_mode = True

if testing_mode:
    from config_test import Config
    cred = credentials.Certificate("covid19test-218a3-firebase-adminsdk-o6s3e-40e98ea53d.json")
else:
    from config import Config
    cred = credentials.Certificate("covid19-selfreport-firebase-adminsdk-jfup1-8a45aedc76.json")

app = Flask(__name__)
app.config.from_object(Config)

Bootstrap(app)

firebase_admin.initialize_app(cred)
db = firestore.client()
report_ref = db.collection("Report")
rki_ref = db.collection("RKI_Laender")
landkreise_ref = db.collection("Landkreise")

BASECOORDS = [51.3150172,9.3205287]

def generate_confirmation_token(signature):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(signature, salt=app.config['SECURITY_PASSWORD_SALT'])

def confirm_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        signature = serializer.loads(
            token,
            salt=app.config['SECURITY_PASSWORD_SALT'],
            max_age=expiration
        )
    except:
        return False
    return signature

def createreportdict(form):
    dct = {}

    dct["plz"] = form.plz.data

    crd = json.loads(form.geolocation.data)
    dct["latitude"] = crd["latitude"]
    dct["longitude"] = crd["longitude"]
    dct["accuracy"] = crd["accuracy"]
    if dct["latitude"] == 0:
        dct["longitude"], dct["latitude"] = plz2longlat(dct["plz"])
        
    dct["latitude_rand"] = dct["latitude"] + 0.01 * random.random()
    dct["longitude_rand"] = dct["longitude"] + 0.01 * random.random()

    dct["test"] = form.test.data
    dct["arzt"] = form.arzt.data
    dct["quarantine"] = form.quarantine.data
    dct["datetest"] = None if form.datetest.data is None else form.datetest.data.strftime("%d.%m.%Y")
    dct["notherstest"] = form.notherstest.data
    dct["symptoms"] = ', '.join(form.symptoms.data)
    dct["dayssymptoms"] = form.dayssymptoms.data
    dct["notherssymptoms"] = form.notherssymptoms.data
    dct["age"] = form.age.data
    dct["sex"] = form.sex.data
    dct["plz"] = form.plz.data
    try:
        dct["kreis"] = plz2kreis[dct["plz"]]
    except:
        dct["kreis"] = ""
        print(f"error converting PLZ {dct['plz']} to Kreisebene")

    dct["email_addr"] = form.email_addr.data
    s = Signer(form.password.data)
    dct["signature"] = str(s.sign(form.email_addr.data))

    dct["timestamp"] = firestore.SERVER_TIMESTAMP
    dct["email_confirmed"] = False
    dct["overwritten"] = False
    dct["source"] = "report"
    dct["token"] = str(generate_confirmation_token(dct["signature"]))
    return dct


@app.route('/landkreis/<name>', methods=['GET', 'POST'])
def landkreis(name):
    return render_template('landkreis.html',  name=name)

@app.route('/report', methods=['GET', 'POST'])
def report():
    form = QuizForm(request.form)
    if not form.validate_on_submit():
        return render_template('report.html', form=form)
    if request.method == 'POST':
        dct = createreportdict(form)
        
        report_ref.document(dct["token"]).set(dct)

        oldreports = report_ref.where("signature", '==', dct["signature"]).stream()
        for oldreport in oldreports:
            oldreport = oldreport.to_dict()
            if oldreport["token"] != dct["token"]:
                oldreport["overwritten"] = True
                report_ref.document(oldreport["token"]).set(oldreport)

        #return render_template('confirm_mail.html', mail=dct["email_addr"])
        return render_template('success.html', mail=dct["email_addr"], risk="mittleres")


@app.route('/delete', methods=['GET', 'POST'])
def delete():
    form = DeleteForm(request.form)
    if not form.validate_on_submit():
        return render_template('delete.html', form=form)
    if request.method == 'POST':
        s = Signer(form.password.data)
        signature = str(s.sign(form.email_addr.data))
        oldreports = report_ref.where("signature", '==', signature).stream()
        ndel = 0
        for oldreport in oldreports:
            oldreport = oldreport.to_dict()
            if oldreport["overwritten"] == False:
                ndel += 1
            oldreport["overwritten"] = True
            oldreport["deleted"] = True
            report_ref.document(oldreport["token"]).set(oldreport)

        return render_template('delete_success.html', ndel=ndel)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/impressum')
def impressum():
    return render_template('impressum.html')


@app.route('/info')
def info():
    return render_template('info.html')


@app.route('/getreports')
def getreports():
    reports = [doc.to_dict() for doc in report_ref.where("overwritten", '==', False).stream()]
    data = [{
        "latitude": report["latitude_rand"], 
        "longitude": report["longitude_rand"],
        "symptoms": report["symptoms"],
        "dayssymptoms": report["dayssymptoms"],
        "test": report["test"],
        "source": report["source"],
        "nothers": report["notherssymptoms"],
        "date": report["timestamp"].strftime("%d.%m.%Y")
    } for report in reports]
    return jsonify({"data": data})

@app.route('/getrki')
def getrki():
    reports = [doc.to_dict() for doc in rki_ref.stream()]
    data = [{
        "latitude": report["latitude"], 
        "longitude": report["longitude"],
        "test": report["test"],
        "ncases": report["ncases"],
        "source": report["source"],
        "popup": report["popup"]
    } for report in reports]
    return jsonify({"data": data})


@app.route('/getlaender')
def getlaender():
    reports = [doc.to_dict() for doc in landkreise_ref.where("overwritten", '==', False).stream()]
    data = [{
        "latitude": report["latitude"], 
        "longitude": report["longitude"],
        "test": report["test"],
        "ncases": report["ncases"],
        "source": report["source"],
        "popup": report["popup"]
    } for report in reports]
    return jsonify({"data": data})


if __name__ == '__main__':
    app.run(debug=True)

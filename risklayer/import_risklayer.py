import geojson
import json
import firebase_admin
import random
from firebase_admin import credentials, firestore
import urllib
import pandas as pd
import datetime
from copy import deepcopy

#cred = credentials.Certificate("../covid19-selfreport-firebase-adminsdk-jfup1-8a45aedc76.json")
cred = credentials.Certificate("../covid19test-218a3-firebase-adminsdk-o6s3e-40e98ea53d.json")
firebase_admin.initialize_app(cred)
db = firestore.client()
landkreise = db.collection("Landkreise")
risklayer = pd.read_csv("Risklayer Kreisebene Quellen - Studie 20032020 0330 - Haupt.csv", header=4) 

for i, row in risklayer.iterrows(): 
    name = row.loc["GEN"] + ' ' + row.loc["BEZ"]
    print(name)
    ncases = int(row.loc["Coronavirus Fälle bis 20.03 00:00"])
    source = row.loc["Quelle 1"]
    source_risklayer = "https://docs.google.com/spreadsheets/d/1wg-s4_Lz2Stil6spQEYFdZaBEp8nWW26gVyfHqvcl8s/htmlview#gid=0"
    kreisreportdocs = landkreise.where("name","==",name).order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).stream()
    kreisreporte = [doc.to_dict() for doc in kreisreportdocs]
    if len(kreisreporte) > 0:
        kreisreport = deepcopy(kreisreporte[0])
        kreisreport["ncases"] = ncases
        kreisreport["source"] = source
        kreisreport["number"] += 1
        kreisreport["popup"] = f'<p>{name}<br/>{kreisreport["ncases"]} Fälle<br/>Quelle: <a href="{kreisreport["source"]}">{kreisreport["source"]}<a/><br/>Daten von <a href="https://docs.google.com/spreadsheets/d/1wg-s4_Lz2Stil6spQEYFdZaBEp8nWW26gVyfHqvcl8s/htmlview#gid=0">Risklayer GmbH<a/> Stand 20.3. 0:00<br/><br/><a href="/landkreis/{urllib.parse.quote(name)}">aktuelle Zahlen eintragen<a/><p/>'
        kreisreport["timestamp"] = datetime.datetime.now()
        landkreise.document(name + str(kreisreport["number"])).set(kreisreport)
        old = deepcopy(kreisreporte[0])
        old["overwritten"] = True
        landkreise.document(old["name"] + str(old["number"])).set(old)


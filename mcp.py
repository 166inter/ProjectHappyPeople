import picamera
import os
import numpy as np
import cv2
import sys
import uuid
import time
import types
import json
import requests
import ConfigParser
import cognitive_face as CF
from watson_developer_cloud import VisualRecognitionV3
from cloudant.client import Cloudant

class PHP():

    def __init__(self):
        self._get_config()
        self._camera = picamera.PiCamera()
        self._db = Cloudant(self._config.get("CLOUDANT", "Username"), self._config.get("CLOUDANT", "Password"), account=self._config.get("CLOUDANT", "Host"), connect=True)

    def _get_config(self):
        update       = False
        config_file  = "config.txt"
        self._config = ConfigParser.ConfigParser()

        if os.path.isfile(config_file):
            self._config.read(config_file)
        else:
            print "Config file not found"
            update = True

        if not self._config.has_section('DIRS'):
            print "Adding DIRS part"
            update = True
            self._config.add_section("DIRS")

        if not self._config.has_option("DIRS", "Capture"):
            print "No Capture Directory"
            update = True
            self._config.set("DIRS", "Capture", "/tmp/php/captures")
            if not os.path.isdir(self._config.get("DIRS", "Capture")):
                print "Creating Capture Dir"
                os.makedirs(self._config.get("DIRS", "Capture"))

        if not self._config.has_option("DIRS", "Mosaic"):
            print "No Mosaic Directory"
            update = True
            self._config.set("DIRS", "Mosaic", "/tmp/php/mosaic")
            if not os.path.isdir(self._config.get("DIRS", "Mosaic")):
                print "Creating Mosaic Dir"
                os.makedirs(self._config.get("DIRS", "Mosaic"))

        if not self._config.has_section('CLOUDANT'):
            print "Adding Cloudant part"
            update = True
            self._config.add_section("CLOUDANT")

        if not self._config.has_option("CLOUDANT", "Host"):
            print "No CLOUDANT Host"
            update = True
            self._config.set("CLOUDANT", "Host", "<Host>")

        if not self._config.has_option("CLOUDANT", "Username"):
            print "No Username"
            update = True
            self._config.set("CLOUDANT", "Username", "Didditulle")

        if not self._config.has_option("CLOUDANT", "Password"):
            print "No Password"
            update = True
            self._config.set("CLOUDANT", "Password", "geheim")

        if not self._config.has_section('MICROSOFT'):
            print "Adding Microsoft part"
            update = True
            self._config.add_section("MICROSOFT")

        if not self._config.has_option("MICROSOFT", "FaceKey"):
            print "No Microsoft FaceKey"
            update = True
            self._config.set("MICROSOFT", "FaceKey", "<Facekey>")

        if not self._config.has_section('IBM'):
            print "Adding IBM part"
            update = True
            self._config.add_section("IBM")

        if not self._config.has_option("IBM", "VisualKey"):
            print "No IBM VisualKey"
            update = True
            self._config.set("IBM", "VisualKey", "<VisualKey>")

        if update:
            with open(config_file, 'w') as f:
                self._config.write(f)
            sys.exit(1)

    def _capture_picture(self):
        name = "%s/%s.jpg" % (self._config.get("DIRS", "Capture"), uuid.uuid4())
        self._camera.capture(name)
        return name

    def _get_ms_results(self, filename):
        # https://www.microsoft.com/cognitive-services/en-US/subscriptions
        CF.Key.set(self._config.get("MICROSOFT", "FaceKey"))
        j = {}
        j['filename'] = filename
        j['result']   = CF.face.detect(filename, landmarks=False, attributes='age,gender,smile,facialHair,glasses,emotion')
        return j

    def _get_ibm_results(self, filename):
        visual_recognition = VisualRecognitionV3('2016-05-20', api_key=self._config.get("IBM", "visualkey"))
        with open(filename, 'rb') as image_file:
            return visual_recognition.classify(images_file=image_file)

    def _store_result_in_db(self, ms, ibm):
        if "ms_results" not in self._db.all_dbs():
            self._db.create_database('ms_results')
            print "Creating ms_results"

        if "ibm_results" not in self._db.all_dbs():
            self._db.create_database('ibm_results')
            print "Creating ibm_results"

        if ms is not None:
            ms_database = self._db['ms_results']
            ms_document = ms_database.create_document(ms)

            if ms_document.exists():
                print 'SUCCESS MS!!'

        if ibm is not None:
            ibm_database = self._db['ibm_results']
            ibm_document = ibm_database.create_document(ibm)

            if ibm_document.exists():
                print 'SUCCESS IBM!!'

    def _enhance_image(self, filename, ms, ibm):
        img = cv2.imread(filename)

        for currFace in ms['result']:
            faceRectangle = currFace['faceRectangle']
            score = 0.0
            emotion = "neural"
            for e in currFace['faceAttributes']['emotion']:
                if currFace['faceAttributes']['emotion'][e] > score:
                    score = currFace['faceAttributes']['emotion'][e]
                    emotion = e
            age           = currFace['faceAttributes']['age']
            textToWrite   = "%s - %s" % (age, emotion)
            cv2.rectangle(img, (faceRectangle['left'], faceRectangle['top']),
                               (faceRectangle['left'] + faceRectangle['width'],
                                faceRectangle['top'] + faceRectangle['height']),
                               color=(255, 255, 0), thickness=5)
            cv2.putText(img, textToWrite, (faceRectangle['left'], faceRectangle['top'] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.imwrite('/tmp/test.png', img)

    def _cut_faces(self, filename, ms):
        img = cv2.imread(filename)

        for currFace in ms['result']:
            faceRectangle = currFace['faceRectangle']
            x = faceRectangle['left']
            y = faceRectangle['top']
            w = faceRectangle['width']
            h = faceRectangle['height']

            crop_img = img[y:y+h, x:x+w]
            newfilename = "%s/%s.jpg" % (self._config.get("DIRS", "Mosaic"), uuid.uuid4())
            cv2.imwrite(newfilename, crop_img)

    def main_loop(self):
        current_image = self._capture_picture()
        msjson        = self._get_ms_results(current_image)
        ibmjson       = self._get_ibm_results(current_image)
        print json.dumps(msjson,  sort_keys=True, indent=4, separators=(',', ': '))
        print json.dumps(ibmjson, sort_keys=True, indent=4, separators=(',', ': '))
        self._store_result_in_db(msjson, ibmjson)
        self._enhance_image(current_image, msjson, ibmjson)
        self._cut_faces(current_image, msjson)

if __name__ == "__main__":
    p = PHP()
    p.main_loop()


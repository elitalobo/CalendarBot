import os
import datetime
from datetime import timedelta
from sys import platform as _platform
from flask import Flask
from flask import request
import requests
import json
from pytz import datetime,timezone
from apiclient.discovery import build_from_document, build
import httplib2
import random
from oauth2client.client import OAuth2WebServerFlow,AccessTokenCredentials,Credentials
from oauth2client import client
from flask import Flask, url_for, redirect,render_template, session, request
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.login import LoginManager, login_required, login_user,logout_user, current_user, UserMixin
from requests_oauthlib import OAuth2Session
from requests.exceptions import HTTPError
import pickle
from flock_secret import APP_SECRET, BOT_TOKEN, BOT_GUID


basedir = os.path.abspath(os.path.dirname(__file__))
client_secret = json.loads(open("client_secret.json",'r').read())


class Auth:

    """Google Project Credentials"""
    CLIENT_ID = client_secret['web']['client_id']
    CLIENT_SECRET = client_secret['web']['client_secret']
    REDIRECT_URI = client_secret['web']['redirect_uris'][0]
    AUTH_URI = client_secret['web']['auth_uri']
    TOKEN_URI = client_secret['web']['token_uri']
    USER_INFO = 'https://www.googleapis.com/userinfo/v2/me'
    SCOPE = ["email","https://www.googleapis.com/auth/calendar"]


class Config:
    """Base config"""
    APP_NAME = "CalendarBot"
    SECRET_KEY = os.environ.get("SECRET_KEY") or "somethingsecret"


class DevConfig(Config):
    """Dev config"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, "test.db")


class ProdConfig(Config):
    """Production config"""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, "prod.db")


config = { "dev": DevConfig, "prod": ProdConfig, "default": DevConfig }



"""APP creation and configuration"""
app = Flask(__name__)
app.config.from_object(config['dev'])
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.session_protection = "strong"




class User(db.Model, UserMixin):
    __tablename__ = "flock_users"
    # id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50),primary_key=True)
    flock_token = db.Column(db.Text)
    context_id = db.Column(db.Text,nullable=True)
    
    # created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow())


class EmailCredentials(db.Model,UserMixin):
    __tablename__ = "email_cred"
    email = db.Column(db.String(50),primary_key=True)
    credentials = db.Column(db.Text,nullable=True)



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def get_google_auth(state=None, token=None):
    if token:
        return OAuth2Session(Auth.CLIENT_ID, token=token)
    if state:
        return OAuth2Session(
            Auth.CLIENT_ID,
            state=state,
            redirect_uri=Auth.REDIRECT_URI)
    oauth = OAuth2Session(
        Auth.CLIENT_ID,
        redirect_uri=Auth.REDIRECT_URI,
        scope=Auth.SCOPE)
    return oauth
    

def get_contacts(user_token):

    response = requests.get("https://api.flock.co/v1/roster.listContacts?token="+user_token)

    contacts_list = json.loads(response.text)

    print "raw contacts: ",contacts_list

    contacts_id= []

    for contact in contacts_list:
        contacts_id.append([contact['id'], contact['firstName']])

    return contacts_id

def send_message(to,message,sender_token):

    response= requests.get("https://api.flock.co/v1/chat.sendMessage?to="+to+"&text="+message+"&token="+sender_token)

    #expecting 200 OK status
    
    return response


def get_user_info(user_token):

    response = requests.get("https://api.flock.co/v1/users.getInfo?token="+user_token)
    print json.loads(response.text)

    return json.loads(response.text)


def get_user_email(user_id):
    user_token = User.query.filter_by(user_id=user_id).first().flock_token
    email = get_user_info(user_token)['email']
    return email


def get_credentials(email):
    credentials = Credentials.new_from_json(EmailCredentials.query.filter_by(email=email).first().credentials)
    http = httplib2.Http()
    try:
        http = credentials.authorize(http)
    except e:
        http = credentials.refresh(http)
        http = credentials.authorize(http)
    service = build("calendar", "v3", http=http)
    return service


def getEventsOnXDay(service, date):
    # import ipdb; ipdb.set_trace()
    date_and_time  = timezone('Asia/Kolkata').localize(date).isoformat('T')
    new_date = date + timedelta(hours=24)   
    eventsResult = service.events().list(
    calendarId='primary', timeMin=date_and_time, maxResults=40, singleEvents=True,
    orderBy='startTime').execute()
    events = []
    
    for event in eventsResult["items"]:
        date_ = event["start"]["dateTime"][:-6]
        new_date1 = datetime.datetime.strptime(date_, "%Y-%m-%dT%H:%M:%S")
        if(new_date1<= new_date):
            events.append(event)
    return events


def getSlots(user_emails, date):

    # import ipdb;
        
    
    Minutes = [ True for x in range(0,60*24)]
    #ipdb.set_trace()
    for user in user_emails:
        # credentials = getUserCredentials(user)
        # http = credentials.authorize(httplib2.Http())
        # service = discovery.build('calendar', 'v3', http=http)
       
        print user
        service = get_credentials(user)
        events = getEventsOnXDay(service,date)
        for event in events:
            start_time = event["start"]["dateTime"][:-6].split('T')[1]
            end_time = event["end"]["dateTime"][:-6].split('T')[1]
            hours1 = int(start_time.split(':')[0])
            mins1 = int(start_time.split(':')[1])
            hours2 = int(end_time.split(':')[0])
            mins2 = int(end_time.split(':')[1])
            i=hours1*60+ mins1
            while i<= hours2*60+ mins2 :
                Minutes[i]=False
                i=i+1
    final_slots = []
    i=0
    flag= False;

    start = -1
    end = -1
    while i < 60*24:
        if(flag==False and Minutes[i]==True):
            flag= True
            start = i
            end = i
        elif(flag== True and Minutes[i]==True):
            end = i
        elif(flag == True and Minutes[i]==False):
            final_slots.append({"startTime": str(start/60)+":"+ str(start%60) , "endTime": str(end/60)+ ":" + str(end%60) })
            end=-1
            start =-1
            flag = False
        i=i+1
    if(start!=-1 and end!=-1):
        final_slots.append({"startTime": str(start/60)+":"+ str(start%60) , "endTime": str(end/60)+ ":" + str(end%60) })



    return final_slots



@app.route('/', methods=['GET'])
def index():
    return displayHTML(request)

@app.route('/events', methods=['GET', 'POST'])
def tracking():

    print request
    
    if request.method == 'POST':
        
        data = request.get_json()
        print data
        event_name = data['name']

        #check if event name is app.install, save tokens to database
        if event_name == 'app.install':
            
            user_token = data['token']
            user_id = data['userId']

            user = User.query.filter_by(user_id=user_id).first()
            
            if user is None:
                user = User()
                user.user_id = user_id
                # user.email= user_info['email']

            user.flock_token = user_token
            db.session.add(user)
            db.session.commit()

        elif event_name == 'chat.receiveMessage':

            print data['message']['from']
            #send a response back
            user_id = data['message']['from']
            user_token = User.query.filter_by(user_id=user_id).first().flock_token

            # print data['message']

            email = get_user_info(user_token)['email']
            service = get_credentials(email)


            message = data['message']['text']

            from pytz import datetime

            if message.startswith("suggest"):

                message_list = message.split(" ")

                emails = message_list[6:][0].split(",")

                date = message_list[4].split("-")

                date = [int(i) for i in date]

                date = datetime.datetime(year=date[0],month=date[1],day=date[2])

                slots = getSlots(emails,date)

                # slots= [list(i) for i in slots]

                result = ""

                for i in slots:
                    print i
                    result += "startTime -"+ i.get("startTime") +"\t"+ "endTime -"+ i.get("endTime")+"\n"

                print slots

                send_message(user_id,results,BOT_TOKEN)

                return "200 OK"

            elif message.startswith('show'):
                events_list = getUpcomingEvents(service)

                # print events_list[0][0]
                events_list= map(lambda x: [x[0].split("+")[0].split("T"),x[1]],events_list)

                events_list = map(lambda x: x[0][0]+"\t"+x[0][1]+"\t"+x[1],events_list)

                events_list = '\n'.join(events_list)

                send_message(user_id,events_list,BOT_TOKEN)

            else:

                if len(message.split(" "))<=9:
                    action,event_name,date,start_time,end_time=parse(message)
                    invites= None
                else:
                    action,event_name,date,start_time,end_time,invites= parse(message)
                
                perform_action(user_id,action,event_name,date,start_time,end_time,invites)


        elif event_name == 'app.uninstall':
            #remove user from database

            user = User.query.get(data['userId'])
            db.session.delete(user)
            print "User %s uninstalled app"%data['userId']



        return "200 OK"


def parse(message):

    # import ipdb
    # ipdb.set_trace()

    message_list = message.split(" ")
    action = message_list[0]
    event_name = message_list[2]
    date = message_list[4]
    start_time = message_list[6]
    end_time = message_list[8]
    if len(message_list) <= 9:
        return [action,event_name,date,start_time,end_time]
    
    emails_list = message_list[10:][0].split(",")
    return [action,event_name,date,start_time,end_time,emails_list]

def perform_action(user_id,action,event_name,date,start_time,end_time,invites):

    from pytz import timezone
    from datetime import datetime

    print date,start_time,end_time

    service = get_credentials( get_user_email(user_id))
    dt_start = date+"T"+start_time+"+05:30"
    dt_end = date+"T"+end_time+"+05:30"
    start = { 'timeZone': 'Asia/Calcutta', "dateTime" : dt_start}
    end = { 'timeZone': 'Asia/Calcutta', "dateTime" : dt_end}

    if invites is not None:
        invites = [ {'email' : x } for x in invites]

    if action=='create':


        event_details = {
            "summary": event_name,
            "start": start,
            "end" : end,
            "attendees" : invites }

        createEvent(service,event_details)
        send_message(user_id,"Event Created (y)",BOT_TOKEN)


    if action=='delete':
        # import ipdb; ipdb.set_trace()
        event = getEvent(event_name,start,end,service)
        print event

        if event:
            deleteEvent(event,service)
            send_message(user_id,"Event deleted (y)",BOT_TOKEN)
        else:
            send_message(user_id,"Couldn't find the event.",BOT_TOKEN)

    if action=='update':

        event = getEvent(event_name,None,None,service)

        e = updateEvent(event,start,end,service)

        if e:
            send_message(user_id,"Event Updated (y)",BOT_TOKEN)

        else:
            send_message(user_id,"Couldn't find the event.",BOT_TOKEN)








@app.route('/install_success', methods=['GET', 'POST'])
def sucess():
    print "success"
    print request
    if request.method == 'GET':
        return "200 OK"


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    google = get_google_auth()
    auth_url, state = google.authorization_url(Auth.AUTH_URI, access_type='offline')
    session['oauth_state'] = state
    return render_template('login.html', auth_url=auth_url)


@app.route('/oauth2callback')
def oauth2callback():

  flow = client.flow_from_clientsecrets(
      'client_secret.json',
      scope=Auth.SCOPE,
      redirect_uri=Auth.REDIRECT_URI)

  if 'code' not in request.args:
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)
  else:

    auth_code = request.args.get('code')
    credentials = flow.step2_exchange(auth_code)
    print "credentials: ",credentials.to_json()
    
    session['credentials'] = credentials.to_json()

    http = httplib2.Http()
    http = credentials.authorize(http)
    service = build("calendar", "v3", http=http)
    calendar_list = service.calendarList().list().execute()

    # http = httplib2.Http()
    # credentials.authorize(http)
    resp, content = http.request(Auth.USER_INFO)

    content = json.loads(content)

    print type(content)
    print content
    # print content['email']

    if resp['status']=='200':
        
        email = content['email']
        
        email_cred = EmailCredentials.query.filter_by(email=email).first()

        if email_cred is None:
            #this should not happen
            email_cred = EmailCredentials()
            email_cred.email = email

        email_cred.credentials = credentials.to_json()
        db.session.add(email_cred)
        db.session.commit()

    return redirect(url_for('finishoauth'))

@app.route('/finishoauth')
def finishoauth():
  return redirect("https://web.flock.co/")





################## EVENT HANDLERS #####################################


def getUpcomingEvents(service):
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    print('Getting the upcoming 10 events')
    eventsResult = service.events().list(
        calendarId='primary', timeMin=now, maxResults=10, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    events_list=[]

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])
        print(event)
        events_list.append([start,event['summary']])


    return events_list

def createEvent(service, eventDetails) :
    summary = '';
    location = '';
    description = '';
    start = None;
    end = None;
    attendees = []
        #import ipdb;ipdb.set_trace()
    if "summary" in eventDetails :
        summary = eventDetails["summary"]
    if "description" in eventDetails:
        description 
    if "location" in eventDetails :
        location = eventDetails["location"]
    if "start" in eventDetails:
        start = eventDetails["start"]
    if "end" in eventDetails:
        end = eventDetails["end"]
    if "attendees" in eventDetails:
        attendees = eventDetails["attendees"]
    event = { "summary": summary, "description": description, "location": location, "start": start, "end": end, "attendees": attendees, "sendNotifications": True}
    
    event = service.events().insert(calendarId='primary', body=event, sendNotifications=True).execute()
    print(event)
    return event


def getEvent(summary,start,end,service) :
    # import ipdb; ipdb.set_trace()
    page_token = None
    req_event = None
    while True:
        events = service.events().list(calendarId='primary', pageToken=page_token).execute()
        #import ipdb; ipdb.set_trace()
        for event in events["items"]:
                if(event.get("summary")!= None and event["summary"] == summary and event.get("start")!=None and event["start"] == start and event.get("end")!= None and event["end"] == end):
                    req_event = event
                    break
                if(start == None and end==None and event.get("summary")==summary):
                        req_event = event
                        break
        page_token = events.get('nextPageToken')
        if not page_token:
            break

    return req_event


def updateEvent(event, start, end ,service, description=None):
    event = service.events().get(calendarId='primary', eventId=event["id"]).execute()

    if(description!=None):
        event["description"] = event.description
    
    if(start == None):
        print("Cannot update event. start datetime required")
        return
    if(end == None):
        print("Cannot delete event. end datetime required")
    
    event["start"] = start
    event["end"] = end
    updated_event = service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()

    # Print the updated date.
    print(updated_event['updated'])
    return updated_event

def deleteEvent(event, service):
    service.events().delete(calendarId='primary', eventId=event["id"]).execute()



################################################################################################



if __name__ == '__main__':

    app.run(host='0.0.0.0', port=5000, debug=True)

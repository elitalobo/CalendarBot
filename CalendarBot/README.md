This app aims to help users manage events in their Google Calendar via a chat bot built on the Flock platform.

Functionalities supported:
	1. Create/Update/Delete Calendar events
	2. Invite Guests to your events
	3. Show upcoming events
	4. Suggest slots for meeting based on everyone's availability.


Built this with [Saikat Kumar Dey](https://github.com/arkro/) and Rahul Bansal at Flockathon 2016.


# Requirements

+ App Secret , Bot Secret and Bot ID from [Flock Developer Platform](https://dev.flock.co) 
+ client_secret.json from Google API console
+ web server to host the app. [ We used [ngrok](https://ngrok.com/) to host our app.  ]


# Installation

	pip install REQUIREMENTS.txt


# Running the app

	ngrok http 5000 [if using ngrok platform]
	python app.py


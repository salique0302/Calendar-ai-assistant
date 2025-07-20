import os
import pickle
import datetime
from zoneinfo import ZoneInfo
from dateutil.parser import parse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def create_event(summary, start_time, end_time):
    service = get_calendar_service()
    tz = ZoneInfo("Asia/Kolkata")

    start_dt = parse(start_time).replace(tzinfo=tz)
    end_dt = parse(end_time).replace(tzinfo=tz)

    event = {
        'summary': summary,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': str(tz)},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': str(tz)},
    }

    created_event = service.events().insert(calendarId='primary', body=event).execute()
    return created_event.get('htmlLink')

def get_daily_summary():
    service = get_calendar_service()
    tz = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(tz)
    end = now + datetime.timedelta(days=1)

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    if not events:
        return "You have no events today."

    output = ["Today's events:"]
    for e in events:
        start = parse(e['start'].get('dateTime', e['start'].get('date')))
        start = start.astimezone(tz)
        output.append(f"• {e['summary']} at {start.strftime('%I:%M %p')}")

    return "\n".join(output)

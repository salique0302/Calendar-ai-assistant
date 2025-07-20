import os
import datetime
import streamlit as st
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentType, initialize_agent, Tool
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
from dateutil.parser import parse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle

# Load environment variables
load_dotenv()

# --- Google Calendar API Setup ---
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
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('calendar', 'v3', credentials=creds)

# --- Tools for Calendar Integration ---

class CreateEventInput(BaseModel):
    summary: str = Field(description="The title or summary of the event.")
    start_time: str = Field(description="Start time (e.g., '2025-07-10 14:00').")
    end_time: str = Field(description="End time (e.g., '2025-07-10 15:00').")
    attendees: Optional[list[str]] = Field(default=None, description="List of attendee emails.")

class CreateCalendarEventTool(BaseTool):
    name = "create_calendar_event"
    description = "Create a Google Calendar event with summary, start and end time."
    args_schema: Type[BaseModel] = CreateEventInput

    def _run(self, summary: str, start_time: str, end_time: str, attendees: Optional[list[str]] = None):
        try:
            service = get_calendar_service()
            local_tz = ZoneInfo("Asia/Kolkata")

            start = parse(start_time, ignoretz=True).replace(tzinfo=local_tz)
            end = parse(end_time, ignoretz=True).replace(tzinfo=local_tz)

            event = {
                'summary': summary,
                'start': {'dateTime': start.isoformat(), 'timeZone': str(local_tz)},
                'end': {'dateTime': end.isoformat(), 'timeZone': str(local_tz)},
            }
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]

            created = service.events().insert(calendarId='primary', body=event).execute()
            return f"✅ Event created successfully: [View Event]({created.get('htmlLink')})"
        except Exception as e:
            return f"❌ Failed to create event: {e}"

# Dummy summary tool
class SummarizeMeetingTool(BaseTool):
    name = "summarize_last_meeting"
    description = "Get a summary of the most recent meeting (dummy response)."
    args_schema: Type[BaseModel] = CreateEventInput

    def _run(self, *args, **kwargs):
        return "Last meeting discussed budget allocation and feature deadlines."

# --- LangChain LLM Function ---
def parse_task(prompt):
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.3)
    response = llm.invoke(prompt)
    return response.content

# --- Streamlit Frontend ---
def main():
    st.set_page_config(page_title="📅 Calendar AI Assistant", page_icon="🧠")
    st.title("📅 Calendar AI Assistant")

    if not os.path.exists("credentials.json"):
        st.error("❌ Missing credentials.json! Please download from Google Cloud Console.")
        return

    user_input = st.text_input("What would you like to do?", placeholder="e.g., Schedule a call with Aayush tomorrow at 5pm")

    if st.button("Submit") and user_input:
        with st.spinner("🧠 Parsing your input..."):
            try:
                prompt = f"""Extract the following from this input: {user_input}
Return in this format (exactly):
Title: <event_title>, Start: YYYY-MM-DD HH:MM, End: YYYY-MM-DD HH:MM
"""
                parsed = parse_task(prompt)
                st.code(parsed, language="markdown")

                # --- Robust Parsing Logic ---
                title_match = re.search(r'Title\s*:\s*(.*?)(,|$)', parsed)
                start_match = re.search(r'Start\s*:\s*([\d\-:\s]+)', parsed)
                end_match = re.search(r'End\s*:\s*([\d\-:\s]+)', parsed)

                if title_match and start_match and end_match:
                    summary = title_match.group(1).strip()
                    start_time = start_match.group(1).strip()
                    end_time = end_match.group(1).strip()

                    tool = CreateCalendarEventTool()
                    result = tool._run(summary, start_time, end_time)
                    st.success(result)
                else:
                    st.error("❌ Could not parse the output correctly. Try rephrasing.")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {e}")

if __name__ == '__main__':
    main()

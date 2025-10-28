# imports 
import logging

import streamlit as st

def validate_form():
    st.session_state.event_date
def validate_time():
    pass

# setup logging
logging.basicConfig(level=logging.INFO)

# setup page
st.set_page_config(page_title="Late Event Calculator", page_icon=":calendar:")

# setup form
st.title("Late Event Calculator!")
show_time_input = st.toggle("Time Dropdown")
valid = True
with st.form("Late Event Form", enter_to_submit=False):
    submitted_date = st.date_input("Date Submitted")
    submitted_time = st.time_input("Time Submitted", None) if show_time_input else st.text_input("Time Submitted", placeholder="3:00 pm")
    event_date = st.date_input("Date of Event")
    event_time = st.time_input("Time of Event", None) if show_time_input else st.text_input("Time of Event",placeholder="3:00 pm")
    num_holidays = st.number_input("Number of Holidays", 0, 
                                   help="Number of days that should not be counted as business days")
    submitted = st.form_submit_button("Calculate", disabled=valid)
    
if submitted:
    pass
        
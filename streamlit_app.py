# imports 
import logging
from datetime import datetime, timedelta, time

import streamlit as st

def validate_form():
    global valid, submitted_date, submitted_time, event_date, event_time, event_end_time, num_closed, form_error
    format_string = "%I:%M %p"
    logging.debug("validate_form called with: submitted_date=%s submitted_time=%s event_date=%s event_time=%s num_holidays=%s",
                  submitted_date, submitted_time, event_date, event_time, num_closed)

    if (not submitted_date or not submitted_time
            or not event_date or not event_time):
        valid = False
        form_error = "Please fill out all fields."
        logging.warning("Validation failed: missing fields - %s", form_error)
        return
    elif submitted_date >= event_date:
        valid = False
        form_error = "Submitted date is before event date." if submitted_date != event_date else "Why even check at this point!"
        logging.warning("Validation failed: date order - submitted_date=%s event_date=%s", submitted_date, event_date)
        return
    elif num_closed < 0:
        valid = False
        form_error = "Number of holidays cannot be negative."
        logging.warning("Validation failed: negative holidays - %s", num_closed)
        return
    else:
        backup_submitted_time = submitted_time
        backup_event_time = event_time
        backup_event_end_time = event_end_time
        try:
            if isinstance(submitted_time, str) and isinstance(event_time, str):
                logging.debug("Parsing string times using format %s", format_string)
                submitted_time = datetime.strptime(submitted_time, format_string)
                event_time = datetime.strptime(event_time, format_string)
                logging.debug("Parsed times -> submitted_time=%s event_time=%s", submitted_time, event_time)
        except ValueError as e:
            submitted_time = backup_submitted_time
            event_time = backup_event_time
            valid = False
            form_error = "Invalid time format. Please use HH:MM AM/PM."
            logging.error("Time parsing failed: %s; restored backups.", e)
            return
        if event_end_time:
            try:
                if isinstance(event_end_time, str):
                    logging.debug("Parsing string times using format %s", format_string)
                    event_end_time = datetime.strptime(event_end_time, format_string)
                    logging.debug("Parsed times -> event_end_time=%s", event_end_time)
            except ValueError as e:
                event_end_time = backup_event_end_time
                valid = False
                form_error = "Invalid time format. Please use HH:MM AM/PM."
                logging.error("Time parsing failed: %s; restored backups.", e)
                return
    form_error = None
    valid = True
    logging.info("Validation succeeded: valid=%s", valid)
    
def is_late():
    # Use globals set by validate_form / the form
    global submitted_date, submitted_time, event_date, event_time, num_closed

    def to_time_obj(t):
        """Normalize t to a datetime.time object. Return None on parse failure."""
        if t is None:
            logging.debug("No time provided")
            return None
        if isinstance(t, datetime):
            logging.debug("Converting datetime to time: %s", t)
            return t.time()
        if isinstance(t, str):
            try:
                logging.debug("Parsing time string: %s", t)
                return datetime.strptime(t, "%I:%M %p").time()
            except ValueError:
                logging.error("Failed to parse time string: %s", t)
                return None
        if not isinstance(t, time):
            logging.error("Unexpected type for time: %s", type(t))
            return None
        return t

    def next_business_day(d):
        d = d + timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d

    def business_days_between_exclusive(start_date, end_date):
        """Count business days between start_date (exclusive) and end_date (inclusive)."""
        if end_date <= start_date:
            return 0
        total_days = (end_date - start_date).days
        days = 0
        for offset in range(1, total_days + 1):
            d = start_date + timedelta(days=offset)
            if d.weekday() < 5:
                days += 1
        return days

    s_time = to_time_obj(submitted_time)
    e_time = to_time_obj(event_time)
    e_end_time = to_time_obj(event_end_time)

    # Determine effective submission date: if submitted after 5:00 PM or submitted time > event time,
    # treat it as if submitted the next business day.
    effective_sub_date = submitted_date
    business_close = time(17, 0)
    if s_time is not None:
        if s_time > business_close:
            logging.debug("Submitted after business hours (%s): shifting to next business day", business_close)
            effective_sub_date = next_business_day(effective_sub_date)
        elif e_time is not None and s_time > e_time:
            logging.debug("Submitted time (%s) is after event time (%s): shifting to next business day", s_time, e_time)
            effective_sub_date = next_business_day(effective_sub_date)

    # Build full datetimes for display/logging (fallback to midnight if time missing)
    submitted_dt = datetime.combine(submitted_date, s_time or datetime.min.time())
    event_dt = datetime.combine(event_date, e_time or datetime.min.time())
    event_end_dt = datetime.combine(event_date, e_end_time or datetime.min.time())

    # Count business days between effective_submission_date (exclusive) and event_date (inclusive)
    business_days = business_days_between_exclusive(effective_sub_date, event_date)

    holidays = int(num_closed) if num_closed else 0
    effective_business = max(0, business_days - holidays)

    # Display results
    st.write(f"Effective submission date used for business-day count: {effective_sub_date.strftime('%Y-%m-%d')}")
    st.write(f"Business days between submission and event (weekdays only): {business_days}")
    if holidays:
        st.write(f"Holidays excluded: {holidays}")
    st.write(f"Effective business days available: {effective_business}")
    st.write(f"Submitted at: {submitted_dt.strftime('%m/%d %I:%M %p')}")
    st.write(f"Event start/setup is at: {event_dt.strftime('%m/%d %I:%M %p')}")
    if event_end_time:
        st.write(f"Event ends at: {event_end_dt.strftime('%m/%d %I:%M %p')}")

    # On-time threshold
    required_business_days = 14

    if effective_business < required_business_days:
        st.error("Event is late", icon=":material/close:")
        if event_end_time:
            st.badge(f"Estimated charge: ${estimate_charge(event_time, event_end_time)}", icon="💰", color="orange")
        logging.info("Late: %s effective business days (required %s)", effective_business, required_business_days)
        # Find the latest submission datetime that would have been on time.
        # Allowed latest time on a candidate date is the lesser of 5:00 PM and event_time (if provided),
        # because submitting after either will push to next business day.
        allowed_time_floor = business_close
        if e_time is not None:
            # allowed latest is the earlier of 17:00 and event_time (inclusive)
            allowed_latest_time = min(business_close, e_time)
        else:
            allowed_latest_time = business_close

        latest_allowed_dt = None
        # Search backward up to 365 days for a latest acceptable submission datetime
        for days_back in range(0, 366):
            candidate_date = event_date - timedelta(days=days_back)
            # candidate_date must be a calendar date on which a submission could be made (any day),
            # but when counting business days the effective date will be adjusted.
            # We'll simulate submitting at the allowed_latest_time on that candidate_date.
            candidate_submit_time = allowed_latest_time
            # simulate effective submission date for this candidate
            candidate_effective_date = candidate_date
            if candidate_submit_time > business_close:
                candidate_effective_date = next_business_day(candidate_effective_date)
            elif e_time is not None and candidate_submit_time > e_time:
                candidate_effective_date = next_business_day(candidate_effective_date)

            candidate_business_days = business_days_between_exclusive(candidate_effective_date, event_date)
            candidate_effective_business = max(0, candidate_business_days - holidays)

            if candidate_effective_business >= required_business_days:
                latest_allowed_dt = datetime.combine(candidate_date, candidate_submit_time)
                break

        if latest_allowed_dt:
            # compute how much earlier the user needed to submit
            actual_dt = submitted_dt
            if actual_dt > latest_allowed_dt:
                delta = actual_dt - latest_allowed_dt
                days = delta.days
                hours, rem = divmod(delta.seconds, 3600)
                minutes = rem // 60
                st.write(f"Latest allowed submission to be on time: {latest_allowed_dt.strftime('%m/%d %I:%M %p')}")
                st.write(f"Would have needed to be submitted {days} days, {hours} hours, and {minutes} minutes earlier.")
            else:
                # This can happen if effective_business < required due to holidays clashing; still show latest allowed
                st.write(f"Latest allowed submission to be on time: {latest_allowed_dt.strftime('%m/%d %I:%M %p')}")
                st.write("This submission time appears earlier than the calculated latest allowed datetime but other conditions (holidays or weekday boundaries) made this late.")
        else:
            st.write("Unable to find a latest acceptable submission datetime within the last year (check holidays/inputs).")

    else:
        st.success("Event is on time.", icon=":material/check:")
        logging.info("On time: %s effective business days", effective_business)
        
        
def estimate_charge(start, end):
    charge_per_hour = 200
    hours_in_event = (end - start).total_seconds() / 3600
    charge = charge_per_hour * hours_in_event
    return charge

#########

# setup logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")

# setup page
st.set_page_config(page_title="Late Event Calculator", page_icon=":calendar:")

# setup form
st.title("Late Event Calculator!")
show_time_input = st.toggle("Time Dropdown")
valid = False
clicked = False
form_error = None
with st.form("Late Event Form", enter_to_submit=False):
    submitted_date = st.date_input("Date Submitted")
    submitted_time = st.time_input("Time Submitted", None) if show_time_input else st.text_input("Time Submitted", placeholder="3:00 pm")
    event_date = st.date_input("Date of Event")
    event_time = st.time_input("Event Start/Setup Time", None, help='Enter time coverage will start (should be setup time)') if show_time_input else st.text_input("Event Start/Setup Time",placeholder="3:00 pm", help='Enter time coverage will start (should be setup time)')
    event_end_time = st.time_input("Event End Time", None, help='Optional (Will show estimated charge if included)') if show_time_input else st.text_input("Event End Time",placeholder="3:00 pm | optional", help='Optional (Will show estimated charge if included)')
    num_closed = st.number_input("Number of Weekdays Closed", 0,
                                 help="Number of days that should not be counted as business days between submission and event dates")
    submitted = st.form_submit_button("Calculate")
    if submitted:
        validate_form()
    if form_error is not None:
        logging.debug("Showing form error: %s", form_error)
        st.badge(form_error, icon=":material/warning:", color="red" )
    
if valid and submitted:
    is_late()
    
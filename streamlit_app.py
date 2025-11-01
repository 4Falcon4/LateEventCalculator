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

    # ============================================
    # DISPLAY RESULTS WITH VISUAL STYLING
    # ============================================

    # Add a divider for visual separation
    st.divider()

    # Create a header for the results section
    st.markdown("### 📊 Calculation Results")

    # Display key information in an attractive format
    # Using columns to create a nice layout
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📅 Submission Info**")
        st.info(f"**Submitted at:**\n\n{submitted_dt.strftime('%m/%d %I:%M %p')}")
        st.info(f"**Effective submission date:**\n\n{effective_sub_date.strftime('%Y-%m-%d')}")

    with col2:
        st.markdown("**🎉 Event Info**")
        st.info(f"**Event start/setup:**\n\n{event_dt.strftime('%m/%d %I:%M %p')}")
        if event_end_time:
            st.info(f"**Event ends at:**\n\n{event_end_dt.strftime('%m/%d %I:%M %p')}")

    # Display business day calculation in a highlighted box
    st.markdown("**⏳ Business Days Calculation**")

    # Create metrics for better visual display
    metric_col1, metric_col2, metric_col3 = st.columns(3)

    with metric_col1:
        st.metric("Weekdays Between", business_days, help="Business days between submission and event (excluding weekends)")

    with metric_col2:
        st.metric("Holidays Excluded", holidays if holidays else 0, help="Number of holidays to exclude from calculation")

    with metric_col3:
        st.metric("Effective Business Days", effective_business, help="Final count after excluding holidays")

    # On-time threshold
    required_business_days = 14

    # ============================================
    # DISPLAY ON-TIME OR LATE STATUS
    # ============================================
    st.divider()

    if effective_business < required_business_days:
        # Event is LATE - show error message with visual emphasis
        st.error("❌ **EVENT IS LATE**", icon=":material/close:")

        # Show estimated charge if event end time is provided
        if event_end_time:
            charge = estimate_charge(event_time, event_end_time)
            st.warning(f"💰 **Estimated Late Fee: ${charge:.2f}**")

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

        # Display information about when it should have been submitted
        if latest_allowed_dt:
            # Create an expandable section for additional details
            with st.expander("📋 **See Details: When Should This Have Been Submitted?**", expanded=True):
                # compute how much earlier the user needed to submit
                actual_dt = submitted_dt
                if actual_dt > latest_allowed_dt:
                    delta = actual_dt - latest_allowed_dt
                    days = delta.days
                    hours, rem = divmod(delta.seconds, 3600)
                    minutes = rem // 60

                    # Show the latest allowed time prominently
                    st.markdown(f"**⏰ Latest Allowed Submission:**")
                    st.success(f"{latest_allowed_dt.strftime('%m/%d %I:%M %p')}")

                    # Show how much earlier it needed to be submitted
                    st.markdown(f"**⏪ How Much Earlier Needed:**")
                    st.info(f"**{days}** days, **{hours}** hours, and **{minutes}** minutes earlier")
                else:
                    # This can happen if effective_business < required due to holidays clashing
                    st.markdown(f"**⏰ Latest Allowed Submission:**")
                    st.success(f"{latest_allowed_dt.strftime('%m/%d %I:%M %p')}")
                    st.warning("⚠️ This submission time appears earlier than the calculated latest allowed datetime, but other conditions (holidays or weekday boundaries) made this late.")
        else:
            st.warning("⚠️ Unable to find a latest acceptable submission datetime within the last year (check holidays/inputs).")

    else:
        # Event is ON TIME - celebrate with a success message!
        st.success("✅ **EVENT IS ON TIME!**", icon=":material/check:")

        # Show a congratulatory balloon animation (optional, comment out if you don't want it)
        st.balloons()

        # Display a nice message
        st.markdown("### 🎉 Congratulations!")
        st.info(f"You submitted this event with **{effective_business}** business days notice, which exceeds the required **{required_business_days}** days. Great planning!")

        logging.info("On time: %s effective business days", effective_business)
        
        
def estimate_charge(start, end):
    charge_per_hour = 200
    hours_in_event = (end - start).total_seconds() / 3600
    charge = charge_per_hour * hours_in_event
    return charge

#########

# setup logging
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")

# setup page configuration - this must be the first Streamlit command
st.set_page_config(
    page_title="Late Event Calculator",
    page_icon="📅",
    layout="wide",  # Use wide layout for better spacing
    initial_sidebar_state="collapsed"  # Keep sidebar collapsed for cleaner look
)

# ============================================
# CUSTOM CSS STYLING
# ============================================
# This section adds custom CSS to make the app look cooler
# We use st.markdown with unsafe_allow_html=True to inject CSS

st.markdown("""
    <style>
    /* ============================================
       THEME-AWARE STYLING
       These styles change based on user's theme preference (light/dark)
       ============================================ */

    /* LIGHT MODE STYLES (Default)
       These styles apply when user has light mode enabled */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        background-attachment: fixed;
    }

    /* Alternative light mode backgrounds you can try (uncomment to use):

    /* Calm blue gradient */
    /* background: linear-gradient(135deg, #3a7bd5 0%, #00d2ff 100%); */

    /* Sunset colors */
    /* background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); */

    /* Green nature */
    /* background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%); */
    */

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 900px;
        background-color: rgba(255, 255, 255, 0.95);  /* White with slight transparency */
        border-radius: 20px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
    }

    h1 {
        color: #667eea;  /* Light mode: bright purple */
        text-align: center;
        font-size: 3rem !important;
        margin-bottom: 1rem;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
    }

    h2, h3 {
        color: #764ba2;  /* Light mode: darker purple */
    }

    /* DARK MODE STYLES
       These styles apply when user has dark mode enabled
       Uses CSS media query to detect system preference */
    @media (prefers-color-scheme: dark) {
        /* Dark mode background - darker gradient for better contrast */
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            background-attachment: fixed;
        }

        /* Alternative dark mode backgrounds (uncomment to try):

        /* Dark purple */
        /* background: linear-gradient(135deg, #2d1b69 0%, #1a0933 100%); */

        /* Dark blue-gray */
        /* background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%); */

        /* Dark teal */
        /* background: linear-gradient(135deg, #134e5e 0%, #71b280 100%); */
        */

        /* Dark mode content card - darker with blue tint */
        .main .block-container {
            background-color: rgba(30, 30, 50, 0.95);  /* Dark blue-gray background */
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);  /* Stronger shadow */
            border: 1px solid rgba(100, 150, 255, 0.2);  /* Subtle blue border */
        }

        /* Dark mode headers - lighter colors for visibility */
        h1 {
            color: #8fa3ff;  /* Lighter blue-purple for dark mode */
            text-shadow: 2px 2px 8px rgba(0, 0, 0, 0.5);
        }

        h2, h3 {
            color: #a89fff;  /* Light purple for dark mode */
        }

        /* Dark mode text color for better readability */
        p, label, span, div {
            color: #e0e0e0 !important;
        }
    }

    /* ============================================
       FORM STYLING (applies to both themes)
       ============================================ */

    /* Style the form container - LIGHT MODE */
    .stForm {
        background-color: rgba(102, 126, 234, 0.05);  /* Light purple tint */
        padding: 2rem;
        border-radius: 15px;
        border: 2px solid rgba(102, 126, 234, 0.3);
    }

    /* Style input fields - LIGHT MODE */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {
        border-radius: 10px;
        border: 2px solid #667eea;
        background-color: white;
    }

    /* Style buttons - LIGHT MODE */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 2rem;
        font-size: 1.1rem;
        font-weight: bold;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
        width: 100%;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }

    /* Style the toggle switch - LIGHT MODE */
    .stCheckbox {
        background-color: rgba(255, 255, 255, 0.8);
        padding: 0.5rem;
        border-radius: 8px;
    }

    /* DARK MODE - Form Elements */
    @media (prefers-color-scheme: dark) {
        /* Dark mode form container */
        .stForm {
            background-color: rgba(100, 150, 255, 0.08);  /* Subtle blue glow */
            border: 2px solid rgba(100, 150, 255, 0.3);
        }

        /* Dark mode input fields */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stDateInput > div > div > input,
        .stTimeInput > div > div > input {
            background-color: rgba(40, 40, 60, 0.8);  /* Dark input background */
            border: 2px solid #6495ff;  /* Lighter blue border */
            color: #e0e0e0;  /* Light text */
        }

        /* Dark mode buttons - brighter gradient for visibility */
        .stButton > button {
            background: linear-gradient(135deg, #5a7fff 0%, #6a5acd 100%);
            box-shadow: 0 4px 15px rgba(90, 127, 255, 0.5);
        }

        .stButton > button:hover {
            box-shadow: 0 6px 20px rgba(90, 127, 255, 0.7);
        }

        /* Dark mode toggle */
        .stCheckbox {
            background-color: rgba(60, 60, 80, 0.6);
        }
    }

    /* Add decorative emoji header */
    .emoji-header {
        text-align: center;
        font-size: 4rem;
        margin-bottom: 0;
    }

    /* Style for result containers */
    div[data-testid="stMarkdownContainer"] > p {
        font-size: 1.1rem;
        line-height: 1.8;
    }

    /* Style badges */
    .stBadge {
        font-size: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================
# APP HEADER
# ============================================
# Add a decorative emoji at the top
st.markdown('<div class="emoji-header">📅⏰</div>', unsafe_allow_html=True)

# Main title
st.title("Late Event Calculator!")

# Add a subtitle with description
st.markdown("""
    <p style='text-align: center; color: #666; font-size: 1.2rem; margin-bottom: 2rem;'>
    Calculate if your event submission is on time based on business days
    </p>
""", unsafe_allow_html=True)

# ============================================
# FORM CONTROLS
# ============================================
# Toggle between time input methods (dropdown vs text input)
show_time_input = st.toggle("🕐 Use Time Dropdown (vs Text Input)", help="Toggle between dropdown time picker and text input")
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

# ============================================
# FOOTER WITH HELPFUL INFORMATION
# ============================================
# Add some spacing before the footer
st.markdown("<br><br>", unsafe_allow_html=True)

# Add a footer with helpful information
st.divider()
st.markdown("""
    <div style='text-align: center; color: #666; padding: 1rem;'>
    <p style='margin: 0;'>💡 <strong>Tip:</strong> Business days exclude weekends and holidays you specify.</p>
    <p style='margin: 0; font-size: 0.9rem;'>Submissions after 5:00 PM count as next business day.</p>
    </div>
""", unsafe_allow_html=True)

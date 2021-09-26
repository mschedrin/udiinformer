import tempfile, time
from calendar import monthrange

import dateparser
import datetime
import playwright
#import playwright.helper
import playwright.sync_api
import telegram_send
#from playwright import sync_playwright
from playwright.sync_api import sync_playwright
from pydantic import BaseSettings, SecretStr

class Settings(BaseSettings):
    EMAIL: str
    PWD: SecretStr

    class Config:
        env_prefix = "UDI_"
        env_file = ".env"
        env_file_encoding = "utf-8"


def send_success(page: playwright.sync_api.Page, msg: str):
    telegram_send.send(messages=[msg])
    with tempfile.TemporaryFile("r+b") as fp:
        encoded_img = page.screenshot(type="png")
        fp.write(encoded_img)
        fp.seek(0, 0)
        telegram_send.send(images=[fp])


def main():
    config = Settings()
    with sync_playwright() as p:
        # browser = p.chromium.launch(headless=False)
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        #page = browser.newPage()
        page.goto("https://selfservice.udi.no/en-gb/")
        # click on log in button
        page.click("#ctl00_BodyRegion_PageRegion_MainRegion_LogInHeading")

        page.type("input[type=email]", config.EMAIL)
        page.type("input[type=password]", config.PWD.get_secret_value())
        page.click("#next")

        try:
            book_btn_id: str = "#ctl00_BodyRegion_PageRegion_MainRegion_IconNavigationTile2_heading"
            page.wait_for_selector(book_btn_id)
            

            # book appointment
            page.click(book_btn_id)
        except Exception as e:
            print(str(e))
            msg = "Failed to login. Check your password."
            print(msg)
            telegram_send.send(messages=[msg])
            return

        # click on the first one in the list
        page.click(
            "#ctl00_BodyRegion_PageRegion_MainRegion_ApplicationOverview_applicationOverviewListView_ctrl0_btnBookAppointment"
        )

        change_btn_id = "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_BookingSummaryInfo_btnChangeBooking"
        try:
            page.wait_for_selector(change_btn_id, timeout=5000)
        except playwright.helper.TimeoutError:
            print("No appointments to rebook.")
            return

        current_booking_id = "#ctl00_PageRegion_MainContentRegion_ViewControl_spnReceiptAndBooking_BookingSummaryInfo_lblDate"
        current_booking = page.text_content(current_booking_id)
        current_booking = dateparser.parse(current_booking)
        #current_booking = dateparser.parse("Wednesday 1 September 2022")
        page.click(change_btn_id)
        #page.waitForNavigation(waitUntil='load')
        # page.wait_for_load_state('networkidle')
        page.wait_for_load_state()
        page.wait_for_load_state(state = "domcontentloaded")
        time.sleep(3)
        # button to go to the next month
        next_btn_id = "#ctl00_BodyRegion_PageRegion_MainRegion_appointmentReservation_appointmentCalendar_btnNext"

        # initialize view_month to be just slightly less than the current booking
        view_month = current_booking - (current_booking - dateparser.parse("1 day"))
        # success flag 
        success = False
        # iterate over months trying to find available appointments
        while current_booking > view_month:
            # page.click(change_btn_id)
            # page.wait_for_load_state()
            view_month_txt = page.query_selector("h2").inner_text()
            view_month = dateparser.parse(view_month_txt)
            print(f"Checking { view_month_txt }")

            #num_closed = len(page.querySelectorAll('css=[class="bookingCalendarClosedDay"]'))
            # num_closed = len(page.querySelectorAll('css=[class="bookingCalendarClosedDay"]')) + len(page.querySelectorAll('css=[class="bookingCalendarFullyBookedDay"]'))
            # num_days_in_month = monthrange(view_month.year, view_month.month)[1]
            # if num_days_in_month == num_closed:
            #     print("Reached a fully closed month.")
            #     #break
            #     page.click(next_btn_id)
            #     page.waitForNavigation()
            #     continue

            bookable = []
            for class_id in [".bookingCalendarHalfBookedDay", ".bookingCalendarBookableDay", ".bookingCalendarBookedDay"]:
                #bookable.extend(page.querySelectorAll(class_id))
                bookable.extend(page.query_selector_all(class_id))

            if bookable:
                bookable = sorted(bookable, key=lambda x: int(x.inner_text().split()[0]))
                bookable_day = int(bookable[0].inner_text().split()[0])
                bookable_date = datetime.datetime(view_month.year,view_month.month,bookable_day)
                if bookable_date < current_booking:
                    msg = f"It is possible to rebook the appointment on {bookable_day}, {view_month_txt}!"
                    send_success(page, msg)
                    break

            page.click(next_btn_id)
            #page.waitForNavigation(waitUntil='load')
            page.wait_for_load_state()
            # page.wait_for_load_state('networkidle')
            page.wait_for_load_state(state = "domcontentloaded")
            time.sleep(3)
            
        if not success: print("No possibilities to rebook.")


if __name__ == "__main__":
    main()

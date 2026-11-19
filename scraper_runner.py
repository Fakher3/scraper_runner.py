import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://aggrega-mqeq.bolt.host"
MAX_WAIT_SECONDS = 180   # أقصى وقت انتظار (3 دقائق)
POLL_INTERVAL = 5        # فحص السجل كل 5 ثوانٍ
HEADLESS = True          # اجعلها False إذا أردت رؤية المتصفح أمامك


def get_logs_text(page) -> str:
    """محاولة قراءة محتوى LIVE LOG أو آخر نصوص الصفحة."""
    selectors = [
        "text=LIVE LOG",
        "[class*='log']",
        "[id*='log']",
        "pre",
        "code",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0:
                txt = loc.inner_text(timeout=1500).strip()
                if len(txt) > 20:
                    return txt
        except Exception:
            pass

    body = page.inner_text("body")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return "\n".join(lines[-20:])


def run_scraper():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"[INFO] فتح الصفحة: {URL}")
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # البحث عن زر Scrape Now والضغط عليه
        btn = page.get_by_role("button", name="Scrape Now")
        if btn.count() == 0:
            btn = page.locator("button:has-text('Scrape Now')").first

        btn.wait_for(state="visible", timeout=20000)
        print("[INFO] تم الضغط على زر Scrape Now...")
        btn.click()

        elapsed = 0
        last_snapshot = ""
        stale_seconds = 0

        while elapsed < MAX_WAIT_SECONDS:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            current_logs = get_logs_text(page)
            lower_logs = current_logs.lower()

            if current_logs != last_snapshot:
                last_snapshot = current_logs
                stale_seconds = 0
                tail_lines = " | ".join(
                    [l.strip() for l in current_logs.splitlines() if l.strip()][-3:]
                )
                print(f"[{elapsed}s] تحديث: {tail_lines}")
            else:
                stale_seconds += POLL_INTERVAL

            # علامات انتهاء أو فشل العملية
            done_keywords = [
                "sync complete",
                "completed",
                "finished",
                "saved ",
                "done in",
            ]
            fatal_keywords = [
                "quota exceeded",
                "api key",
                "unauthorized",
                "401",
                "403",
            ]

            if any(k in lower_logs for k in done_keywords):
                print("[SUCCESS] يبدو أن عملية السحب اكتملت.")
                break

            if any(k in lower_logs for k in fatal_keywords):
                print("[ERROR] ظهر خطأ يمنع الاستمرار في السجل.")
                break

            # إذا لم يتغير السجل لمدة 45 ثانية بعد بدء العمل
            if elapsed >= 30 and stale_seconds >= 45:
                print("[WARN] توقف تحديث السجل لفترة؛ إنهاء الجلسة لتجنب التعليق.")
                break

        else:
            print("[WARN] انتهت مهلة الانتظار القصوى.")

        browser.close()
        print("[INFO] تم إغلاق المتصفح.")


if __name__ == "__main__":
    try:
        run_scraper()
    except PlaywrightTimeoutError as e:
        print(f"[TIMEOUT] انتهت مهلة التحميل أو العثور على العنصر: {e}")
    except Exception as e:
        print(f"[FATAL] حدث خطأ غير متوقع: {e}")

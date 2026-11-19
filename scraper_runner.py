import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://aggrega-mqeq.bolt.host"
MAX_WAIT_SECONDS = 210   # أقصى وقت انتظار بعد الضغط (3.5 دقائق)
POLL_INTERVAL = 5        # فحص السجل كل 5 ثوانٍ
HEADLESS = True


def get_logs_text(page) -> str:
    """قراءة محتوى LIVE LOG أو آخر نصوص الصفحة."""
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
                txt = loc.inner_text(timeout=2000).strip()
                if len(txt) > 20:
                    return txt
        except Exception:
            pass

    body = page.inner_text("body")
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return "\n".join(lines[-25:])


def run_scraper():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
        )
        page = context.new_page()

        print(f"[INFO] فتح الصفحة: {URL}")
        try:
            page.goto(URL, wait_until="networkidle", timeout=90000)
        except PlaywrightTimeoutError:
            print("[WARN] انتهى وقت networkidle، محاولة المتابعة بعد تحميل domcontentloaded...")
            page.goto(URL, wait_until="domcontentloaded", timeout=90000)

        page.wait_for_timeout(5000)

        # البحث عن زر Scrape Now والانتظار حتى يصبح ظاهراً
        btn = page.get_by_role("button", name="Scrape Now").first
        try:
            btn.wait_for(state="visible", timeout=45000)
        except PlaywrightTimeoutError:
            btn = page.locator("button:has-text('Scrape')").first
            try:
                btn.wait_for(state="visible", timeout=20000)
            except PlaywrightTimeoutError:
                buttons_text = []
                try:
                    buttons_text = page.locator("button").all_inner_texts()
                except Exception:
                    pass
                print(f"[DEBUG] لم يظهر زر Scrape Now. الأزرار الموجودة: {buttons_text}")
                sample_lines = [
                    l.strip() for l in page.inner_text("body").splitlines() if l.strip()
                ][:15]
                print(f"[DEBUG] أول سطور من الصفحة: {' | '.join(sample_lines)}")
                browser.close()
                raise

        btn.scroll_into_view_if_needed()
        print("[INFO] تم العثور على الزر، جارٍ الضغط على Scrape Now...")
        btn.click(force=True)

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
                    [l.strip() for l in current_logs.splitlines() if l.strip()][-4:]
                )
                print(f"[{elapsed}s] تحديث: {tail_lines}")
            else:
                stale_seconds += POLL_INTERVAL

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
                print("[SUCCESS] اكتملت عملية السحب.")
                break

            if any(k in lower_logs for k in fatal_keywords):
                print("[ERROR] ظهر خطأ يمنع الاستمرار في السجل.")
                break

            # إذا توقف السجل عن التغير لمدة 60 ثانية بعد بدء التشغيل
            if elapsed >= 35 and stale_seconds >= 60:
                print("[WARN] لم يتغير السجل لمدة 60 ثانية؛ إنهاء الجلسة.")
                break
        else:
            print("[WARN] انتهت مهلة الانتظار القصوى.")

        browser.close()
        print("[INFO] تم إغلاق المتصفح.")


if __name__ == "__main__":
    try:
        run_scraper()
    except PlaywrightTimeoutError as e:
        print(f"[TIMEOUT] انتهت مهلة الانتظار: {e}")
        raise
    except Exception as e:
        print(f"[FATAL] حدث خطأ: {e}")
        raise

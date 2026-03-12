import undetected_chromedriver as uc
import time
import os
import ctypes
import sys
 
FIRST_RUN_CHECKED = False
 
def _cleanup_profile(profile_path):
    import shutil
 
    # Lock-файлы — если браузер упал, они блокируют следующий запуск
    for lock_file in ["lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"]:
        path = os.path.join(profile_path, lock_file)
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
 
    cache_dirs = [
        "Default/Cache",
        "Default/Code Cache",
        "Default/GPUCache",
        "GrShaderCache",
        "ShaderCache",
        "Default/Service Worker/CacheStorage",
    ]
    for d in cache_dirs:
        path = os.path.join(profile_path, d)
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except:
                pass

def safe_get(driver, url, retries=3):
    """Открывает страницу с повторными попытками при таймауте рендерера."""
    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            return True
        except Exception as e:
            if "Timed out receiving message from renderer" in str(e) or "timeout" in str(e).lower():
                print(f"Таймаут загрузки страницы (попытка {attempt}/{retries}), повторяю")
                time.sleep(3)
            else:
                raise
    print(f"Страница не загрузилась после {retries} попыток: {url}")
    return False

def wait_for_element(driver, js_check, timeout=15, poll=0.5):
    """Ждёт появления элемента. js_check должен возвращать элемент или null."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = driver.execute_script(js_check)
        if result:
            return result
        time.sleep(poll)
    return None

def get_files_snapshot(download_path):
    """Возвращает множество завершённых файлов в папке (без .crdownload/.tmp)."""
    try:
        return set(
            f for f in os.listdir(download_path)
            if not f.endswith('.crdownload') and not f.endswith('.tmp')
        )
    except:
        return set()

def wait_for_completion(download_path, snapshot_before, timeout=3600):
    print("Жду начала скачивания")
    deadline_start = time.time() + 30
    started = False
 
    while time.time() < deadline_start:
        try:
            all_files = set(os.listdir(download_path))
            in_progress = any(f.endswith('.crdownload') or f.endswith('.tmp') for f in all_files)
            finished = get_files_snapshot(download_path)
            new_finished = finished - snapshot_before
 
            if in_progress:
                started = True
                print("Скачивание идёт")
                break
            elif new_finished:
                print(f"Файл уже готов (скачался мгновенно): {new_finished}")
                return True
        except:
            pass
        time.sleep(1)
 
    if not started:
        print("Скачивание не началось за 30 секунд")
        return False

    # Ждём завершения
    print("Жду завершения скачивания")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            all_files = set(os.listdir(download_path))
            in_progress = any(f.endswith('.crdownload') or f.endswith('.tmp') for f in all_files)
            if not in_progress:
                new_finished = get_files_snapshot(download_path) - snapshot_before
                if new_finished:
                    print(f"Скачивание завершено: {new_finished}")
                    return True
        except:
            pass
        time.sleep(2)
        
    print("Таймаут ожидания скачивания")
    return False

def do_slow_download(driver, download_path, snapshot_before):
    """Нажимает Slow Download через Shadow DOM и ждёт завершения."""
 
    print("Ожидаю страницу Slow Download")
    time.sleep(8)
 
    host_found = wait_for_element(driver, """
        return document.querySelector('mod-file-download') || null;
    """, timeout=20)
 
    if not host_found:
        print("Элемент mod-file-download не найден")
        return False
 
    success = driver.execute_script("""
        const host = document.querySelector('mod-file-download');
        if (!host) return false;
        host.dispatchEvent(new CustomEvent('slowDownload'));
        if (host.shadowRoot) {
            const btn = host.shadowRoot.querySelector('button, .btn-slow');
            if (btn) { btn.click(); return true; }
        }
        return false;
    """)
 
    if not success:
        print("Кнопка Slow Download не найдена в Shadow DOM")
        return False
 
    print("Slow Download нажат")
    time.sleep(8)
    return wait_for_completion(download_path, snapshot_before)

def download_with_selenium(url, download_path):
    global FIRST_RUN_CHECKED
    driver = None
 
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
 
    profile_path = os.path.join(base_dir, "nexus_bot_profile")
    abs_download_path = os.path.join(base_dir, download_path)
 
    if not os.path.exists(abs_download_path):
        os.makedirs(abs_download_path)
    if not os.path.exists(profile_path):
        os.makedirs(profile_path)
 
    # Чистим мусор профиля перед каждым запуском
    _cleanup_profile(profile_path)
 
    try:
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir={profile_path}')
        options.add_argument('--start-minimized')
        prefs = {
            "download.default_directory": abs_download_path,
            "download.prompt_for_download": False,
            "profile.default_content_settings.popups": 0,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)
 
        driver = uc.Chrome(options=options, version_main=145)
        driver.minimize_window()
        driver.set_page_load_timeout(60)
 
        time.sleep(2)
 
        # Разрешаем все загрузки через CDP — без отключения Safe Browsing
        driver.execute_cdp_cmd("Browser.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": abs_download_path,
            "eventsEnabled": True
        })
 
        snapshot_before = get_files_snapshot(abs_download_path)
 
        # Авторизация 
        print(f"Открываю: {url}")
        safe_get(driver, url)
        wait_for_element(driver, "return document.readyState === 'complete' ? true : null", timeout=20)
        time.sleep(3)
 
        if not FIRST_RUN_CHECKED:
            is_logged = driver.execute_script("""
                return !!(document.querySelector('a[href*="logout"]') ||
                          document.querySelector('.nav-user-username') ||
                          document.querySelector('.member-name') ||
                          document.querySelector('a[href*="sign_out"]'));
            """)
 
            if not is_logged:
                driver.set_window_position(0, 0)
                driver.maximize_window()
                ctypes.windll.user32.MessageBoxW(0, "Войдите в аккаунт и нажмите ОК.", "Авторизация", 0x40 | 0x1)
                driver.minimize_window()
                safe_get(driver, url)
                wait_for_element(driver, "return document.readyState === 'complete' ? true : null", timeout=20)
                time.sleep(3)
            else:
                print("Авторизация подтверждена")
            FIRST_RUN_CHECKED = True
 
        # Определяем тип мода 
        already_on_slow = driver.execute_script("""
            return document.querySelector('mod-file-download') || null;
        """)
 
        if already_on_slow:
            print("Уже на странице Slow Download")
            result = do_slow_download(driver, abs_download_path, snapshot_before)
            if result:
                print("Файл получен")
            else:
                print("Файл не скачан")
            return
 
        # Переходим на вкладку files
        if "?tab=files" not in url and "&tab=files" not in url:
            files_url = (url + "&tab=files") if "?" in url else (url + "?tab=files")
        else:
            files_url = url
 
        if driver.current_url.rstrip('/') != files_url.rstrip('/'):
            safe_get(driver, files_url)
            wait_for_element(driver, "return document.readyState === 'complete' ? true : null", timeout=20)
            time.sleep(3)
 
        # Ищем кнопки "Manual download" на странице files
        manual_btn_popup = wait_for_element(driver, """
            return Array.from(document.querySelectorAll('a.popup-btn-ajax'))
                .find(el => el.innerText.trim().toLowerCase() === 'manual download') || null;
        """, timeout=5)
 
        manual_btn_direct = wait_for_element(driver, """
            return Array.from(document.querySelectorAll('a.btn'))
                .find(el =>
                    el.innerText.trim().toLowerCase() === 'manual download' &&
                    el.href.includes('file_id') &&
                    !el.classList.contains('popup-btn-ajax')
                ) || null;
        """, timeout=3)
 
        if manual_btn_popup:
            # мод с требованиями, открываем модалку 
            print("ТИП Б: нашёл 'Manual download' (popup), кликаю")
            driver.execute_script("arguments[0].click();", manual_btn_popup)
 
            download_btn = wait_for_element(driver, """
                const roots = [
                    '.mfp-content', '.mfp-wrap', '.popup-content',
                    '[class*="modal"]', '[class*="popup"]'
                ];
                for (const sel of roots) {
                    const root = document.querySelector(sel);
                    if (!root) continue;
                    const btn = Array.from(root.querySelectorAll('a, button'))
                        .find(el => el.innerText.trim().toLowerCase() === 'download');
                    if (btn) return btn;
                }
                return null;
            """, timeout=12)
 
            if download_btn:
                print("Нашёл 'Download' в модалке, кликаю")
                driver.execute_script("arguments[0].click();", download_btn)
            else:
                print("Модалка не появилась — продолжаю к Slow Download")
 
        elif manual_btn_direct:
            # прямая ссылка с file_id, переходим по href
            direct_href = driver.execute_script("return arguments[0].href", manual_btn_direct)
            print(f"ТИП А: нашёл прямую ссылку, перехожу: {direct_href}")
            safe_get(driver, direct_href)
            wait_for_element(driver, "return document.readyState === 'complete' ? true : null", timeout=20)
            time.sleep(3)
 
        else:
            print("Кнопка 'Manual download' не найдена ни в одном из форматов")
            return
 
        # Slow Download (общий для обоих типов) 
        result = do_slow_download(driver, abs_download_path, snapshot_before)
        if result:
            print("Файл получен")
        else:
            print("Файл не скачан")
 
    except Exception as e:
        print(f"Ошибка в nexus_api: {e}")
    finally:
        if driver:
            driver.quit()
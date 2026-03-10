import undetected_chromedriver as uc
import time
import os
import ctypes
import sys

FIRST_RUN_CHECKED = False

def wait_for_completion(download_path, timeout=3600):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            files = os.listdir(download_path)
            if any(f.endswith('.crdownload') or f.endswith('.tmp') for f in files):
                time.sleep(2)
                continue
            return True
        except:
            time.sleep(2)
    return False

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
        
    try:
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir={profile_path}')
        options.add_argument('--start-minimized')
        
        # Оставляем только базовые настройки для автоматизации загрузки
        prefs = { 
            "download.default_directory": abs_download_path,
            "download.prompt_for_download": False,
            "profile.default_content_settings.popups": 0,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
            "safebrowsing.enabled": True 
        }
        options.add_experimental_option("prefs", prefs)
        
        driver = uc.Chrome(options=options, version_main=145)
        driver.minimize_window()
        driver.set_page_load_timeout(20)
        driver.get(url)

        time.sleep(5) 
        
        target_loaded = False
        for _ in range(10):
            if "nexusmods.com" in driver.current_url:
                target_loaded = True
                break
            time.sleep(2)
        
        if not target_loaded:
            return

        # Одноразовая авторизация
        if not FIRST_RUN_CHECKED:
            is_logged = driver.execute_script("""
                return !!(document.querySelector('a[href*="logout"]') || 
                          document.querySelector('.nav-user-username') || 
                          document.querySelector('.member-name'));
            """)
            
            if not is_logged:
                driver.set_window_position(0, 0)
                driver.maximize_window()
                ctypes.windll.user32.MessageBoxW(0, "Войдите в аккаунт и нажмите ОК.", "Авторизация", 0x40 | 0x1)
                driver.set_window_position(-2000, 0)
            else:
                print("✅ Авторизация подтверждена (профиль сохранен).")
            FIRST_RUN_CHECKED = True
        
        bypassed = False
        for _ in range(5):
            bypassed = driver.execute_script("""
                const manual = Array.from(document.querySelectorAll('a, button')).find(el => el.innerText.toUpperCase().includes('MANUAL'));
                if (manual) { manual.click(); return true; }
                return false;
            """)
            if bypassed: break
            time.sleep(2)
         
        if bypassed:
            time.sleep(5)
            # Обработка окна требований или списка файлов
            bypassed = driver.execute_script("""
                const confirmBtn = document.querySelector('.mfp-content .btn, .confirm-download');
                if (confirmBtn && confirmBtn.innerText.toUpperCase().includes('DOWNLOAD')) {
                    confirmBtn.click();
                    return true;
                }
                return false;
            """)
            if not bypassed:
                driver.execute_script("""
                    const fileBtns = Array.from(document.querySelectorAll('a, button'));
                    const secondManual = fileBtns.find(el => el.innerText.toLowerCase().includes('manual download'));
                    if (secondManual) { secondManual.click(); }
                """)
            time.sleep(10)

        # Финальное скачивание через Shadow DOM
        success = driver.execute_script(""" 
            const host = document.querySelector('mod-file-download');
            if (host) {
                host.dispatchEvent(new CustomEvent('slowDownload'));
                if (host.shadowRoot) {
                    const btn = host.shadowRoot.querySelector('button, .btn-slow');
                    if (btn) btn.click();
                }
                return true;
            }
            return false;
        """)

        if success:
            time.sleep(8) 
            wait_for_completion(download_path)
            print("✅ Файл получен.")
        else:
            print("❌ Кнопка скачивания не найдена.")

    except Exception as e:
        print(f"Ошибка в nexus_api: {e}")
    finally:
        if driver:
            driver.quit()
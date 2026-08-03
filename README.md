# ⚡ eOVPN-Pro

<div align="center">
    <img src="static/window_connected_with_flag.png" alt="eOVPN-Pro" width="600">
</div>

---

**eOVPN-Pro** is an advanced, high-performance, and feature-rich OpenVPN configuration manager built with GTK4 and Libadwaita. It is a modernized and significantly upgraded version of the original client, engineered to provide unparalleled speed, visual insight, and robust connectivity features for Linux power users.

**eOVPN-Pro** یک مدیریت‌کننده پیشرفته، با کارایی بالا و مجهز برای کانفیگ‌های OpenVPN است که با GTK4 و Libadwaita طراحی شده است. این نسخه ارتقا یافته و مدرن، به طور ویژه برای ارائه سرعت بی‌نظیر، مانیتورینگ زنده ترافیک و قابلیت‌های اتصال فوق‌العاده پایدار برای کاربران حرفه‌ای لینوکس مهندسی و پیاده‌سازی شده است.

---

## ✨ Pro Features (امکانات نسخه حرفه‌ای)

- ⚡ **Concurrent TCP Speed Test (تست سرعت موازی و همزمان)**:
  - Parses all remote endpoints within `.ovpn` files and tests their socket-level latency concurrently using multi-threaded worker pools in less than 2 seconds, keeping the GUI perfectly fluid.
  - استخراج تمامی آدرس‌ها و پورت‌های مقصد از فایل‌های کانفیگ و انجام تست دست‌دهی پروتکل TCP به صورت چندنخی و کاملاً موازی در کمتر از ۲ ثانیه، بدون کوچکترین هنگ یا افت فریم در برنامه.

- 🔄 **Dynamic Latency Sorting (مرتب‌سازی داینامیک بر اساس سرعت)**:
  - Instantly sorts your VPN configuration list from lowest to highest latency, moving failed or unreachable servers to the bottom automatically.
  - مرتب‌سازی آنی لیست کانفیگ‌ها از سریع‌ترین (کمترین پینگ) به سنگین‌ترین سرورها به صورت کاملاً خودکار، و هدایت کانفیگ‌های قطع‌شده به انتهای لیست.

- 🎯 **Auto-Select Fastest (انتخاب هوشمند سریع‌ترین سرور)**:
  - Analyzes the latency of all configurations and dynamically highlights/selects the absolute fastest server in your list with a single click.
  - بررسی خودکار پینگ تمام سرورها و فوکوس/انتخاب سریع‌ترین سرور فعال در کل لیست تنها با فشردن یک کلیک جهت اتصال فوق‌سریع.

- 📊 **Real-time Bandwidth Monitor (نمایشگر زنده پهنای باند و ترافیک)**:
  - Monitors and displays real-time download speed, upload speed, and total traffic usage from `/proc/net/dev` once connected.
  - مانیتورینگ زنده و نمایش گرافیکی نرخ دانلود، آپلود و میزان کل مصرف ترافیک اینترنت کارت شبکه VPN به صورت زنده و ثانیه‌ای.

- 🔌 **Auto-Reconnect (اتصال مجدد خودکار)**:
  - Detects unexpected connection drops and automatically schedules an immediate reconnect attempt within 3 seconds to guarantee continuous privacy.
  - شناسایی هوشمند قطعی‌های ناگهانی فیلترشکن و اقدام خودکار جهت اتصال مجدد در ۳ ثانیه برای تضمین امنیت مداوم ترافیک شما.

- 📁 **Local Folder Import (وارد کردن دسته‌جمعی و پوشه‌ای کانفیگ‌ها)**:
  - Supports importing VPN configurations directly from a local folder path in addition to traditional ZIP archives.
  - امکان وارد کردن و ایمپورت مستقیم فایل‌های کانفیگ از یک پوشه در سیستم شما علاوه بر پشتیبانی از فرمت‌های سنتی آرشیو ZIP.

---

## 🛠️ Installation & Execution (نصب و اجرا)

### Option A: Run via VS Code (ساده‌ترین روش - از طریق ویژوال استودیو کد)
1. Open the project folder in **VS Code** (**File -> Open Folder**).
2. Install the **Python** and **Python Debugger** extensions in VS Code.
3. Open a terminal in VS Code (`Ctrl+``) and install the python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Simply press **F5** (or go to **Run and Debug** and click the green Play button).
   - VS Code will compile the C/C++ backend bindings and run the application natively in debug mode.

---

### Option B: Local Python Debug Script (اجرا بدون نیاز به نصب سیستمی)
You can compile and run the application locally without performing a global system install:
```bash
# 1. Install pip dependencies
pip install -r requirements.txt

# 2. Run the automated debug script
python3 run_program_debug.py
```

---

### Option C: Global System Installation (نصب دائمی روی لینوکس)
To compile and install eOVPN-Pro natively on your system (adding it to your application menus and shortcuts):

```bash
# 1. Setup the meson build system
meson setup build -Dprefix=/usr

# 2. Compile and install
sudo ninja install -C build
```

*Note: If you wish to disable OpenVPN 3 d-bus backend support, add `-Dopenvpn3=false` to the meson setup command.*

To uninstall:
```bash
sudo ninja uninstall -C build
```

---

## 💎 Project Information (مشخصات پروژه)

- **Application Name (نام برنامه)**: eOVPN-Pro
- **Application ID (شناسه برنامه)**: `com.github.mahdi-bagheban.eovpn-pro`
- **Current Version (نسخه)**: 1.4
- **Lead Developer & Publisher (توسعه‌دهنده اصلی)**: [Mahdi Bagheban](http://www.MahdiArts.ir)
- **Official Website (وب‌سایت رسمی)**: [MahdiArts](http://www.MahdiArts.ir)
- **Primary Support Mail (ایمیل پشتیبانی)**: info@MahdiArts.ir
- **Secondary Mail (ایمیل ثانویه)**: mehdi.bagheban@gmail.com

---

*یا علی مدد* 💚

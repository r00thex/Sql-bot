#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PSQLI Telegram Bot Configuration
"""

# ============================================
# 🔑 TELEGRAM BOT CONFIGURATION
# ============================================

# @BotFather থেকে আপনার বট টোকেন নিন
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# ============================================
# 👑 ADMIN CONFIGURATION
# ============================================

# অ্যাডমিন ইউজার আইডি - এরা সব কমান্ড ব্যবহার করতে পারবে
# @userinfobot থেকে আপনার আইডি নিন
ADMIN_IDS = [
    123456789,  # আপনার টেলিগ্রাম আইডি
    # 987654321,  # আরেকজন অ্যাডমিন
]

# অনুমোদিত ইউজার - খালি রাখলে সবাই ব্যবহার করতে পারবে
ALLOWED_USERS = []  # [123456789, 987654321]

# ============================================
# ⚙️ SYSTEM CONFIGURATION
# ============================================

# PSQLI স্ক্রিপ্টের পাথ
PSQLI_SCRIPT = "./psqli.sh"

# আউটপুট ডিরেক্টরি
OUTPUT_DIR = "output"
RESULT_DIR = "results"

# কমান্ড কুলডাউন (সেকেন্ড)
COOLDOWN_TIME = 5

# একসাথে কতগুলো স্ক্যান চলবে
MAX_CONCURRENT_SCANS = 3

# স্ক্যান টাইমআউট (সেকেন্ড)
SCAN_TIMEOUT = 300

# ============================================
# 🔍 DORK CONFIGURATION
# ============================================

# ডিফল্ট ডোর্ক পেজ
DEFAULT_PAGES = 3

# প্রিফাইনড ডোর্কস
PREDEFINED_DORKS = {
    "admin": "inurl:admin.php|inurl:login.php|inurl:admin/",
    "sqli": "inurl:.php?id=|inurl:index.php?id=|inurl:product.php?id=",
    "upload": "inurl:upload.php|inurl:file_upload.php",
}

# ============================================
# 📊 OUTPUT FORMATTING
# ============================================

# ফলাফল ফরম্যাটিং
MAX_RESULT_LINES = 30
MAX_ERROR_LINES = 5
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# ============================================
# 🛡️ SECURITY
# ============================================

# অনুরোধ ট্র্যাকিং
ENABLE_RATE_LIMITING = True
ENABLE_LOGGING = True

# ============================================
# 📝 LOGGING
# ============================================

LOG_FILE = "bot.log"
LOG_LEVEL = "INFO"

# 🚀 Powerful SQL Injection Testing Bot based on psqli.sh v3 MOD.


📁 ফাইল স্ট্রাকচার

```
psqli_bot/
├── bot.py              # মূল বট
├── config.py           # কনফিগারেশন
├── requirements.txt    # প্রয়োজনীয় প্যাকেজ
├── run_bot.sh          # চালানোর স্ক্রিপ্ট
├── psqli.sh            # আপনার মূল PSQLI স্ক্রিপ্ট
└── README.md           # ডকুমেন্টেশন

## ⚡ Features

- 🎯 **Single Site Injection** - Test one site
- 📋 **Mass Exploit** - Test multiple sites
- 🔍 **Auto Dorking** - Search and exploit
- 🛡️ **Admin Finder** - Find admin panels
- 🔐 **Login Bypass** - SQL injection bypass
- 🗃️ **Dork Dumper** - Dump data from dorks
- 📊 **Real-time Status** - Track progress
- ⏹️ **Cancel Scans** - Stop running scans
- 📎 **File Upload** - Upload URL lists

## 📦 Installation

### 1. Clone or Create Directory
```bash
mkdir psqli_bot
cd psqli_bot
```

2. Copy all files to this directory:

· bot.py
· config.py
· requirements.txt
· run_bot.sh
· psqli.sh (your script)

3. Configure

```bash
# Edit config.py and set:
BOT_TOKEN = "your_bot_token"
ADMIN_IDS = [your_telegram_id]
```

4. Install Dependencies

```bash
pip3 install -r requirements.txt
```

5. Run

```bash
chmod +x run_bot.sh
./run_bot.sh
```

🤖 Commands

Command Description
/start Show main menu
/help Show help
/status Check active scans
/cancel Cancel current scan
/scan <url> Single site scan
/admin <url> Admin finder
/bypass <url> Login bypass
/predefined Show predefined dorks
/scanall Mass scan mode

🎯 Usage Examples

Single Site Scan

```
/scan http://example.com/page.php?id=1
```

Mass Scan (File)

Upload a .txt file with URLs (one per line)

Mass Scan (Text)

```
http://site1.com/page.php?id=1
http://site2.com/page.php?id=2
http://site3.com/page.php?id=3
```

Dork Scan

```
inurl:.php?id= site:example.com|5
```

Admin Finder

```
/admin http://example.com
```

Login Bypass

```
/bypass http://example.com/admin/login.php
```

🔒 Security

· Rate Limiting: Prevents spam
· User Authorization: Restrict to allowed users
· Admin Controls: Full access for admins
· Logging: All actions are logged
· Timeout: Automatic scan timeout

⚙️ Configuration

Edit config.py:

```python
# Required
BOT_TOKEN = "your_bot_token"

# Admin users (full access)
ADMIN_IDS = [123456789]

# Allowed users (empty = everyone)
ALLOWED_USERS = []

# Rate limiting (seconds)
COOLDOWN_TIME = 5

# Concurrent scans
MAX_CONCURRENT_SCANS = 3

# Scan timeout (seconds)
SCAN_TIMEOUT = 300
```

📊 Output Format

Results are automatically formatted:

· ✅ Vulnerable sites found
· ❌ Not vulnerable sites
· ⚠️ Errors and issues
· 📊 Summary statistics
· 📄 Full results in text file

🛠️ Troubleshooting

Bot Not Starting

```bash
# Check Python
python3 --version

# Check dependencies
pip3 install -r requirements.txt --upgrade

# Check token
grep BOT_TOKEN config.py
```

Permission Issues

```bash
chmod +x psqli.sh
chmod +x run_bot.sh
chmod +x bot.py
```

Connection Issues

· Check internet connection
· Check firewall settings
· Try VPN if blocked

Scan Timeout

· Increase SCAN_TIMEOUT in config
· Check target URL is accessible
· Try smaller dork pages

📝 Logging

Logs are saved to:

· bot.log - Main log file
· logs/ - Detailed logs

⚠️ Disclaimer

Use this tool responsibly!

· Only test sites you own or have permission to test
· Unauthorized testing is illegal
· The developer is not responsible for misuse
· Use for educational and authorized security testing only

📜 License

This tool is for educational and authorized testing purposes only.

🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

📞 Support

For issues and questions:

· Check the logs: tail -f bot.log
· Open an issue on GitHub
· Contact the developer

---

Happy Testing! 🚀
```

---

## 🚀 দ্রুত শুরু করার নির্দেশনা

### ১. ফোল্ডার তৈরি করুন:
```bash
mkdir psqli_bot
cd psqli_bot
```

২. উপরের সব ফাইল কপি করে তৈরি করুন

৩. টোকেন সেট করুন:

config.py এ আপনার বট টোকেন দিন

৪. চালান:

```bash
chmod +x run_bot.sh
./run_bot.sh
```

৫. টেলিগ্রামে আপনার বট খুঁজুন এবং /start দিন

---

📱 টেলিগ্রামে ব্যবহার

1. আপনার বটকে /start মেসেজ দিন
2. মেনু থেকে অপশন সিলেক্ট করুন
3. নির্দেশনা অনুসরণ করুন
4. ফলাফল দেখুন

বটটি সম্পূর্ণ রেডি! শুভ ব্যবহার! 🚀

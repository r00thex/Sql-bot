#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🚀 PSQLI Telegram Bot
Powerful SQL Injection Testing Bot
Based on psqli.sh v3 MOD
"""

import asyncio
import subprocess
import os
import re
import time
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

import aiofiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

import config

# ============================================
# 📝 LOGGING SETUP
# ============================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

# ============================================
# 📊 DATA CLASSES
# ============================================

class ScanStatus(Enum):
    """Scan status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ScanInfo:
    """Scan information"""
    user_id: int
    scan_type: str
    target: str
    started: str = field(default_factory=lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    status: ScanStatus = ScanStatus.PENDING
    progress: str = "0%"
    result: str = ""
    error: str = ""

@dataclass
class UserSession:
    """User session data"""
    user_id: int
    mode: str = "single"
    last_command: float = 0
    scans: List[str] = field(default_factory=list)

# ============================================
# 🔧 UTILITY FUNCTIONS
# ============================================

class RateLimiter:
    """Rate limiter for users"""
    def __init__(self):
        self.user_last_command: Dict[int, float] = {}
        self.user_request_count: Dict[int, int] = {}
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to make request"""
        async with self._lock:
            now = time.time()
            if user_id in self.user_last_command:
                if now - self.user_last_command[user_id] < config.COOLDOWN_TIME:
                    return False
            self.user_last_command[user_id] = now
            return True
    
    async def reset(self, user_id: int):
        """Reset rate limit for user"""
        async with self._lock:
            if user_id in self.user_last_command:
                del self.user_last_command[user_id]

class SessionManager:
    """Manage user sessions"""
    def __init__(self):
        self.sessions: Dict[int, UserSession] = {}
        self._lock = asyncio.Lock()
    
    async def get_session(self, user_id: int) -> UserSession:
        """Get or create user session"""
        async with self._lock:
            if user_id not in self.sessions:
                self.sessions[user_id] = UserSession(user_id=user_id)
            return self.sessions[user_id]
    
    async def set_mode(self, user_id: int, mode: str):
        """Set user mode"""
        session = await self.get_session(user_id)
        session.mode = mode
    
    async def get_mode(self, user_id: int) -> str:
        """Get user mode"""
        session = await self.get_session(user_id)
        return session.mode

class ScanManager:
    """Manage active scans"""
    def __init__(self):
        self.active_scans: Dict[int, ScanInfo] = {}
        self._lock = asyncio.Lock()
    
    async def start_scan(self, user_id: int, scan_info: ScanInfo) -> bool:
        """Start a new scan"""
        async with self._lock:
            if len(self.active_scans) >= config.MAX_CONCURRENT_SCANS:
                return False
            self.active_scans[user_id] = scan_info
            return True
    
    async def update_scan(self, user_id: int, **kwargs):
        """Update scan info"""
        async with self._lock:
            if user_id in self.active_scans:
                for key, value in kwargs.items():
                    if hasattr(self.active_scans[user_id], key):
                        setattr(self.active_scans[user_id], key, value)
    
    async def get_scan(self, user_id: int) -> Optional[ScanInfo]:
        """Get scan info"""
        async with self._lock:
            return self.active_scans.get(user_id)
    
    async def complete_scan(self, user_id: int, result: str = "", error: str = ""):
        """Complete a scan"""
        async with self._lock:
            if user_id in self.active_scans:
                scan = self.active_scans[user_id]
                if error:
                    scan.status = ScanStatus.FAILED
                    scan.error = error
                else:
                    scan.status = ScanStatus.COMPLETED
                    scan.result = result
                # Keep for 1 hour then remove
                asyncio.create_task(self._cleanup_scan(user_id))
    
    async def cancel_scan(self, user_id: int):
        """Cancel a scan"""
        async with self._lock:
            if user_id in self.active_scans:
                self.active_scans[user_id].status = ScanStatus.CANCELLED
                await self._cleanup_scan(user_id, immediate=True)
    
    async def _cleanup_scan(self, user_id: int, immediate: bool = False):
        """Clean up scan after completion"""
        if immediate:
            async with self._lock:
                if user_id in self.active_scans:
                    del self.active_scans[user_id]
            return
        
        await asyncio.sleep(3600)  # Keep for 1 hour
        async with self._lock:
            if user_id in self.active_scans:
                del self.active_scans[user_id]

# ============================================
# 🎨 KEYBOARD MARKUPS
# ============================================

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("🎯 Single Site", callback_data="single"),
            InlineKeyboardButton("📋 Mass Exploit", callback_data="mass"),
        ],
        [
            InlineKeyboardButton("🔍 Dork + Exploit", callback_data="dork"),
            InlineKeyboardButton("🛡️ Admin Finder", callback_data="admin"),
        ],
        [
            InlineKeyboardButton("🗃️ Dork Dumper", callback_data="dumper"),
            InlineKeyboardButton("🔐 Login Bypass", callback_data="bypass"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("📊 Status", callback_data="status"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_scan_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Keyboard for active scan control"""
    keyboard = [
        [InlineKeyboardButton("⏹️ Stop Scan", callback_data=f"stop_{user_id}")],
        [InlineKeyboardButton("📊 Check Status", callback_data=f"check_{user_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_dork_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for predefined dorks"""
    keyboard = [
        [InlineKeyboardButton("🔍 Admin Pages", callback_data="dork_admin")],
        [InlineKeyboardButton("💉 SQLi Vulnerable", callback_data="dork_sqli")],
        [InlineKeyboardButton("📤 File Upload", callback_data="dork_upload")],
        [InlineKeyboardButton("✏️ Custom Dork", callback_data="dork_custom")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ============================================
# 🚀 CORE FUNCTIONS
# ============================================

async def run_command(command: List[str], timeout: int = config.SCAN_TIMEOUT) -> Tuple[str, str]:
    """Run command with timeout"""
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd()
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), 
            timeout=timeout
        )
        return stdout.decode('utf-8', errors='ignore'), stderr.decode('utf-8', errors='ignore')
    except asyncio.TimeoutError:
        try:
            process.kill()
        except:
            pass
        return "", "⏱️ Scan timeout: The process took too long"
    except Exception as e:
        return "", f"❌ Error: {str(e)}"

def format_scan_result(output: str) -> str:
    """Format scan result for Telegram message"""
    if not output:
        return "✅ Scan completed! No output received."
    
    lines = output.split('\n')
    result_lines = []
    
    vuln_count = 0
    error_count = 0
    found_count = 0
    
    keywords = ['vuln', 'found', 'injected', 'success', 'cracked']
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if any(k in line.lower() for k in keywords):
            if 'vuln' in line.lower() or 'found' in line.lower():
                vuln_count += 1
                result_lines.append(f"✅ {line}")
            elif 'injected' in line.lower():
                found_count += 1
                result_lines.append(f"💉 {line}")
            elif 'cracked' in line.lower():
                found_count += 1
                result_lines.append(f"🔓 {line}")
            else:
                result_lines.append(f"📝 {line}")
        elif 'error' in line.lower() or 'failed' in line.lower():
            error_count += 1
            if error_count <= config.MAX_ERROR_LINES:
                result_lines.append(f"⚠️ {line}")
    
    if not result_lines:
        # If no special keywords found, show first few lines
        for i, line in enumerate(lines[:20]):
            if line.strip():
                result_lines.append(f"📄 {line.strip()}")
        if len(lines) > 20:
            result_lines.append(f"... and {len(lines) - 20} more lines")
    
    summary = f"""📊 **Scan Summary**
├─ Vulnerabilities: {vuln_count}
├─ Found Items: {found_count}
├─ Errors: {error_count}
└─ Total Lines: {len(lines)}

📝 **Details:**"""
    
    summary += "\n" + "\n".join(result_lines[:config.MAX_RESULT_LINES])
    
    if len(result_lines) > config.MAX_RESULT_LINES:
        summary += f"\n\n... and {len(result_lines) - config.MAX_RESULT_LINES} more results"
    
    return summary

async def validate_url(url: str) -> bool:
    """Validate URL format"""
    if not url:
        return False
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"
    return True

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe storage"""
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)

# ============================================
# 🤖 COMMAND HANDLERS
# ============================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    # Check authorization
    if config.ALLOWED_USERS and user_id not in config.ALLOWED_USERS:
        await update.message.reply_text(
            "⛔ **Access Denied**\n\n"
            "You are not authorized to use this bot.\n"
            "Please contact the bot administrator.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    welcome_text = f"""
🚀 **PSQLI Bot**

Welcome {user.first_name}! 

I am a powerful SQL Injection testing bot.

**Main Features:**
├─ 🎯 Single Site Injection
├─ 📋 Mass Exploitation
├─ 🔍 Auto Dorking
├─ 🛡️ Admin Finder
├─ 🔐 Login Bypass
└─ 🗃️ Dork Dumper

**Quick Commands:**
/help - Show help
/status - Check active scans
/cancel - Cancel current scan
/predefined - Show predefined dorks

⚠️ **Use only on authorized targets!**
"""
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    logger.info(f"User {user_id} ({user.first_name}) started bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📖 **PSQLI Bot Help**

**Basic Commands:**
/start - Show main menu
/help - Show this help
/status - Check active scans
/cancel - Cancel current scan

**Features Guide:**

1️⃣ **Single Site**
   • Test one URL for SQL injection
   • Format: Send a URL or use /scan <url>

2️⃣ **Mass Exploit**
   • Test multiple sites at once
   • Upload a text file or paste URLs

3️⃣ **Auto Dorking**
   • Search for vulnerable sites
   • Format: dork|pages (e.g., inurl:.php?id=|5)

4️⃣ **Admin Finder**
   • Find admin panels
   • Format: /admin <url>

5️⃣ **Login Bypass**
   • Test SQL injection bypass
   • Format: /bypass <login_url>

6️⃣ **Dork Dumper**
   • Dump data from dork results
   • Format: dork|pages

**Tips:**
• Wait for scan to complete
• Results are auto-formatted
• Use /cancel to stop
• Check /status for progress

⚠️ **Legal Use Only!**
"""
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    user_id = update.effective_user.id
    scan = await scan_manager.get_scan(user_id)
    
    if not scan:
        await update.message.reply_text("📊 **No active scans running.**", parse_mode=ParseMode.MARKDOWN)
        return
    
    status_text = f"""
📊 **Scan Status**

🔹 **Type:** {scan.scan_type}
🔹 **Target:** `{scan.target[:50]}`
🔹 **Started:** {scan.started}
🔹 **Status:** {scan.status.value}
🔹 **Progress:** {scan.progress}

{scan.error if scan.error else ""}
"""
    await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = update.effective_user.id
    await scan_manager.cancel_scan(user_id)
    await update.message.reply_text("⏹️ **Scan cancelled successfully.**", parse_mode=ParseMode.MARKDOWN)

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scan command"""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a URL.\n"
            "Example: `/scan http://example.com/page.php?id=1`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    target = context.args[0]
    await run_single_scan(update, context, target)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a URL.\n"
            "Example: `/admin http://example.com`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    target = context.args[0]
    await run_admin_finder(update, context, target)

async def bypass_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /bypass command"""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a login URL.\n"
            "Example: `/bypass http://example.com/admin/login.php`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    target = context.args[0]
    await run_bypass_scan(update, context, target)

async def predefined_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /predefined command"""
    await update.message.reply_text(
        "🔍 **Predefined Dorks**\n\n"
        "Select a dork to use:",
        reply_markup=get_dork_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def scan_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /scanall command"""
    await update.message.reply_text(
        "📋 **Mass Scan Mode**\n\n"
        "Please upload a text file with URLs (one per line)\n"
        "or paste your URLs directly.",
        parse_mode=ParseMode.MARKDOWN
    )
    await session_manager.set_mode(update.effective_user.id, "mass")

# ============================================
# 🔄 CALLBACK HANDLERS
# ============================================

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Check authorization
    if config.ALLOWED_USERS and user_id not in config.ALLOWED_USERS:
        await query.edit_message_text("⛔ **Access Denied**", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Rate limit
    if not await rate_limiter.is_allowed(user_id):
        await query.edit_message_text(
            f"⏳ Please wait {config.COOLDOWN_TIME} seconds.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Handle menu navigation
    if data == "single":
        await query.edit_message_text(
            "🎯 **Single Site Injection**\n\n"
            "Send me the target URL.\n\n"
            "Example: `http://example.com/page.php?id=1`\n\n"
            "Or use: `/scan http://example.com/page.php?id=1`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "single")
    
    elif data == "mass":
        await query.edit_message_text(
            "📋 **Mass Exploit**\n\n"
            "**Option 1:** Upload a .txt file with URLs\n"
            "**Option 2:** Paste URLs (one per line)\n\n"
            "Example:\n"
            "`http://site1.com/page.php?id=1`\n"
            "`http://site2.com/page.php?id=2`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "mass")
    
    elif data == "dork":
        await query.edit_message_text(
            "🔍 **Auto Dorking**\n\n"
            "Send your dork query.\n\n"
            "**Format:** `dork|pages`\n\n"
            "Example: `inurl:.php?id= site:example.com|5`\n\n"
            "Or select a predefined dork:",
            reply_markup=get_dork_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "dork")
    
    elif data == "admin":
        await query.edit_message_text(
            "🛡️ **Admin Finder**\n\n"
            "Send me the target URL.\n\n"
            "Example: `http://example.com`\n\n"
            "Or use: `/admin http://example.com`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "admin")
    
    elif data == "dumper":
        await query.edit_message_text(
            "🗃️ **Dork Dumper**\n\n"
            "Send your dork query and pages.\n\n"
            "**Format:** `dork|pages`\n\n"
            "Example: `inurl:.php?id= login|3`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "dumper")
    
    elif data == "bypass":
        await query.edit_message_text(
            "🔐 **Login Bypass**\n\n"
            "Send me the login page URL.\n\n"
            "Example: `http://example.com/login.php`\n\n"
            "Or use: `/bypass http://example.com/login.php`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "bypass")
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "status":
        await status_command(update, context)
    
    # Dork selections
    elif data == "dork_admin":
        await query.edit_message_text(
            f"🔍 Using predefined admin dork:\n\n"
            f"`{config.PREDEFINED_DORKS['admin']}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "dork")
    
    elif data == "dork_sqli":
        await query.edit_message_text(
            f"🔍 Using predefined SQLi dork:\n\n"
            f"`{config.PREDEFINED_DORKS['sqli']}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "dork")
    
    elif data == "dork_upload":
        await query.edit_message_text(
            f"🔍 Using predefined upload dork:\n\n"
            f"`{config.PREDEFINED_DORKS['upload']}`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "dork")
    
    elif data == "dork_custom":
        await query.edit_message_text(
            "✏️ **Custom Dork**\n\n"
            "Send your custom dork query.\n\n"
            "**Format:** `dork|pages`\n\n"
            "Example: `inurl:.php?id= site:example.com|5`",
            parse_mode=ParseMode.MARKDOWN
        )
        await session_manager.set_mode(user_id, "dork")
    
    # Scan control
    elif data.startswith("stop_"):
        target_user = int(data.replace("stop_", ""))
        if user_id == target_user or user_id in config.ADMIN_IDS:
            await scan_manager.cancel_scan(target_user)
            await query.edit_message_text("⏹️ **Scan stopped.**", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("⛔ You can only stop your own scans.", parse_mode=ParseMode.MARKDOWN)
    
    elif data.startswith("check_"):
        target_user = int(data.replace("check_", ""))
        if user_id == target_user or user_id in config.ADMIN_IDS:
            await status_command(update, context)
        else:
            await query.edit_message_text("⛔ You can only check your own scans.", parse_mode=ParseMode.MARKDOWN)

# ============================================
# 📥 MESSAGE HANDLERS
# ============================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages"""
    user_id = update.effective_user.id
    message = update.message
    text = message.text
    document = message.document
    
    # Check authorization
    if config.ALLOWED_USERS and user_id not in config.ALLOWED_USERS:
        await message.reply_text("⛔ **Access Denied**", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Rate limit
    if not await rate_limiter.is_allowed(user_id):
        await message.reply_text(
            f"⏳ Please wait {config.COOLDOWN_TIME} seconds.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Get user mode
    mode = await session_manager.get_mode(user_id)
    
    # Handle document upload
    if document:
        if mode == "mass":
            await handle_mass_upload(update, context)
            return
        else:
            await message.reply_text(
                "📎 File received. Use Mass Exploit mode for file upload.\n"
                "Click '📋 Mass Exploit' from the menu.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
    
    # Handle text input
    if not text:
        await message.reply_text("❌ Invalid input. Please try again.")
        return
    
    # Process based on mode
    if mode == "single":
        await run_single_scan(update, context, text)
    elif mode == "mass":
        await handle_mass_text(update, context, text)
    elif mode in ["dork", "dumper"]:
        await run_dork_scan(update, context, text, mode)
    elif mode == "admin":
        await run_admin_finder(update, context, text)
    elif mode == "bypass":
        await run_bypass_scan(update, context, text)
    else:
        await message.reply_text(
            "❌ Unknown mode. Please use /start to select an option.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_mass_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mass scan file upload"""
    user_id = update.effective_user.id
    document = update.message.document
    
    # Validate file
    if not document.file_name.endswith('.txt'):
        await update.message.reply_text(
            "❌ Please upload a `.txt` file with URLs.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if document.file_size > config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ File too large. Maximum size: {config.MAX_FILE_SIZE // (1024*1024)}MB",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Download file
    file_path = f"temp_{user_id}_{int(time.time())}.txt"
    try:
        file = await document.get_file()
        await file.download_to_drive(file_path)
        
        # Read URLs
        async with aiofiles.open(file_path, 'r') as f:
            content = await f.read()
            urls = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not urls:
            await update.message.reply_text(
                "❌ No URLs found in the file.",
                parse_mode=ParseMode.MARKDOWN
            )
            os.remove(file_path)
            return
await update.message.reply_text(
            f"📋 **Mass Scan Started**\n\n"
            f"📄 File: {document.file_name}\n"
            f"📊 Total URLs: {len(urls)}\n\n"
            f"⏳ Processing...",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_scan_keyboard(user_id)
        )
        
        await run_mass_scan(update, context, urls)
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error reading file: {str(e)}", parse_mode=ParseMode.MARKDOWN)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

async def handle_mass_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Handle mass scan text input"""
    urls = [line.strip() for line in text.split('\n') if line.strip()]
    
    if len(urls) == 1:
        # Single URL - treat as single scan
        await run_single_scan(update, context, urls[0])
        return
    
    await update.message.reply_text(
        f"📋 **Mass Scan Started**\n\n"
        f"📊 Total URLs: {len(urls)}\n\n"
        f"⏳ Processing...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_scan_keyboard(update.effective_user.id)
    )
    
    await run_mass_scan(update, context, urls)

# ============================================
# 🎯 SCAN EXECUTION FUNCTIONS
# ============================================
async def run_single_scan(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Run single site scan"""
    user_id = update.effective_user.id
    
    # Validate URL
    if not await validate_url(target):
        await update.message.reply_text(
            "❌ Invalid URL format.\n"
            "Please provide a valid URL with protocol (http:// or https://)",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Check for duplicate scan
    existing = await scan_manager.get_scan(user_id)
    if existing and existing.status == ScanStatus.RUNNING:
        await update.message.reply_text(
            "⚠️ You already have a scan running.\n"
            "Please wait or use /cancel to stop it.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Create scan info
    scan_info = ScanInfo(
        user_id=user_id,
        scan_type="single",
        target=target
    )
    
    if not await scan_manager.start_scan(user_id, scan_info):
        await update.message.reply_text(
            f"⚠️ Maximum {config.MAX_CONCURRENT_SCANS} scans running.\n"
            "Please wait for others to finish.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    await update.message.reply_text(
        f"🎯 **Scanning:** `{target}`\n\n"
        f"⏳ This may take a few minutes...\n"
        f"Use /status to check progress.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_scan_keyboard(user_id)
    )
    
    try:
        # Run PSQLI
        command = [config.PSQLI_SCRIPT, target]
        stdout, stderr = await run_command(command)
        
        if stderr and "error" in stderr.lower():
            await scan_manager.complete_scan(user_id, error=stderr[:200])
            await update.message.reply_text(
                f"❌ **Error:**\n`{stderr[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Format result
        result = format_scan_result(stdout)
        await scan_manager.complete_scan(user_id, result=result)
        
        await update.message.reply_text(
            f"✅ **Scan Complete!**\n\n{result}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send result as file if too long
        if len(result) > 4000:
            result_file = f"result_{user_id}_{int(time.time())}.txt"
            async with aiofiles.open(result_file, 'w') as f:
                await f.write(f"Target: {target}\n\n{result}")
            await update.message.reply_document(
                document=open(result_file, 'rb'),
                caption=f"📄 Full result for {target[:50]}"
            )
            if os.path.exists(result_file):
                os.remove(result_file)
        
        logger.info(f"Completed single scan for user {user_id}: {target}")
        
    except Exception as e:
        await scan_manager.complete_scan(user_id, error=str(e))
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error in single scan for user {user_id}: {str(e)}")

async def run_mass_scan(update: Update, context: ContextTypes.DEFAULT_TYPE, urls: List[str]):
    """Run mass scan on multiple URLs"""
    user_id = update.effective_user.id
    
    scan_info = ScanInfo(
        user_id=user_id,
        scan_type="mass",
        target=f"mass_scan_{len(urls)}_urls"
    )
    await scan_manager.start_scan(user_id, scan_info)
total = len(urls)
    results = []
    vulnerable = 0
    failed = 0
    
    try:
        for i, url in enumerate(urls):
            progress = f"{i+1}/{total}"
            await scan_manager.update_scan(user_id, progress=progress)
            
            try:
                command = [config.PSQLI_SCRIPT, url]
                stdout, stderr = await run_command(command, timeout=120)
                
                if "vuln" in stdout.lower() or "found" in stdout.lower():
                    vulnerable += 1
                    results.append(f"✅ {url}")
                else:
                    results.append(f"❌ {url}")
                    
            except Exception as e:
                failed += 1
                results.append(f"⚠️ {url} - {str(e)[:50]}")
        
        await scan_manager.complete_scan(user_id)
        
        # Send summary
        summary = f"""
📊 **Mass Scan Complete!**

📋 Total Sites: {total}
✅ Vulnerable: {vulnerable}
❌ Not Vulnerable: {total - vulnerable - failed}
⚠️ Failed: {failed}

**Detailed Results:**
"""
        # Show results in batches
        for i, result in enumerate(results):
            if i < config.MAX_RESULT_LINES:
                summary += f"\n{result}"
        
        if len(results) > config.MAX_RESULT_LINES:
            summary += f"\n\n... and {len(results) - config.MAX_RESULT_LINES} more results"
        
        await update.message.reply_text(summary, parse_mode=ParseMode.MARKDOWN)
        
        # Send full results as file
        full_result = f"Mass_Scan_{user_id}_{int(time.time())}.txt"
        async with aiofiles.open(full_result, 'w') as f:
            await f.write(f"Mass Scan Results\n\nTotal: {total}\nVulnerable: {vulnerable}\n\n")
            await f.write("\n".join(results))
        
        await update.message.reply_document(
            document=open(full_result, 'rb'),
            caption=f"📄 Full results for {total} sites"
        )
        
        if os.path.exists(full_result):
            os.remove(full_result)
        
        logger.info(f"Completed mass scan for user {user_id}: {total} sites, {vulnerable} vulnerable")
        
    except Exception as e:
        await scan_manager.complete_scan(user_id, error=str(e))
        await update.message.reply_text(f"❌ **Mass scan error:** {str(e)}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error in mass scan for user {user_id}: {str(e)}")

async def run_dork_scan(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str, mode: str):
    """Run dork scan"""
    user_id = update.effective_user.id
    
    try:
        # Parse dork and pages
        if '|' in data:
            dork, pages = data.split('|', 1)
            dork = dork.strip()
            pages = pages.strip()
        else:
            dork = data.strip()
            pages = str(config.DEFAULT_PAGES)
        
        # Validate pages
        try:
            pages = int(pages)
            if pages < 1:
                pages = 1
            if pages > 10:
                pages = 10
        except:
            pages = config.DEFAULT_PAGES
        
        scan_info = ScanInfo(
            user_id=user_id,
            scan_type=mode,
            target=dork[:50]
        )
        await scan_manager.start_scan(user_id, scan_info)
        
        await update.message.reply_text(
            f"🔍 **Dork Scan Started**\n\n"
            f"📝 Dork: `{dork}`\n"
            f"📄 Pages: {pages}\n\n"
            f"⏳ Searching and scanning...",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_scan_keyboard(user_id)
        )
        
        # Run dork scan with PSQLI
        command = [config.PSQLI_SCRIPT, mode, dork, str(pages)]
        stdout, stderr = await run_command(command, timeout=600)
        
        if stderr and "error" in stderr.lower():
            await scan_manager.complete_scan(user_id, error=stderr[:200])
            await update.message.reply_text(
                f"❌ **Error:**\n`{stderr[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        result = format_scan_result(stdout)
        await scan_manager.complete_scan(user_id, result=result)
        
        await update.message.reply_text(
            f"✅ **Dork Scan Complete!**\n\n{result}",
            parse_mode=ParseMode.MARKDOWN
        )
logger.info(f"Completed dork scan for user {user_id}: {dork}")
        
    except Exception as e:
        await scan_manager.complete_scan(user_id, error=str(e))
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error in dork scan for user {user_id}: {str(e)}")

async def run_admin_finder(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Run admin finder"""
    user_id = update.effective_user.id
    
    if not await validate_url(target):
        await update.message.reply_text(
            "❌ Invalid URL format.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    scan_info = ScanInfo(
        user_id=user_id,
        scan_type="admin",
        target=target
    )
    await scan_manager.start_scan(user_id, scan_info)
    
    await update.message.reply_text(
        f"🛡️ **Admin Finder**\n\n"
        f"🔍 Searching on: `{target}`\n\n"
        f"⏳ Scanning for admin panels...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_scan_keyboard(user_id)
    )
    
    try:
        command = [config.PSQLI_SCRIPT, "admin", target]
        stdout, stderr = await run_command(command, timeout=180)
        
        if stderr and "error" in stderr.lower():
            await scan_manager.complete_scan(user_id, error=stderr[:200])
            await update.message.reply_text(
                f"❌ **Error:**\n`{stderr[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        result = format_scan_result(stdout)
        await scan_manager.complete_scan(user_id, result=result)
        
        await update.message.reply_text(
            f"✅ **Admin Finder Complete!**\n\n{result}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Completed admin finder for user {user_id}: {target}")
        
    except Exception as e:
        await scan_manager.complete_scan(user_id, error=str(e))
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error in admin finder for user {user_id}: {str(e)}")

async def run_bypass_scan(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str):
    """Run login bypass scan"""
    user_id = update.effective_user.id
    
    if not await validate_url(target):
        await update.message.reply_text(
            "❌ Invalid URL format.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    scan_info = ScanInfo(
        user_id=user_id,
        scan_type="bypass",
        target=target
    )
    await scan_manager.start_scan(user_id, scan_info)
    
await update.message.reply_text(
        f"🔐 **Login Bypass Test**\n\n"
        f"🔍 Testing on: `{target}`\n\n"
        f"⏳ Testing SQL injection bypass techniques...",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_scan_keyboard(user_id)
    )
    
    try:
        command = [config.PSQLI_SCRIPT, "bypass", target]
        stdout, stderr = await run_command(command, timeout=180)
        
        if stderr and "error" in stderr.lower():
            await scan_manager.complete_scan(user_id, error=stderr[:200])
            await update.message.reply_text(
                f"❌ **Error:**\n`{stderr[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        result = format_scan_result(stdout)
        await scan_manager.complete_scan(user_id, result=result)
        
        await update.message.reply_text(
            f"✅ **Bypass Test Complete!**\n\n{result}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"Completed bypass scan for user {user_id}: {target}")
        
    except Exception as e:
        await scan_manager.complete_scan(user_id, error=str(e))
        await update.message.reply_text(f"❌ **Error:** {str(e)}", parse_mode=ParseMode.MARKDOWN)
        logger.error(f"Error in bypass scan for user {user_id}: {str(e)}")

# ============================================
# ❌ ERROR HANDLER
# ============================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    error = context.error
    logger.error(f"Update {update} caused error {error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                f"❌ **An error occurred:**\n`{str(error)[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
    except:
        pass

# ============================================
# 🚀 MAIN FUNCTION
# ============================================

# Initialize managers
rate_limiter = RateLimiter()
session_manager = SessionManager()
scan_manager = ScanManager()

def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════╗
    ║    🚀 PSQLI Telegram Bot              ║
    ║    SQL Injection Testing Bot          ║
    ║    Based on psqli.sh v3 MOD           ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Create required directories
    for dir_name in [config.OUTPUT_DIR, config.RESULT_DIR]:
        os.makedirs(dir_name, exist_ok=True)
    
    # Check if psqli.sh exists
    if not os.path.exists(config.PSQLI_SCRIPT):
        print(f"❌ Error: {config.PSQLI_SCRIPT} not found!")
        print("Please ensure psqli.sh is in the same directory.")
        return
    
    # Make psqli.sh executable
    os.chmod(config.PSQLI_SCRIPT, 0o755)
    
    # Create application
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("scan", scan_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("bypass", bypass_command))
    application.add_handler(CommandHandler("predefined", predefined_command))
    application.add_handler(CommandHandler("scanall", scan_all_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # Add message handler
    application.add_handler(MessageHandler(
        filters.TEXT | filters.Document.ALL, 
        handle_message
    ))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    print("✅ Bot is running!")
    print("📊 Active sessions: 0")
    print("🔄 Press Ctrl+C to stop.")
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()

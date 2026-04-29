import asyncio
import json
import os
import re
import random
import secrets
import string
import hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest
import aiohttp

# ============================================
# 🔧 CONFIG - EDITED AS REQUESTED
# ============================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8748726116:AAHBskrmC976aLz8UoUUiXv2AQSlIneuvGk")
OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "8627624927").split(",") if x.strip()]

# TWO CHANNELS (NO GROUP)
CHANNEL_USERNAME_1 = "@ssbugchannel"      # First channel
CHANNEL_USERNAME_2 = "@+ZVEczsZmiWFkNTBl"     # Second channel (replace with actual)
YOUTUBE_LINK = "https://youtube.com/@shadowhere.460"
WHATSAPP_LINK = "https://whatsapp.com/channel/0029VbD54jxEgGfIqPaPSK24"

# ============================================
# ⚙️ MAIL.TM API CONFIG
# ============================================
MAIL_API = "https://api.mail.tm"

# ============================================
# 📁 FILE STORAGE SYSTEM
# ============================================
DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_path(filename):
    return os.path.join(DATA_DIR, filename)

def load_json(filename, default=None):
    path = get_path(filename)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default if default is not None else {}
    return default if default is not None else {}

def save_json(filename, data):
    path = get_path(filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def init_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    files = {
        "users.json": {},
        "otp_history.json": [],
        "tokens.json": {},  # Connected bots
        "admin_logs.json": []
    }
    for fname, default in files.items():
        if not os.path.exists(get_path(fname)):
            save_json(fname, default)

# User management
def get_user(user_id):
    users = load_json("users.json", {})
    return users.get(str(user_id), {})

def save_user(user_id, data):
    users = load_json("users.json", {})
    users[str(user_id)] = data
    save_json("users.json", users)

def get_all_users():
    return load_json("users.json", {})

# Connected Tokens (Sub-bots) - IMPROVED SYSTEM
def add_connected_token(token, added_by):
    tokens = load_json("tokens.json", {})
    tokens[token] = {
        "added_by": added_by,
        "added_at": datetime.now().isoformat(),
        "status": "active",
        "bot_username": None,
        "bot_id": None
    }
    save_json("tokens.json", tokens)

def remove_connected_token(token):
    tokens = load_json("tokens.json", {})
    if token in tokens:
        del tokens[token]
        save_json("tokens.json", tokens)

def get_connected_tokens():
    return load_json("tokens.json", {})

def update_token_info(token, bot_info):
    tokens = load_json("tokens.json", {})
    if token in tokens:
        tokens[token].update(bot_info)
        save_json("tokens.json", tokens)

# OTP History
def add_otp_record(user_id, data):
    history = load_json("otp_history.json", [])
    data['user_id'] = user_id
    data['id'] = secrets.token_hex(6)
    data['time'] = datetime.now().isoformat()
    history.append(data)
    if len(history) > 5000:
        history = history[-5000:]
    save_json("otp_history.json", history)

def get_user_otps(user_id, limit=10):
    history = load_json("otp_history.json", [])
    user_otps = [h for h in history if h.get('user_id') == user_id]
    return sorted(user_otps, key=lambda x: x.get('time', ''), reverse=True)[:limit]

# Admin Logs
def log_admin(action, admin_id, details=""):
    logs = load_json("admin_logs.json", [])
    logs.append({
        "action": action,
        "admin_id": admin_id,
        "details": details,
        "time": datetime.now().isoformat()
    })
    if len(logs) > 1000:
        logs = logs[-1000:]
    save_json("admin_logs.json", logs)

# ============================================
# 🔍 VERIFICATION CHECK - 2 CHANNELS
# ============================================

async def check_user_joined(bot, user_id):
    """Check if user joined both channels"""
    try:
        # Check Channel 1
        ch1_member = await bot.get_chat_member(CHANNEL_USERNAME_1, user_id)
        ch1_ok = ch1_member.status in ['member', 'administrator', 'creator']
        
        # Check Channel 2
        ch2_member = await bot.get_chat_member(CHANNEL_USERNAME_2, user_id)
        ch2_ok = ch2_member.status in ['member', 'administrator', 'creator']
        
        return ch1_ok and ch2_ok
    except Exception as e:
        print(f"Check join error: {e}")
        return False

# ============================================
# 🎨 UI & ANIMATIONS
# ============================================

def banner_text(text):
    return f"""
╔══════════════════════════════════════════╗
║  {text:^38}  ║
╚══════════════════════════════════════════╝"""

def glitch_effect(text):
    chars = "▓▒░█▄▀▌▐■□▪▫▬►◄▲▼◆◇○●◐◑★☆"
    return "".join(random.choice(chars) if random.random() > 0.85 else c for c in text)

def neon_text(text):
    neon = ["", "", "", ""]
    return random.choice(neon) + text

# Keyboards
def start_kb():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 CHANNEL 1", url=f"https://t.me/{CHANNEL_USERNAME_1.replace('@', '')}"),
            InlineKeyboardButton("📢 CHANNEL 2", url=f"https://t.me/{CHANNEL_USERNAME_2.replace('@', '')}")
        ],
        [
            InlineKeyboardButton("▶️ YOUTUBE", url=YOUTUBE_LINK),
            InlineKeyboardButton("💬 WHATSAPP", url=WHATSAPP_LINK)
        ],
        [InlineKeyboardButton("🔐 VERIFY & START", callback_data="verify")]
    ])

def main_menu_kb(is_owner=False):
    buttons = [
        [InlineKeyboardButton("📧 GET TEMP MAIL", callback_data="getmail")],
        [InlineKeyboardButton("📨 CHECK INBOX", callback_data="inbox")],
        [InlineKeyboardButton("👤 MY PROFILE", callback_data="profile")],
        [InlineKeyboardButton("📋 MY EMAILS", callback_data="history")]
    ]
    if is_owner:
        buttons.append([InlineKeyboardButton("👑 OWNER MENU", callback_data="owner_menu")])
    return InlineKeyboardMarkup(buttons)

def owner_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 BROADCAST", callback_data="broadcast")],
        [InlineKeyboardButton("➕ ADD BOT TOKEN", callback_data="addtoken")],
        [InlineKeyboardButton("📋 BOT LIST", callback_data="tokenlist")],
        [InlineKeyboardButton("📊 STATISTICS", callback_data="stats")],
        [InlineKeyboardButton("🔙 MAIN MENU", callback_data="menu")]
    ])

# ============================================
# 🤖 BOT COMMANDS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    user_data = get_user(uid)
    
    # ✅ AUTO CHECK: Agar pehle verified tha but ab channel leave kar diya
    if user_data and user_data.get('verified'):
        joined = await check_user_joined(context.bot, uid)
        if not joined:
            # User ne channel leave kar diya - unverify karo
            user_data['verified'] = False
            save_user(uid, user_data)
            await update.message.reply_photo(
                photo="https://i.postimg.cc/zX8C13Tg/header.jpg",
                caption=f"""{banner_text("⚠️ VERIFICATION LOST")}

❌ <b>You left the channels!</b>

⚠️ <b>Re-join karo:</b>
• {CHANNEL_USERNAME_1}
• {CHANNEL_USERNAME_2}

<code>🔻 Then click VERIFY & START 🔻</code>""",
                parse_mode=ParseMode.HTML,
                reply_markup=start_kb()
            )
            return
    
    if not user_data:
        # New user
        save_user(uid, {
            "uid": uid,
            "username": user.username,
            "name": user.first_name,
            "joined": datetime.now().isoformat(),
            "verified": False,
            "email": None,
            "email_pass": None,
            "email_token": None
        })
        
        welcome = f"""
{banner_text("🔥 TEMP MAIL BY SHADOW 🔥")}

👤 <b>User:</b> <code>{uid}</code>
📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ <b>COMPLETE VERIFICATION:</b>
• Join Channel 1 📢
• Join Channel 2 📢  
• Subscribe YouTube ▶️
• Join WhatsApp 💬

<code>🔻 Then click VERIFY & START 🔻</code>
"""
        await update.message.reply_photo(
            photo="https://i.postimg.cc/zX8C13Tg/header.jpg",
            caption=welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
    else:
        if user_data.get('verified'):
            # ✅ Already verified - direct menu show
            await show_menu(update, context)
        else:
            await update.message.reply_photo(
                photo="https://i.postimg.cc/zX8C13Tg/header.jpg",
                caption=f"""{banner_text("⚠️ VERIFICATION REQUIRED")}

Please complete verification:

• {CHANNEL_USERNAME_1}
• {CHANNEL_USERNAME_2}

Then click VERIFY & START""",
                parse_mode=ParseMode.HTML, 
                reply_markup=start_kb()
            )

async def verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Checking...")
    uid = query.from_user.id
    
    # CHECK BOTH CHANNELS
    joined = await check_user_joined(context.bot, uid)
    
    if not joined:
        await query.edit_message_caption(
            caption=f"""{banner_text("❌ NOT JOINED")}

⚠️ <b>Please join both channels:</b>
• {CHANNEL_USERNAME_1}
• {CHANNEL_USERNAME_2}

Then click VERIFY & START again.""",
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
        return
    
    # Save verified status
    user_data = get_user(uid)
    user_data['verified'] = True
    save_user(uid, user_data)
    
    # ✅ SUCCESS - Delete photo and show menu directly
    await query.delete_message()
    
    # Animation messages
    msg = await context.bot.send_message(
        uid,
        f"<code>{glitch_effect('TEMP MAIL BY SHADOW')}</code>\n\n<b>{neon_text('⚡ SYSTEM BOOT...')}</b>",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    await msg.edit_text(
        f"<code>{glitch_effect('TEMP MAIL BY SHADOW')}</code>\n\n<b>{neon_text('🔥 CONNECTING...')}</b>",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    await msg.edit_text(
        f"<code>{glitch_effect('TEMP MAIL BY SHADOW')}</code>\n\n<b>{neon_text('✅ ACCESS GRANTED!')}</b>",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(0.5)
    
    # Delete animation and show menu
    await msg.delete()
    await show_menu(update, context, edit=False)

# ============================================
# 📧 MAIL.TM INTEGRATION - 100% FREE
# ============================================

async def getmail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating...")
    uid = query.from_user.id
    
    # ✅ CHECK VERIFICATION AGAIN (auto-detect leave)
    joined = await check_user_joined(context.bot, uid)
    if not joined:
        user_data = get_user(uid)
        user_data['verified'] = False
        save_user(uid, user_data)
        await query.edit_message_text(
            f"""{banner_text("❌ VERIFICATION LOST")}

⚠️ <b>You left the channels!</b>

Please re-join:
• {CHANNEL_USERNAME_1}
• {CHANNEL_USERNAME_2}

Then /start again.""",
            parse_mode=ParseMode.HTML
        )
        return
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get domain
            async with session.get(f"{MAIL_API}/domains") as resp:
                domains_resp = await resp.json()
                members = domains_resp.get('hydra:member', [])
                if not members:
                    raise Exception("No domains available!")
                domain = random.choice(members)['domain']

            # Create account
            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            email = f"{username}@{domain}"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=15))

            async with session.post(f"{MAIL_API}/accounts", json={"address": email, "password": password}) as resp:
                if resp.status != 201:
                    raise Exception("Failed to create account")

            # Get token
            async with session.post(f"{MAIL_API}/token", json={"address": email, "password": password}) as resp:
                token_data = await resp.json()
                token = token_data.get('token')
                if not token:
                    raise Exception("Token failed")
            
            # Save user data
            user_data = get_user(uid)
            user_data.update({
                'email': email,
                'email_pass': password,
                'email_token': token,
                'email_created': datetime.now().isoformat()
            })
            save_user(uid, user_data)

            # Start polling
            asyncio.create_task(poll_otp_task(uid, email, token, context.bot))

            mail_text = f"""
{banner_text("📧 TEMP MAIL READY")}

📬 <b>Email:</b> <code>{email}</code>
🔑 <b>Password:</b> <code>{password}</code>
⏱ <b>Expires:</b> 15 minutes

<code>━━━━━━━━━━━━━━━━━━━━━</code>
⚡ <b>OTP will appear automatically!</b>
<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
            await query.edit_message_text(
                mail_text, 
                parse_mode=ParseMode.HTML, 
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 NEW MAIL", callback_data="getmail")],
                    [InlineKeyboardButton("📨 CHECK INBOX", callback_data="inbox")],
                    [InlineKeyboardButton("🔙 MENU", callback_data="menu")]
                ])
            )
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error:</b> <code>{str(e)}</code>\n\nTry again!", 
            parse_mode=ParseMode.HTML
        )

async def poll_otp_task(uid, email, token, bot):
    headers = {"Authorization": f"Bearer {token}"}
    seen = set()
    try:
        for _ in range(180):  # 15 min
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{MAIL_API}/messages", headers=headers) as resp:
                    data = await resp.json()
                    messages = data.get('hydra:member', [])
                    
                    for msg in messages:
                        mid = msg.get('id')
                        if mid and mid not in seen:
                            seen.add(mid)
                            
                            async with session.get(f"{MAIL_API}/messages/{mid}", headers=headers) as r:
                                detail = await r.json()
                                subject = detail.get('subject', 'No Subject')
                                sender = detail.get('from', {}).get('address', 'Unknown')
                                body = detail.get('text', '') or detail.get('html', '')
                                
                                otp = extract_otp(subject + " " + body)
                                
                                add_otp_record(uid, {
                                    "from": sender, 
                                    "subject": subject, 
                                    "otp": otp, 
                                    "body": body[:200]
                                })
                                
                                alert = f"""
🚨 {banner_text("OTP RECEIVED")} 🚨

📧 <b>From:</b> <code>{sender}</code>
📝 <b>Subject:</b> <code>{subject}</code>

<code>━━━━━━━━━━━━━━━━━━━━━</code>
🔐 <b>OTP CODE:</b>
<code>{otp or 'Not found in email'}</code>
<code>━━━━━━━━━━━━━━━━━━━━━</code>

⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}
"""
                                await bot.send_message(uid, alert, parse_mode=ParseMode.HTML)
            await asyncio.sleep(5)
    except Exception as e:
        print(f"Polling error: {e}")
    finally:
        # Cleanup
        user_data = get_user(uid)
        if user_data.get('email') == email:
            user_data['email'] = None
            user_data['email_token'] = None
            save_user(uid, user_data)
        await bot.send_message(
            uid, 
            "⏱️ <b>Email expired!</b>\nUse /start to get new one.", 
            parse_mode=ParseMode.HTML
        )

def extract_otp(text):
    """Extract OTP from text"""
    if not text:
        return None
    
    text = text.replace('\n', ' ').replace('\r', ' ')
    
    patterns = [
        r'(\d{3}[-\s]\d{3})',
        r'\b(\d{6})\b',
        r'\b(\d{4})\b',
        r'\b(\d{8})\b',
        r'(?i)otp[:\s]+(\d{3}[-\s]?\d{3})',
        r'(?i)otp[:\s]+(\d+)',
        r'(?i)code[:\s]+(\d{3}[-\s]\d{3})',
        r'(?i)code[:\s]+(\d+)',
        r'(?i)verification[:\s]+(\d+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if match:
                return match.strip()
    
    return None

# ============================================
# 📨 OTHER HANDLERS
# ============================================

async def inbox_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    # ✅ AUTO CHECK VERIFICATION
    joined = await check_user_joined(context.bot, uid)
    if not joined:
        user_data = get_user(uid)
        user_data['verified'] = False
        save_user(uid, user_data)
        await query.edit_message_text(
            f"""{banner_text("❌ VERIFICATION LOST")}

⚠️ <b>You left the channels!</b>

Please re-join and /start again.""",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_data = get_user(uid)
    email = user_data.get('email')
    
    if not email:
        await query.edit_message_text(
            "❌ No active email!\nGet one first.", 
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📧 GET MAIL", callback_data="getmail")]
            ])
        )
        return
    
    otps = get_user_otps(uid, 5)
    text = f"""
{banner_text("📨 INBOX")}

📬 <b>Email:</b> <code>{email}</code>

<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
    if otps:
        for i, o in enumerate(otps, 1):
            otp_disp = o.get('otp', 'N/A') or 'N/A'
            time_disp = o.get('time', '')
            if time_disp:
                time_disp = time_disp[11:16]
            text += f"\n{i}. <b>OTP:</b> <code>{otp_disp}</code> | ⏰ {time_disp}"
    else:
        text += "\n<i>Waiting for OTP...</i>"
    
    text += "\n<code>━━━━━━━━━━━━━━━━━━━━━</code>"
    
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 REFRESH", callback_data="inbox")],
            [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
        ])
    )

async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    # ✅ AUTO CHECK VERIFICATION
    joined = await check_user_joined(context.bot, uid)
    if not joined:
        user_data = get_user(uid)
        user_data['verified'] = False
        save_user(uid, user_data)
        await query.edit_message_text(
            f"""{banner_text("❌ VERIFICATION LOST")}

⚠️ <b>You left the channels!</b>

Please re-join and /start again.""",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_data = get_user(uid)
    
    # Count total emails generated
    history = load_json("otp_history.json", [])
    total_emails = len([h for h in history if h.get('user_id') == uid])
    
    text = f"""
{banner_text("👤 PROFILE")}

🆔 <b>ID:</b> <code>{uid}</code>
👤 <b>Name:</b> {user_data.get('name', 'N/A')}
📧 <b>Total Emails:</b> <code>{total_emails}</code>
📅 <b>Joined:</b> {user_data.get('joined', 'N/A')[:10]}

✅ <b>Status:</b> VERIFIED USER
💎 <b>Plan:</b> FREE UNLIMITED
"""
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML, 
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
        ])
    )

async def history_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    # ✅ AUTO CHECK VERIFICATION
    joined = await check_user_joined(context.bot, uid)
    if not joined:
        user_data = get_user(uid)
        user_data['verified'] = False
        save_user(uid, user_data)
        await query.edit_message_text(
            f"""{banner_text("❌ VERIFICATION LOST")}

⚠️ <b>You left the channels!</b>

Please re-join and /start again.""",
            parse_mode=ParseMode.HTML
        )
        return
    
    otps = get_user_otps(uid, 10)
    
    text = f"""
{banner_text("📋 EMAIL HISTORY")}

<b>Last 10 Emails:</b>

<code>━━━━━━━━━━━━━━━━━━━━━</code>
"""
    if otps:
        for i, o in enumerate(otps, 1):
            otp_disp = o.get('otp', 'N/A') or 'N/A'
            from_addr = o.get('from', 'Unknown')[:20]
            time_disp = o.get('time', '')
            if time_disp:
                time_disp = time_disp[11:16]
            text += f"\n{i}. <b>OTP:</b> <code>{otp_disp}</code>\n   📧 {from_addr} | ⏰ {time_disp}\n"
    else:
        text += "\n<i>No emails yet. Generate one!</i>"
    
    text += "\n<code>━━━━━━━━━━━━━━━━━━━━━</code>"
    
    await query.edit_message_text(
        text, 
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 BACK", callback_data="menu")]
        ])
    )

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_menu(update, context, edit=True)

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    uid = update.effective_user.id
    is_owner = uid in OWNER_IDS
    
    text = f"""
{banner_text("🔥 TEMP MAIL BY SHADOW 🔥")}

👤 <b>User:</b> <code>{uid}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

✅ <b>100% FREE - UNLIMITED EMAILS</b>

<code>⚡ Select an option below ⚡</code>
"""
    if edit:
        await update.callback_query.edit_message_text(
            text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=main_menu_kb(is_owner)
        )
    else:
        await update.message.reply_text(
            text, 
            parse_mode=ParseMode.HTML, 
            reply_markup=main_menu_kb(is_owner)
        )

# ============================================
# 👑 OWNER MENU & COMMANDS - SIMPLIFIED
# ============================================

async def owner_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    text = f"""
{banner_text("👑 OWNER MENU")}

🆔 <b>Admin ID:</b> <code>{uid}</code>
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}

<code>⚡ Select admin action ⚡</code>
"""
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=owner_menu_kb()
    )

async def broadcast_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"""{banner_text("📢 BROADCAST")}

📝 <b>Send your message now</b>
(Type /cancel to abort)

📊 <b>Target:</b> All users
⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_broadcast'] = True

async def addtoken_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    await query.edit_message_text(
        f"""{banner_text("➕ ADD BOT TOKEN")}

📝 <b>Send bot token to connect</b>
(Type /cancel to abort)

<code>Format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz</code>

✅ <b>Bot will auto-start and work like this bot!</b>""",
        parse_mode=ParseMode.HTML
    )
    context.user_data['awaiting_token'] = True

async def tokenlist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    tokens = get_connected_tokens()
    
    if not tokens:
        text = f"""{banner_text("📋 BOT LIST")}
        
<i>No connected bots found.</i>"""
    else:
        text = f"""{banner_text("📋 CONNECTED BOTS")}

<b>Total:</b> {len(tokens)} bots

"""
        for i, (token, data) in enumerate(tokens.items(), 1):
            bot_name = data.get('bot_username', 'Unknown')
            status = data.get('status', 'unknown')
            added = data.get('added_at', 'Unknown')[:10]
            text += f"{i}. @{bot_name}\n   📅 {added} | {'✅ Active' if status == 'active' else '❌ Inactive'}\n\n"
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 CLEAR ALL", callback_data="clear_tokens")],
            [InlineKeyboardButton("🔙 BACK", callback_data="owner_menu")]
        ])
    )

async def stats_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    
    if uid not in OWNER_IDS:
        await query.answer("❌ Owner only!", show_alert=True)
        return
    
    users = get_all_users()
    tokens = get_connected_tokens()
    
    verified = sum(1 for u in users.values() if u.get('verified'))
    
    text = f"""
{banner_text("📊 STATISTICS")}

👥 <b>Total Users:</b> <code>{len(users)}</code>
✅ <b>Verified:</b> <code>{verified}</code>
🤖 <b>Connected Bots:</b> <code>{len(tokens)}</code>

📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}
"""
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 BACK", callback_data="owner_menu")]
        ])
    )

# ============================================
# 📩 MESSAGE HANDLERS
# ============================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    if uid not in OWNER_IDS:
        return
    
    # Handle broadcast
    if context.user_data.get('awaiting_broadcast'):
        context.user_data['awaiting_broadcast'] = False
        message = update.message
        
        await message.reply_text("📤 <b>Broadcasting...</b>", parse_mode=ParseMode.HTML)
        
        users = get_all_users()
        sent = 0
        failed = 0
        
        for user_id in users.keys():
            try:
                if message.photo:
                    await context.bot.send_photo(
                        chat_id=user_id,
                        photo=message.photo[-1].file_id,
                        caption=message.caption,
                        parse_mode=ParseMode.HTML
                    )
                elif message.video:
                    await context.bot.send_video(
                        chat_id=user_id,
                        video=message.video.file_id,
                        caption=message.caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=message.text,
                        parse_mode=ParseMode.HTML
                    )
                sent += 1
                await asyncio.sleep(0.1)
            except (Forbidden, BadRequest):
                failed += 1
        
        log_admin("broadcast", uid, f"Sent: {sent}, Failed: {failed}")
        await message.reply_text(
            f"""{banner_text("✅ BROADCAST COMPLETE")}

📤 <b>Sent:</b> <code>{sent}</code>
❌ <b>Failed:</b> <code>{failed}</code>""",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Handle token add - NOW WITH AUTO-START
    if context.user_data.get('awaiting_token'):
        context.user_data['awaiting_token'] = False
        token = update.message.text.strip()
        
        # Validate token format
        if not re.match(r'^\d+:[A-Za-z0-9_-]+$', token):
            await update.message.reply_text("❌ <b>Invalid token format!</b>")
            return
        
        # Check if already exists
        tokens = get_connected_tokens()
        if token in tokens:
            await update.message.reply_text("❌ <b>Token already connected!</b>")
            return
        
        # Validate and get bot info
        try:
            from telegram import Bot
            test_bot = Bot(token)
            bot_info = await test_bot.get_me()
            bot_name = bot_info.username
            bot_id = bot_info.id
            
            # Save token with info
            add_connected_token(token, uid)
            update_token_info(token, {
                "bot_username": bot_name,
                "bot_id": bot_id,
                "status": "active"
            })
            
            log_admin("add_token", uid, f"Bot: @{bot_name}")
            
            await update.message.reply_text(
                f"""{banner_text("✅ BOT CONNECTED & STARTED")}

🤖 <b>Bot:</b> @{bot_name}
🆔 <b>ID:</b> <code>{bot_id}</code>
🔑 <b>Token:</b> <code>{token[:20]}...</code>

✅ <b>Bot is now ONLINE and working!</b>
✅ Same features as this main bot!

⚡ Users can now use @{bot_name}""",
                parse_mode=ParseMode.HTML
            )
            
            # 🚀 AUTO-START THE SUB-BOT
            asyncio.create_task(start_sub_bot(token))
            
        except Exception as e:
            await update.message.reply_text(f"❌ <b>Invalid token!</b>\nError: {str(e)}")
        return

# ============================================
# 🤖 SUB-BOT SYSTEM - AUTO START & WORK
# ============================================

async def start_sub_bot(token):
    """Start a connected sub-bot with same functionality"""
    try:
        sub_app = Application.builder().token(token).build()
        
        # Add same handlers as main bot
        sub_app.add_handler(CommandHandler("start", start))
        sub_app.add_handler(CommandHandler("cancel", cancel_cmd))
        
        # Callbacks - Main
        sub_app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
        sub_app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
        sub_app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
        sub_app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
        sub_app.add_handler(CallbackQueryHandler(history_cb, pattern="^history$"))
        sub_app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
        
        # Start the sub-bot
        await sub_app.initialize()
        await sub_app.start()
        await sub_app.updater.start_polling()
        
        print(f"✅ Sub-bot started: {token[:20]}...")
        
        # Keep running
        while True:
            await asyncio.sleep(3600)
            
    except Exception as e:
        print(f"❌ Sub-bot failed: {e}")
        # Mark as inactive
        tokens = load_json("tokens.json", {})
        if token in tokens:
            tokens[token]['status'] = 'error'
            save_json("tokens.json", tokens)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_menu_kb(update.effective_user.id in OWNER_IDS))

# ============================================
# 🚀 MAIN
# ============================================

def main():
    init_files()
    
    print("🤖 Temp Mail by Shadow - Starting...")
    print(f"👑 Owners: {OWNER_IDS}")
    print("📁 File-based storage initialized")
    print("📧 Mail.tm API integrated")
    print("✅ 100% FREE SYSTEM - No Premium")
    print("🤖 Sub-bot auto-start enabled")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    
    # Message handler (for broadcast/token)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Callbacks - Main
    app.add_handler(CallbackQueryHandler(verify_cb, pattern="^verify$"))
    app.add_handler(CallbackQueryHandler(getmail_cb, pattern="^getmail$"))
    app.add_handler(CallbackQueryHandler(inbox_cb, pattern="^inbox$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(history_cb, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
    
    # Callbacks - Owner
    app.add_handler(CallbackQueryHandler(owner_menu_cb, pattern="^owner_menu$"))
    app.add_handler(CallbackQueryHandler(broadcast_cb, pattern="^broadcast$"))
    app.add_handler(CallbackQueryHandler(addtoken_cb, pattern="^addtoken$"))
    app.add_handler(CallbackQueryHandler(tokenlist_cb, pattern="^tokenlist$"))
    app.add_handler(CallbackQueryHandler(stats_cb, pattern="^stats$"))
    
    print("✅ Bot ready!")
    app.run_polling()

if __name__ == "__main__":
    main()

import ast, re, sys
from pathlib import Path

p = Path.home() / "Desktop" / "vuadaomo" / "vuadaomo.py"
src = p.read_text(encoding="utf-8")
changed = []

# 1. Dam bao co state AS_*
if "AS_NAME, AS_PHONE, AS_SESS" not in src:
    old = "S_NAME, S_PHONE, S_OTP, S_PWD = range(4)"
    new = "S_NAME, S_PHONE, S_OTP, S_PWD = range(4)\nAS_NAME, AS_PHONE, AS_SESS = range(10, 13)"
    src = src.replace(old, new)
    changed.append("state")

# 2. Thay the 4 handler addsess neu da co, hoac them moi
new_block = '''async def addsess_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    if q: await q.answer()
    c.user_data.clear()
    if q:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Huy", callback_data="menu")]])
        txt = ("<b>THEM ACC BANG SESSION</b>\n\n"
               "Buoc 1/3: Nhap <b>ten acc</b> (vd: FOX)")
        try: await q.edit_message_caption(caption=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        except:
            try: await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
            except: await q.message.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await u.message.reply_text("<b>THEM ACC BANG SESSION</b>\n\nBuoc 1/3: Nhap <b>ten acc</b> (vd: FOX)", parse_mode=ParseMode.HTML)
    return AS_NAME


async def addsess_name(u: Update, c: ContextTypes.DEFAULT_TYPE):
    n = (u.message.text or "").strip()
    try: await u.message.delete()
    except: pass
    if not n or not re.match(r"^[A-Za-z0-9_]{1,20}$", n):
        await u.message.reply_text("Ten chi gom chu/so/gach duoi, 1-20 ky tu. Nhap lai hoac /cancel:")
        return AS_NAME
    if n in ACCS and not is_owner(u.effective_user.id, n):
        await u.message.reply_text("Ten " + n + " da co nguoi dung. Nhap ten khac:")
        return AS_NAME
    if n in ACCS:
        await u.message.reply_text("Ten " + n + " da co trong acc cua ban. Nhap ten khac:")
        return AS_NAME
    c.user_data["as_name"] = n
    await u.message.reply_text("Buoc 2/3: Nhap <b>SDT</b> (+84, vd: +84837258569):", parse_mode=ParseMode.HTML)
    return AS_PHONE


async def addsess_phone(u: Update, c: ContextTypes.DEFAULT_TYPE):
    ph = (u.message.text or "").strip()
    try: await u.message.delete()
    except: pass
    ph_clean = ph.replace(" ", "").replace("-", "")
    if not ph_clean.startswith("+") or not ph_clean[1:].isdigit() or len(ph_clean) < 10:
        await u.message.reply_text("SDT phai co dang +84xxxxxxxxx. Nhap lai hoac /cancel:")
        return AS_PHONE
    c.user_data["as_phone"] = ph_clean
    await u.message.reply_text(
        "Buoc 3/3: Paste <b>session string</b> vao day.\n\n"
        "<i>Lay session: chay script get_session.py tren may tinh (login 1 lan), copy chuoi dai bat dau bang <code>1BV...</code></i>\n\n"
        "Bot se XOA tin nay sau khi luu. Go /cancel de huy.",
        parse_mode=ParseMode.HTML)
    return AS_SESS


async def addsess_sess(u: Update, c: ContextTypes.DEFAULT_TYPE):
    s = (u.message.text or "").strip()
    try: await u.message.delete()
    except: pass
    name = c.user_data.get("as_name")
    phone = c.user_data.get("as_phone")
    if not name or not phone:
        await u.message.reply_text("Phien bi mat. Go /addsession de lam lai.")
        return ConversationHandler.END
    if not s or len(s) < 100:
        await u.message.reply_text("Session qua ngan (can > 100 ky tu). Nhap lai hoac /cancel:")
        return AS_SESS
    msg = await u.message.reply_text("Dang kiem tra session...")
    try:
        test = await fetch_initdata(s)
    except Exception as e:
        test = None
        err = str(e)
    if not test:
        try: await msg.edit_text("Session khong hoat dong. Kiem tra lai session string, hoac /cancel.")
        except: pass
        return AS_SESS
    ACCS[name] = {
        "phone": phone, "session_string": s, "owner": u.effective_user.id,
        "created": datetime.now().isoformat(),
        "flags": {"mine": True, "claim": True, "watch": True, "box": True, "craft": True, "spin": True, "exchange": True, "upgrade": True},
        "user": {}, "stats": {}, "cd": {},
        "init_data": test, "init_ts": time.time(),
    }
    _save(ACC_FILE, ACCS)
    c.user_data.clear()
    await msg.edit_text("Da them acc <b>" + name + "</b>\n\nSDT: " + phone + "\nInit data: OK",
        parse_mode=ParseMode.HTML, reply_markup=kb_main())
    return ConversationHandler.END


async def addsess_cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data.clear()
    await u.message.reply_text("Da huy.")
    return ConversationHandler.END


'''

# Xoa 4 handler cu neu co
for fn in ["addsess_start", "addsess_name", "addsess_phone", "addsess_sess", "addsess_cancel"]:
    m = re.search(rf"^async def {fn}\([^)]*\):\s*$", src, re.MULTILINE)
    if m:
        nxt = re.search(r"^(?:async def |def |class )", src[m.end():], re.MULTILINE)
        end = m.end() + nxt.start() if nxt else len(src)
        src = src[:m.start()] + src[end:]

# Chen block moi truoc cmd_start
src = src.replace("async def cmd_start(", new_block + "async def cmd_start(", 1)
changed.append("handlers")

# 3. Xoa conv2 cu neu co, dang ky lai
src = re.sub(r"    conv2 = ConversationHandler\(.*?app\.add_handler\(conv2\)\n",
             "", src, flags=re.DOTALL)

old_reg = "    app.add_handler(conv)\n"
new_reg = ('    conv2 = ConversationHandler(\n'
           '        entry_points=[CommandHandler("addsession", addsess_start),\n'
           '                       CallbackQueryHandler(addsess_start, pattern="^add_session$")],\n'
           '        states={AS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addsess_name)],\n'
           '                AS_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, addsess_phone)],\n'
           '                AS_SESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, addsess_sess)]},\n'
           '        fallbacks=[CommandHandler("cancel", addsess_cancel)])\n'
           '    app.add_handler(conv)\n'
           '    app.add_handler(conv2)\n')
src = src.replace(old_reg, new_reg, 1)
changed.append("conversation")

# 4. Dam bao co nut "Them bang session" trong menu
if 'callback_data="add_session"' not in src:
    old_btn = '[InlineKeyboardButton("➕  Thêm tài khoản", callback_data="add"),\n         InlineKeyboardButton("📋  Danh sách acc", callback_data="panel_list")],'
    new_btn = ('[InlineKeyboardButton("➕  Thêm (login)", callback_data="add"),\n'
               '         InlineKeyboardButton("🔑  Thêm (session)", callback_data="add_session")],\n'
               '        [InlineKeyboardButton("📋  Danh sách acc", callback_data="panel_list")],')
    if old_btn in src:
        src = src.replace(old_btn, new_btn, 1)
        changed.append("menu_btn")

# 5. Bo handler callback addsess_help cu (khong can nua)
src = re.sub(r'async def cb_addsess_help\([^)]*\):\s*.*?(?=^async def |\Z)',
             "", src, flags=re.DOTALL | re.MULTILINE)

p.write_text(src, encoding="utf-8")
ast.parse(src)
print("[+] OK. Changed: " + ", ".join(changed))
# language: Python, file: bot/control_bot.py
import asyncio
from pathlib import Path
from uuid import uuid4

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from _ipv4_session import IPv4Session as AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.errors import SessionPasswordNeededError, FloodWaitError

from config import (
    BOT_TOKEN, ADMIN_ID, API_ID, API_HASH, BOT_PROXY,
    SESSIONS_DIR, IMAGES_DIR,
    MESSAGES_FILE, TARGETS_FILE, BIOS_FILE, PROXIES_FILE,
    MIN_DELAY, MAX_DELAY, DAILY_MSG_CAP, BIO_ROTATE_EVERY,
)
from bot.keyboards import (
    main_menu, back_menu, accounts_menu, account_detail_menu,
    images_menu, item_list_menu, confirm_wipe, settings_menu, PER_PAGE,
    send_pick_account, send_pick_target, send_pick_message,
    send_pick_image, send_pick_image_from_library, send_confirm,
)
from core import notify as notify_mod
from core.spintax import spintax

_session = AiohttpSession(proxy=BOT_PROXY) if BOT_PROXY else None
bot = Bot(token=BOT_TOKEN, session=_session,
          default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
notify_mod.bind(bot)

_manager = None
_last_bot_msg: dict[int, int] = {}   # chat_id -> message_id tin bot cuối

MENU_TEXT = (
    "🛡️ <b>TELEGRAM CONTROL PANEL</b>\n"
    "━━━━━━━━━━━━━━━━━━━━━\n"
    "Chọn một mục bên dưới."
)


def attach(manager):
    global _manager
    _manager = manager


def _guard(event) -> bool:
    uid = event.from_user.id if event.from_user else 0
    return uid == ADMIN_ID


async def _safe_edit(c: CallbackQuery, text: str, kb=None):
    """Sửa tin bot tại chỗ. Ghi nhớ id để lần sau wipe được."""
    try:
        await c.message.edit_text(text, reply_markup=kb)
        _last_bot_msg[c.message.chat.id] = c.message.message_id
        return
    except Exception as e:
        if "message is not modified" in str(e).lower():
            _last_bot_msg[c.message.chat.id] = c.message.message_id
            return
        try:
            await c.message.delete()
        except Exception:
            pass
        try:
            sent = await c.message.answer(text, reply_markup=kb)
            _last_bot_msg[sent.chat.id] = sent.message_id
        except Exception:
            pass


async def _wipe_and_menu(chat_id: int, extra_ids=None):
    """Xoá tin bot cuối (+ vài id thêm), gửi lại menu chính."""
    to_del = set()
    old = _last_bot_msg.pop(chat_id, None)
    if old:
        to_del.add(old)
    if extra_ids:
        for x in extra_ids:
            if x:
                to_del.add(x)
    for mid in to_del:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass
    sent = await bot.send_message(chat_id, MENU_TEXT, reply_markup=main_menu())
    _last_bot_msg[chat_id] = sent.message_id


async def _try_delete(m: Message):
    """Xoá tin user vừa gửi (best effort)."""
    try:
        await m.delete()
    except Exception:
        pass


# ---------- file helpers ----------

def _lines(path: Path):
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def _write_lines(path: Path, lines):
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _delete_at(path: Path, idx: int) -> int:
    lines = _lines(path)
    if 0 <= idx < len(lines):
        lines.pop(idx)
        _write_lines(path, lines)
    return len(lines)


def _append_lines(path: Path, text: str) -> int:
    new = [l.strip() for l in text.splitlines()
           if l.strip() and not l.strip().startswith("#")]
    lines = _lines(path) + new
    _write_lines(path, lines)
    return len(lines)


def _wipe(path: Path) -> int:
    n = len(_lines(path))
    _write_lines(path, [])
    return n


# ---------- FSM ----------

class LoginFlow(StatesGroup):
    phone    = State()
    code     = State()
    password = State()


class ItemFlow(StatesGroup):
    target  = State()
    message = State()
    bio     = State()
    proxy   = State()


class ImageFlow(StatesGroup):
    photo = State()


class SendFlow(StatesGroup):
    pick_target  = State()
    pick_message = State()
    pick_image   = State()


class SetBioFlow(StatesGroup):
    input = State()


_pending = {}
_send_sessions = {}


# ---------- /start, /cancel ----------

@dp.message(Command("start"))
async def cmd_start(m: Message, state: FSMContext):
    if not _guard(m):
        return
    await state.clear()
    _send_sessions.pop(m.from_user.id, None)
    await _try_delete(m)
    await _wipe_and_menu(m.chat.id)


@dp.message(Command("cancel"))
async def cmd_cancel(m: Message, state: FSMContext):
    if not _guard(m):
        return
    uid = m.from_user.id
    if uid in _pending:
        try:
            await _pending[uid]["client"].disconnect()
        except Exception:
            pass
        _pending.pop(uid, None)
    _send_sessions.pop(uid, None)
    await state.clear()
    await _try_delete(m)
    await _wipe_and_menu(m.chat.id)


# ---------- navigation ----------

@dp.callback_query(F.data == "back")
async def cb_back(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    await state.clear()
    _send_sessions.pop(c.from_user.id, None)
    await c.answer()
    await _wipe_and_menu(c.message.chat.id, extra_ids=[c.message.message_id])


# ---------- dashboard ----------

@dp.callback_query(F.data == "dashboard")
async def cb_dashboard(c: CallbackQuery):
    if not _guard(c):
        return
    rows = _manager.stats()
    total_sent = sum(r[2] for r in rows)
    total_err  = sum(r[3] for r in rows)
    active = sum(1 for r in rows if r[1] == "🟢")
    paused = sum(1 for r in rows if r[1] == "⏸️")
    imgs = len([f for f in IMAGES_DIR.glob("*") if f.is_file()])

    lines = [
        "📊  <b>DASHBOARD</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"👥 Tài khoản: <b>{len(rows)}</b>   🟢 {active}  ⏸️ {paused}",
        f"📨 Đã gửi: <b>{total_sent}</b>   ⚠️ Lỗi: <b>{total_err}</b>",
        f"🖼 Ảnh: <b>{imgs}</b>   🎯 Targets: <b>{len(_lines(TARGETS_FILE))}</b>",
        f"📝 Messages: <b>{len(_lines(MESSAGES_FILE))}</b>   🛡 Bio: <b>{len(_lines(BIOS_FILE))}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]
    if rows:
        lines.append("<b>Chi tiết:</b>")
        for name, st, sent, err in rows:
            lines.append(f"{st} <code>{name}</code>  📨<b>{sent}</b>  ⚠️<b>{err}</b>")
    else:
        lines.append("<i>Chưa có worker nào chạy.</i>")

    await c.answer()
    await _safe_edit(c, "\n".join(lines), main_menu())


# ---------- start/stop/pause/resume ----------

@dp.callback_query(F.data == "start_all")
async def cb_start(c: CallbackQuery):
    if not _guard(c):
        return
    await c.answer("Đang khởi động…")
    await _manager.start_all()
    await cb_dashboard(c)


@dp.callback_query(F.data == "stop_all")
async def cb_stop(c: CallbackQuery):
    if not _guard(c):
        return
    await c.answer("Đang dừng…")
    await _manager.stop_all()
    await cb_dashboard(c)


@dp.callback_query(F.data == "pause_all")
async def cb_pause(c: CallbackQuery):
    if not _guard(c):
        return
    _manager.pause()
    await c.answer("⏸ Đã tạm dừng")
    await cb_dashboard(c)


@dp.callback_query(F.data == "resume_all")
async def cb_resume(c: CallbackQuery):
    if not _guard(c):
        return
    _manager.resume()
    await c.answer("▶️ Đã tiếp tục")
    await cb_dashboard(c)


# =========================================================
#  ACCOUNTS
# =========================================================

@dp.callback_query(F.data == "accounts")
async def cb_accounts(c: CallbackQuery):
    if not _guard(c):
        return
    sessions = sorted(p.stem for p in SESSIONS_DIR.glob("*.session"))
    text = (
        "👥  <b>TÀI KHOẢN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"Tổng: <b>{len(sessions)}</b> session\n\n"
        + ("\n".join(f"•  <code>{s}</code>" for s in sessions) if sessions
           else "<i>Chưa có session nào. Bấm ➕ để thêm.</i>")
    )
    await c.answer()
    await _safe_edit(c, text, accounts_menu(sessions))


@dp.callback_query(F.data.startswith("acc:show:"))
async def cb_acc_show(c: CallbackQuery):
    if not _guard(c):
        return
    name = c.data.split(":", 2)[2]
    w = _manager.get_worker(name)
    if w:
        state_icon = "🟢 online" if (w.running and not w.paused) else (
            "⏸️ paused" if w.paused else "⚪ offline")
        proxy_str = f"{w.proxy[1]}:{w.proxy[2]}" if w.proxy else "none"
        sent = w.sent
        err = w.errors
    else:
        state_icon = "⚪ chưa chạy"
        proxy_str = "—"
        sent = 0
        err = 0
    text = (
        f"👤  <b>{name}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Trạng thái: {state_icon}\n"
        f"📨 Đã gửi: <b>{sent}</b>\n"
        f"⚠️ Lỗi: <b>{err}</b>\n"
        f"🌐 Proxy: <code>{proxy_str}</code>"
    )
    await c.answer()
    await _safe_edit(c, text, account_detail_menu(name))


@dp.callback_query(F.data.startswith("acc:pause:"))
async def cb_acc_pause(c: CallbackQuery):
    if not _guard(c):
        return
    name = c.data.split(":", 2)[2]
    w = _manager.get_worker(name)
    if w:
        w.paused = True
    await c.answer("⏸ Đã tạm dừng")
    await cb_acc_show(c)


@dp.callback_query(F.data.startswith("acc:resume:"))
async def cb_acc_resume(c: CallbackQuery):
    if not _guard(c):
        return
    name = c.data.split(":", 2)[2]
    w = _manager.get_worker(name)
    if w:
        w.paused = False
    await c.answer("▶️ Đã tiếp tục")
    await cb_acc_show(c)


@dp.callback_query(F.data.startswith("acc:bio:"))
async def cb_acc_bio(c: CallbackQuery):
    if not _guard(c):
        return
    name = c.data.split(":", 2)[2]
    ok = await _manager.rotate_bio_now(name)
    await c.answer("🛡 Đã đổi bio" if ok else "Worker không chạy")
    await cb_acc_show(c)


@dp.callback_query(F.data.startswith("acc:setbio:"))
async def cb_acc_setbio(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    name = c.data.split(":", 2)[2]
    _send_sessions.setdefault(c.from_user.id, {})["setbio_acc"] = name
    await state.set_state(SetBioFlow.input)
    await c.answer()
    await _safe_edit(
        c,
        f"✏️  <b>ĐẶT BIO CỤ THỂ</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Acc: <code>{name}</code>\n\n"
        "Gửi <b>nội dung bio</b> mày muốn đặt.\n"
        "Chữ, emoji, link, số — gì cũng được.\n"
        "Giới hạn: <b>70</b> ký tự (acc thường) / <b>140</b> (Premium).\n\n"
        "<i>/cancel để huỷ.</i>",
        back_menu(),
    )


@dp.message(SetBioFlow.input)
async def setbio_input(m: Message, state: FSMContext):
    if not _guard(m):
        return
    text = (m.text or "").strip()
    sess = _send_sessions.get(m.from_user.id, {})
    name = sess.get("setbio_acc")
    await _try_delete(m)

    if not text or not name:
        await state.clear()
        _send_sessions.pop(m.from_user.id, None)
        await _wipe_and_menu(m.chat.id)
        return

    ok, info = await _set_bio_direct(name, text)
    await state.clear()
    _send_sessions.pop(m.from_user.id, None)

    if ok:
        body = (
            f"✅  <b>ĐÃ ĐẶT BIO</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Acc: <code>{name}</code>\n"
            f"📝 Bio: <i>{text}</i>\n"
            f"📏 {len(text)} ký tự"
        )
    else:
        body = (
            f"❌  <b>LỖI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Acc: <code>{name}</code>\n"
            f"<code>{info}</code>"
        )

    await _wipe_and_menu(m.chat.id)
    sent = await bot.send_message(m.chat.id, body, reply_markup=main_menu())
    _last_bot_msg[m.chat.id] = sent.message_id


async def _set_bio_direct(acc_name: str, bio_text: str):
    worker = _manager.get_worker(acc_name)
    client = None
    we_connected = False

    if worker and worker.client:
        client = worker.client
        try:
            if not client.is_connected():
                await client.connect()
                we_connected = True
        except Exception as e:
            return False, f"connect: {type(e).__name__}: {e}"
    else:
        session_path = SESSIONS_DIR / acc_name
        client = TelegramClient(
            str(session_path), API_ID, API_HASH,
            device_model="Desktop", system_version="Windows 10", app_version="4.16.8",
        )
        try:
            await client.connect()
            we_connected = True
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "session chưa login hoặc đã hết hạn"
        except Exception as e:
            return False, f"connect: {type(e).__name__}: {e}"

    try:
        await client(UpdateProfileRequest(about=bio_text))
        return True, "ok"
    except Exception as e:
        n = type(e).__name__
        if "AboutTooLong" in n:
            return False, f"Bio quá dài ({len(bio_text)} ký tự). Rút ngắn lại."
        return False, f"{n}: {e}"
    finally:
        if we_connected and not worker:
            try:
                await client.disconnect()
            except Exception:
                pass


@dp.callback_query(F.data == "acc:add")
async def cb_acc_add(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    await state.set_state(LoginFlow.phone)
    await c.answer()
    await _safe_edit(
        c,
        "➕  <b>THÊM TÀI KHOẢN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Gửi <b>số điện thoại</b> đầy đủ:\n"
        "<code>+84911404475</code>\n\n"
        "<i>/cancel để huỷ.</i>",
        back_menu(),
    )


@dp.message(LoginFlow.phone)
async def login_phone(m: Message, state: FSMContext):
    if not _guard(m):
        return
    phone = (m.text or "").strip()
    await _try_delete(m)

    if not phone.startswith("+") or len(phone) < 8:
        sent = await bot.send_message(m.chat.id,
            "⚠️ Sai định dạng. Gửi lại <code>+84...</code>", reply_markup=back_menu())
        _last_bot_msg[m.chat.id] = sent.message_id
        return

    if not API_ID or not API_HASH:
        await state.clear()
        await _wipe_and_menu(m.chat.id)
        sent = await bot.send_message(m.chat.id,
            "❌ Chưa điền API_ID / API_HASH trong config.py", reply_markup=main_menu())
        _last_bot_msg[m.chat.id] = sent.message_id
        return

    uid = m.from_user.id
    if uid in _pending:
        try:
            await _pending[uid]["client"].disconnect()
        except Exception:
            pass
        _pending.pop(uid, None)

    clean = phone.replace("+", "").replace(" ", "")
    session_path = SESSIONS_DIR / clean

    client = TelegramClient(
        str(session_path), API_ID, API_HASH,
        device_model="Desktop", system_version="Windows 10", app_version="4.16.8",
    )
    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
    except Exception as e:
        await state.clear()
        try:
            await client.disconnect()
        except Exception:
            pass
        await _wipe_and_menu(m.chat.id)
        sm = await bot.send_message(m.chat.id,
            f"❌ Lỗi gửi OTP: <code>{type(e).__name__}: {e}</code>",
            reply_markup=main_menu())
        _last_bot_msg[m.chat.id] = sm.message_id
        return

    _pending[uid] = {"client": client, "phone": phone, "hash": sent_code.phone_code_hash}
    await state.set_state(LoginFlow.code)
    sent = await bot.send_message(m.chat.id,
        f"📩 OTP đã gửi tới <code>{phone}</code>.\nGửi <b>mã OTP</b>.",
        reply_markup=back_menu())
    _last_bot_msg[m.chat.id] = sent.message_id


@dp.message(LoginFlow.code)
async def login_code(m: Message, state: FSMContext):
    if not _guard(m):
        return
    code = (m.text or "").strip().replace(" ", "")
    p = _pending.get(m.from_user.id)
    await _try_delete(m)

    if not p:
        await state.clear()
        await _wipe_and_menu(m.chat.id)
        return

    try:
        await p["client"].sign_in(p["phone"], code, phone_code_hash=p["hash"])
    except SessionPasswordNeededError:
        await state.set_state(LoginFlow.password)
        sent = await bot.send_message(m.chat.id,
            "🔐 Tài khoản có 2FA. Gửi <b>mật khẩu 2FA</b>.", reply_markup=back_menu())
        _last_bot_msg[m.chat.id] = sent.message_id
        return
    except Exception as e:
        sent = await bot.send_message(m.chat.id,
            f"❌ OTP sai / hết hạn: <code>{type(e).__name__}: {e}</code>",
            reply_markup=back_menu())
        _last_bot_msg[m.chat.id] = sent.message_id
        return

    await _finalize_login(m, state)


@dp.message(LoginFlow.password)
async def login_password(m: Message, state: FSMContext):
    if not _guard(m):
        return
    pw = (m.text or "").strip()
    p = _pending.get(m.from_user.id)
    await _try_delete(m)

    if not p:
        await state.clear()
        await _wipe_and_menu(m.chat.id)
        return
    try:
        await p["client"].sign_in(password=pw)
    except Exception as e:
        sent = await bot.send_message(m.chat.id,
            f"❌ Sai 2FA: <code>{type(e).__name__}: {e}</code>", reply_markup=back_menu())
        _last_bot_msg[m.chat.id] = sent.message_id
        return
    await _finalize_login(m, state)


async def _finalize_login(m: Message, state: FSMContext):
    p = _pending.pop(m.from_user.id, None)
    if not p:
        await state.clear()
        await _wipe_and_menu(m.chat.id)
        return
    name = "?"
    try:
        me = await p["client"].get_me()
        name = me.username or me.id
    except Exception:
        pass
    finally:
        try:
            await p["client"].disconnect()
        except Exception:
            pass

    await state.clear()
    await _wipe_and_menu(m.chat.id)
    sent = await bot.send_message(m.chat.id,
        f"✅  <b>ĐĂNG NHẬP THÀNH CÔNG</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 @{name}\n"
        f"💾 Session: <code>{p['phone']}</code>",
        reply_markup=main_menu())
    _last_bot_msg[m.chat.id] = sent.message_id


# =========================================================
#  SEND NOW
# =========================================================

@dp.callback_query(F.data == "send_now")
async def cb_send_now(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    sessions = sorted(p.stem for p in SESSIONS_DIR.glob("*.session"))
    if not sessions:
        await c.answer("Chưa có tài khoản nào", show_alert=True)
        return
    _send_sessions[c.from_user.id] = {}
    await state.clear()
    await c.answer()
    await _safe_edit(
        c,
        "📤  <b>GỬI NGAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 1/4</b> — chọn tài khoản gửi.",
        send_pick_account(sessions),
    )


@dp.callback_query(F.data.startswith("sn:acc:"))
async def cb_sn_acc(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    acc = c.data.split(":", 2)[2]
    _send_sessions.setdefault(c.from_user.id, {})["acc"] = acc
    targets = _lines(TARGETS_FILE)
    await c.answer()
    if targets:
        await _safe_edit(
            c,
            f"📤  <b>GỬI NGAY</b>\n"
            f"👤 Acc: <code>{acc}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Bước 2/4</b> — chọn target, hoặc nhập mới.",
            send_pick_target(targets, page=0),
        )
    else:
        await state.set_state(SendFlow.pick_target)
        await _safe_edit(
            c,
            f"📤  <b>GỬI NGAY</b>\n"
            f"👤 Acc: <code>{acc}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Bước 2/4</b> — danh sách trống.\n"
            "Gửi <b>target</b>:\n"
            "<code>@username</code> hoặc <code>https://t.me/...</code>",
            back_menu(),
        )


@dp.callback_query(F.data.startswith("sn:tg_page:"))
async def cb_sn_tg_page(c: CallbackQuery):
    if not _guard(c):
        return
    page = int(c.data.rsplit(":", 1)[1])
    targets = _lines(TARGETS_FILE)
    sess = _send_sessions.get(c.from_user.id, {})
    await c.answer()
    await _safe_edit(
        c,
        f"📤  <b>GỬI NGAY</b>\n"
        f"👤 Acc: <code>{sess.get('acc','?')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 2/4</b> — chọn target.",
        send_pick_target(targets, page=page),
    )


@dp.callback_query(F.data.startswith("sn:tg:"))
async def cb_sn_tg(c: CallbackQuery):
    if not _guard(c):
        return
    idx = int(c.data.rsplit(":", 1)[1])
    targets = _lines(TARGETS_FILE)
    if not (0 <= idx < len(targets)):
        await c.answer("Không tìm thấy", show_alert=True)
        return
    _send_sessions[c.from_user.id]["target"] = targets[idx]
    await _sn_ask_message(c)


@dp.callback_query(F.data == "sn:tg_custom")
async def cb_sn_tg_custom(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    await state.set_state(SendFlow.pick_target)
    await c.answer()
    await _safe_edit(
        c,
        "📤  <b>GỬI NGAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 2/4</b> — nhập <b>target</b>:\n"
        "<code>@username</code> hoặc <code>https://t.me/...</code>",
        back_menu(),
    )


@dp.message(SendFlow.pick_target)
async def sn_save_target(m: Message, state: FSMContext):
    if not _guard(m):
        return
    t = (m.text or "").strip()
    await _try_delete(m)
    if not t:
        return
    _send_sessions.setdefault(m.from_user.id, {})["target"] = t
    await state.clear()

    # Edit tin bot đang hiện để đi bước 3, không gửi tin mới
    chat_id = m.chat.id
    mid = _last_bot_msg.get(chat_id)
    text = (
        f"📤  <b>GỬI NGAY</b>\n"
        f"👤 Acc: <code>{_send_sessions[m.from_user.id].get('acc','?')}</code>\n"
        f"🎯 Target: <code>{t}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 3/4</b> — nhập <b>nội dung</b> gửi:"
    )
    if mid:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=mid,
                text=text, reply_markup=back_menu())
            await state.set_state(SendFlow.pick_message)
            return
        except Exception:
            pass
    sent = await bot.send_message(chat_id, text, reply_markup=back_menu())
    _last_bot_msg[chat_id] = sent.message_id
    await state.set_state(SendFlow.pick_message)


async def _sn_ask_message(c: CallbackQuery):
    msgs = _lines(MESSAGES_FILE)
    sess = _send_sessions.get(c.from_user.id, {})
    await c.answer()
    if msgs:
        await _safe_edit(
            c,
            f"📤  <b>GỬI NGAY</b>\n"
            f"👤 Acc: <code>{sess.get('acc','?')}</code>\n"
            f"🎯 Target: <code>{sess.get('target','?')}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Bước 3/4</b> — chọn nội dung, hoặc nhập mới.",
            send_pick_message(msgs, page=0),
        )
    else:
        await _safe_edit(
            c,
            f"📤  <b>GỬI NGAY</b>\n"
            f"👤 Acc: <code>{sess.get('acc','?')}</code>\n"
            f"🎯 Target: <code>{sess.get('target','?')}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Bước 3/4</b> — nhập <b>nội dung</b> gửi:\n"
            "Spintax <code>{a|b|c}</code> dùng được.",
            back_menu(),
        )


@dp.callback_query(F.data.startswith("sn:msg_page:"))
async def cb_sn_msg_page(c: CallbackQuery):
    if not _guard(c):
        return
    page = int(c.data.rsplit(":", 1)[1])
    msgs = _lines(MESSAGES_FILE)
    sess = _send_sessions.get(c.from_user.id, {})
    await c.answer()
    await _safe_edit(
        c,
        f"📤  <b>GỬI NGAY</b>\n"
        f"👤 <code>{sess.get('acc','?')}</code>  🎯 <code>{sess.get('target','?')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 3/4</b> — chọn nội dung.",
        send_pick_message(msgs, page=page),
    )


@dp.callback_query(F.data.startswith("sn:msg:"))
async def cb_sn_msg(c: CallbackQuery):
    if not _guard(c):
        return
    idx = int(c.data.rsplit(":", 1)[1])
    msgs = _lines(MESSAGES_FILE)
    if not (0 <= idx < len(msgs)):
        await c.answer("Không tìm thấy", show_alert=True)
        return
    _send_sessions[c.from_user.id]["message"] = msgs[idx]
    await _sn_ask_image(c)


@dp.callback_query(F.data == "sn:msg_custom")
async def cb_sn_msg_custom(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    await state.set_state(SendFlow.pick_message)
    await c.answer()
    await _safe_edit(
        c,
        "📤  <b>GỬI NGAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 3/4</b> — nhập <b>nội dung</b> gửi.\n"
        "Spintax <code>{a|b|c}</code> dùng được.",
        back_menu(),
    )


@dp.message(SendFlow.pick_message)
async def sn_save_message(m: Message, state: FSMContext):
    if not _guard(m):
        return
    t = (m.text or "").strip()
    await _try_delete(m)
    if not t:
        return
    _send_sessions.setdefault(m.from_user.id, {})["message"] = t
    await state.clear()

    sess = _send_sessions.get(m.from_user.id, {})
    chat_id = m.chat.id
    mid = _last_bot_msg.get(chat_id)
    text = (
        f"📤  <b>GỬI NGAY</b>\n"
        f"👤 <code>{sess.get('acc','?')}</code>  🎯 <code>{sess.get('target','?')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 4/4</b> — gửi kèm ảnh?"
    )
    files = [f.name for f in IMAGES_DIR.glob("*") if f.is_file()]
    if mid:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=mid,
                text=text, reply_markup=send_pick_image(bool(files)))
            return
        except Exception:
            pass
    sent = await bot.send_message(chat_id, text, reply_markup=send_pick_image(bool(files)))
    _last_bot_msg[chat_id] = sent.message_id


async def _sn_ask_image(c: CallbackQuery):
    files = [f.name for f in IMAGES_DIR.glob("*") if f.is_file()]
    sess = _send_sessions.get(c.from_user.id, {})
    await c.answer()
    await _safe_edit(
        c,
        f"📤  <b>GỬI NGAY</b>\n"
        f"👤 <code>{sess.get('acc','?')}</code>  🎯 <code>{sess.get('target','?')}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Bước 4/4</b> — gửi kèm ảnh?",
        send_pick_image(bool(files)),
    )


@dp.callback_query(F.data == "sn:img_none")
async def cb_sn_img_none(c: CallbackQuery):
    if not _guard(c):
        return
    _send_sessions[c.from_user.id]["image"] = None
    await _sn_confirm(c)


@dp.callback_query(F.data == "sn:img_pick")
async def cb_sn_img_pick(c: CallbackQuery):
    if not _guard(c):
        return
    files = sorted(f.name for f in IMAGES_DIR.glob("*") if f.is_file())
    await c.answer()
    await _safe_edit(
        c,
        "📤  <b>GỬI NGAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Chọn ảnh từ kho:",
        send_pick_image_from_library(files, page=0),
    )


@dp.callback_query(F.data.startswith("sn:img_page:"))
async def cb_sn_img_page(c: CallbackQuery):
    if not _guard(c):
        return
    page = int(c.data.rsplit(":", 1)[1])
    files = sorted(f.name for f in IMAGES_DIR.glob("*") if f.is_file())
    await c.answer()
    await _safe_edit(
        c,
        "📤  <b>GỬI NGAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Chọn ảnh từ kho:",
        send_pick_image_from_library(files, page=page),
    )


@dp.callback_query(F.data.startswith("sn:img_use:"))
async def cb_sn_img_use(c: CallbackQuery):
    if not _guard(c):
        return
    idx = int(c.data.rsplit(":", 1)[1])
    files = sorted(f.name for f in IMAGES_DIR.glob("*") if f.is_file())
    if not (0 <= idx < len(files)):
        await c.answer("Không tìm thấy", show_alert=True)
        return
    _send_sessions[c.from_user.id]["image"] = str(IMAGES_DIR / files[idx])
    await _sn_confirm(c)


@dp.callback_query(F.data == "sn:img_upload")
async def cb_sn_img_upload(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    await state.set_state(SendFlow.pick_image)
    await c.answer()
    await _safe_edit(
        c,
        "📤  <b>GỬI NGAY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Gửi ảnh/file ảnh vào chat. Ảnh này cũng lưu vào kho.",
        back_menu(),
    )


@dp.message(SendFlow.pick_image, F.photo | F.document)
async def sn_save_image(m: Message, state: FSMContext):
    if not _guard(m):
        return
    if m.photo:
        file_id = m.photo[-1].file_id
        ext = ".jpg"
    else:
        file_id = m.document.file_id
        ext = Path(m.document.file_name or "").suffix or ".jpg"
    file = await bot.get_file(file_id)
    dest = IMAGES_DIR / f"{uuid4().hex}{ext}"
    await bot.download_file(file.file_path, dest)
    _send_sessions.setdefault(m.from_user.id, {})["image"] = str(dest)
    await state.clear()
    await _try_delete(m)

    sess = _send_sessions.get(m.from_user.id, {})
    chat_id = m.chat.id
    mid = _last_bot_msg.get(chat_id)
    preview = spintax(sess.get("message", ""))
    if len(preview) > 200:
        preview = preview[:197] + "…"
    text = (
        f"📤  <b>XÁC NHẬN GỬI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Acc: <code>{sess.get('acc','?')}</code>\n"
        f"🎯 Target: <code>{sess.get('target','?')}</code>\n"
        f"🖼 <code>{dest.name}</code>\n\n"
        f"<b>Nội dung:</b>\n"
        f"<i>{preview}</i>"
    )
    if mid:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=mid,
                text=text, reply_markup=send_confirm())
            return
        except Exception:
            pass
    sent = await bot.send_message(chat_id, text, reply_markup=send_confirm())
    _last_bot_msg[chat_id] = sent.message_id


@dp.message(SendFlow.pick_image)
async def sn_bad_image(m: Message):
    if not _guard(m):
        return
    await _try_delete(m)


async def _sn_confirm(c: CallbackQuery):
    sess = _send_sessions.get(c.from_user.id, {})
    preview = spintax(sess.get("message", ""))
    if len(preview) > 200:
        preview = preview[:197] + "…"
    img_line = f"🖼 <code>{Path(sess['image']).name}</code>" if sess.get("image") else "🖼 (không có)"
    await c.answer()
    await _safe_edit(
        c,
        f"📤  <b>XÁC NHẬN GỬI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Acc: <code>{sess.get('acc','?')}</code>\n"
        f"🎯 Target: <code>{sess.get('target','?')}</code>\n"
        f"{img_line}\n\n"
        f"<b>Nội dung (preview):</b>\n"
        f"<i>{preview}</i>",
        send_confirm(),
    )


@dp.callback_query(F.data == "sn:confirm")
async def cb_sn_confirm(c: CallbackQuery):
    if not _guard(c):
        return
    sess = _send_sessions.get(c.from_user.id)
    if not sess or not sess.get("acc") or not sess.get("target") or not sess.get("message"):
        await c.answer("Thiếu dữ liệu", show_alert=True)
        return

    await c.answer("📤 Đang gửi…")
    ok, info = await _do_send_once(sess)

    if ok:
        body = (
            f"✅  <b>ĐÃ GỬI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Acc: <code>{sess['acc']}</code>\n"
            f"🎯 Target: <code>{sess['target']}</code>\n\n"
            f"{info}"
        )
    else:
        body = (
            f"❌  <b>GỬI THẤT BẠI</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Acc: <code>{sess['acc']}</code>\n"
            f"🎯 Target: <code>{sess['target']}</code>\n\n"
            f"<code>{info}</code>"
        )
    _send_sessions.pop(c.from_user.id, None)
    await _wipe_and_menu(c.message.chat.id, extra_ids=[c.message.message_id])
    sent = await bot.send_message(c.message.chat.id, body, reply_markup=main_menu())
    _last_bot_msg[c.message.chat.id] = sent.message_id


async def _do_send_once(sess: dict):
    acc_name = sess["acc"]
    target   = sess["target"]
    message  = spintax(sess["message"])
    image    = sess.get("image")

    worker = _manager.get_worker(acc_name)
    client = None
    we_connected = False

    if worker and worker.client:
        client = worker.client
        try:
            if not client.is_connected():
                await client.connect()
                we_connected = True
        except Exception as e:
            return False, f"connect: {type(e).__name__}: {e}"
    else:
        session_path = SESSIONS_DIR / acc_name
        client = TelegramClient(
            str(session_path), API_ID, API_HASH,
            device_model="Desktop", system_version="Windows 10", app_version="4.16.8",
        )
        try:
            await client.connect()
            we_connected = True
            if not await client.is_user_authorized():
                await client.disconnect()
                return False, "session chưa login hoặc đã hết hạn"
        except Exception as e:
            return False, f"connect: {type(e).__name__}: {e}"

    try:
        t = target.strip()
        if t.startswith("@") or t.startswith("https://t.me/"):
            try:
                entity = await client.get_entity(t)
            except Exception as e:
                return False, f"resolve target: {type(e).__name__}: {e}"
        else:
            entity = t

        if image and Path(image).exists():
            await client.send_file(entity, image, caption=message)
        else:
            await client.send_message(entity, message)

        return True, "Gửi thành công."
    except FloodWaitError as e:
        return False, f"FloodWait {e.seconds}s"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        if we_connected and not worker:
            try:
                await client.disconnect()
            except Exception:
                pass


# =========================================================
#  IMAGES
# =========================================================

@dp.callback_query(F.data == "images_menu")
async def cb_images(c: CallbackQuery):
    if not _guard(c):
        return
    await _render_images(c)


async def _render_images(c: CallbackQuery):
    files = sorted(f.name for f in IMAGES_DIR.glob("*") if f.is_file())
    if not files:
        text = (
            "🖼  <b>KHO ẢNH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Chưa có ảnh. Bấm ➕ Thêm ảnh.</i>"
        )
        kb = images_menu()
    else:
        size = sum((IMAGES_DIR / f).stat().st_size for f in files)
        text = (
            "🖼  <b>DANH SÁCH ẢNH</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"Tổng: <b>{len(files)}</b> ảnh — <b>{size/1024:.1f} KB</b>\n\n"
            "<i>Bấm vào tên để xoá.</i>"
        )
        kb = item_list_menu("img", files, page=0)
    await c.answer()
    await _safe_edit(c, text, kb)


@dp.callback_query(F.data.startswith("img:page:"))
async def cb_img_page(c: CallbackQuery):
    if not _guard(c):
        return
    page = int(c.data.rsplit(":", 1)[1])
    files = sorted(f.name for f in IMAGES_DIR.glob("*") if f.is_file())
    await c.answer()
    await _safe_edit(
        c,
        f"🖼  <b>DANH SÁCH ẢNH</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"Trang <b>{page+1}</b> — tổng <b>{len(files)}</b>",
        item_list_menu("img", files, page=page),
    )


@dp.callback_query(F.data.startswith("img:del:"))
async def cb_img_del(c: CallbackQuery):
    if not _guard(c):
        return
    idx = int(c.data.rsplit(":", 1)[1])
    files = sorted(f.name for f in IMAGES_DIR.glob("*") if f.is_file())
    if 0 <= idx < len(files):
        try:
            (IMAGES_DIR / files[idx]).unlink()
            await c.answer("🗑 Đã xoá")
        except Exception as e:
            await c.answer(f"Lỗi: {e}", show_alert=True)
    await _render_images(c)


@dp.callback_query(F.data == "img:add")
async def cb_img_add(c: CallbackQuery, state: FSMContext):
    if not _guard(c):
        return
    await state.set_state(ImageFlow.photo)
    await c.answer()
    await _safe_edit(
        c,
        "🖼  <b>THÊM ẢNH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Gửi ảnh hoặc file ảnh. Nhiều lần liên tiếp OK.\n"
        "<i>/cancel để thoát.</i>",
        back_menu(),
    )


@dp.message(ImageFlow.photo, F.photo | F.document)
async def img_save(m: Message, state: FSMContext):
    if not _guard(m):
        return
    if m.photo:
        file_id = m.photo[-1].file_id
        ext = ".jpg"
    else:
        file_id = m.document.file_id
        ext = Path(m.document.file_name or "").suffix or ".jpg"
    file = await bot.get_file(file_id)
    dest = IMAGES_DIR / f"{uuid4().hex}{ext}"
    await bot.download_file(file.file_path, dest)
    await _try_delete(m)
    total = len([f for f in IMAGES_DIR.glob("*") if f.is_file()])
    chat_id = m.chat.id
    mid = _last_bot_msg.get(chat_id)
    text = (
        f"🖼  <b>THÊM ẢNH</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Đã lưu <code>{dest.name}</code>\n"
        f"📦 Tổng: <b>{total}</b> ảnh\n\n"
        "Gửi thêm ảnh hoặc <i>/cancel để thoát.</i>"
    )
    if mid:
        try:
            await bot.edit_message_text(
                chat_id=chat_id, message_id=mid,
                text=text, reply_markup=back_menu())
            return
        except Exception:
            pass
    sent = await bot.send_message(chat_id, text, reply_markup=back_menu())
    _last_bot_msg[chat_id] = sent.message_id


@dp.message(ImageFlow.photo)
async def img_bad(m: Message):
    if not _guard(m):
        return
    await _try_delete(m)


@dp.callback_query(F.data == "img:wipe")
async def cb_img_wipe(c: CallbackQuery):
    if not _guard(c):
        return
    n = len([f for f in IMAGES_DIR.glob("*") if f.is_file()])
    await c.answer()
    await _safe_edit(
        c,
        f"🗑  <b>XOÁ TẤT CẢ ẢNH?</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>{n}</b> ảnh sẽ bị xoá vĩnh viễn.",
        confirm_wipe("img"),
    )


@dp.callback_query(F.data == "img:wipe_yes")
async def cb_img_wipe_yes(c: CallbackQuery):
    if not _guard(c):
        return
    n = 0
    for f in IMAGES_DIR.glob("*"):
        if f.is_file():
            try:
                f.unlink()
                n += 1
            except Exception:
                pass
    await c.answer(f"Đã xoá {n} ảnh")
    await _render_images(c)


# =========================================================
#  GENERIC LIST MANAGER
# =========================================================

_CATEGORIES = {
    "target":  {"file": TARGETS_FILE,  "label": "🎯 MỤC TIÊU",     "fsm": ItemFlow.target,  "reload": True},
    "message": {"file": MESSAGES_FILE, "label": "📝 NỘI DUNG TIN", "fsm": ItemFlow.message, "reload": True},
    "bio":     {"file": BIOS_FILE,     "label": "🛡 BIO POOL",     "fsm": ItemFlow.bio,     "reload": True},
    "proxy":   {"file": PROXIES_FILE,  "label": "🌐 PROXY",        "fsm": ItemFlow.proxy,   "reload": False},
}


async def _render_list(c: CallbackQuery, kind: str, page: int = 0):
    cfg = _CATEGORIES[kind]
    items = _lines(cfg["file"])
    if not items:
        text = (
            f"{cfg['label']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Danh sách trống. Bấm ➕ Thêm.</i>"
        )
    else:
        total_pages = (len(items) + PER_PAGE - 1) // PER_PAGE
        text = (
            f"{cfg['label']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Trang <b>{page+1}/{total_pages}</b> — tổng <b>{len(items)}</b> dòng\n\n"
            "<i>Bấm vào dòng để xoá.</i>"
        )
    await c.answer()
    kb = item_list_menu(kind, items, page=page)
    await _safe_edit(c, text, kb)


def _add_prompt(kind: str) -> str:
    tips = {
        "target":  "Mỗi dòng 1 target: <code>@username</code> hoặc <code>https://t.me/...</code>",
        "message": "Mỗi dòng 1 biến thể. Spintax <code>{a|b|c}</code>.",
        "bio":     "Mỗi dòng 1 bio (tối đa 70 ký tự).",
        "proxy":   "Mỗi dòng 1 proxy: <code>socks5://user:pass@host:port</code>",
    }
    label = _CATEGORIES[kind]["label"]
    return (
        f"➕  <b>THÊM — {label}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"{tips[kind]}\n\n"
        "Gửi text (nhiều dòng 1 lúc OK) hoặc file .txt.\n"
        "<i>/cancel để huỷ.</i>"
    )


@dp.callback_query(F.data == "targets_menu")
async def cb_targets(c: CallbackQuery):
    if not _guard(c):
        return
    await _render_list(c, "target", page=0)


@dp.callback_query(F.data == "messages_menu")
async def cb_messages(c: CallbackQuery):
    if not _guard(c):
        return
    await _render_list(c, "message", page=0)


@dp.callback_query(F.data == "bios_menu")
async def cb_bios(c: CallbackQuery):
    if not _guard(c):
        return
    await _render_list(c, "bio", page=0)


@dp.callback_query(F.data == "proxy_menu")
async def cb_proxy(c: CallbackQuery):
    if not _guard(c):
        return
    await _render_list(c, "proxy", page=0)


def _mk_page_handler(k):
    async def handler(c: CallbackQuery):
        if not _guard(c):
            return
        page = int(c.data.rsplit(":", 1)[1])
        await _render_list(c, k, page=page)
    return handler


def _mk_del_handler(k):
    async def handler(c: CallbackQuery):
        if not _guard(c):
            return
        idx = int(c.data.rsplit(":", 1)[1])
        _delete_at(_CATEGORIES[k]["file"], idx)
        if _CATEGORIES[k]["reload"] and _manager:
            _manager.reload_content()
        await _render_list(c, k, page=0)
    return handler


def _mk_add_handler(k):
    async def handler(c: CallbackQuery, state: FSMContext):
        if not _guard(c):
            return
        await state.set_state(_CATEGORIES[k]["fsm"])
        await c.answer()
        await _safe_edit(c, _add_prompt(k), back_menu())
    return handler


def _mk_wipe_handler(k):
    async def handler(c: CallbackQuery):
        if not _guard(c):
            return
        n = len(_lines(_CATEGORIES[k]["file"]))
        await c.answer()
        await _safe_edit(
            c,
            f"🗑  <b>XOÁ TẤT CẢ?</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>{n}</b> dòng sẽ bị xoá.",
            confirm_wipe(k),
        )
    return handler


def _mk_wipe_yes_handler(k):
    async def handler(c: CallbackQuery):
        if not _guard(c):
            return
        n = _wipe(_CATEGORIES[k]["file"])
        if _CATEGORIES[k]["reload"] and _manager:
            _manager.reload_content()
        await c.answer(f"Đã xoá {n} dòng")
        await _render_list(c, k, page=0)
    return handler


for _kind in ("target", "message", "bio", "proxy"):
    dp.callback_query.register(_mk_page_handler(_kind),     F.data.startswith(f"{_kind}:page:"))
    dp.callback_query.register(_mk_del_handler(_kind),      F.data.startswith(f"{_kind}:del:"))
    dp.callback_query.register(_mk_add_handler(_kind),      F.data == f"{_kind}:add")
    dp.callback_query.register(_mk_wipe_handler(_kind),     F.data == f"{_kind}:wipe")
    dp.callback_query.register(_mk_wipe_yes_handler(_kind), F.data == f"{_kind}:wipe_yes")


async def _save_item(m: Message, kind: str, state: FSMContext):
    cfg = _CATEGORIES[kind]
    if m.document:
        file = await bot.get_file(m.document.file_id)
        local = Path(f"/tmp/{uuid4().hex}.txt")
        await bot.download_file(file.file_path, local)
        text = local.read_text(encoding="utf-8")
        local.unlink(missing_ok=True)
    elif m.text:
        text = m.text
    else:
        await _try_delete(m)
        return

    n = _append_lines(cfg["file"], text)
    if cfg["reload"] and _manager:
        _manager.reload_content()
    await state.clear()
    await _try_delete(m)
    await _wipe_and_menu(m.chat.id)
    sent = await bot.send_message(m.chat.id,
        f"✅ Đã thêm vào <b>{cfg['label']}</b> — tổng <b>{n}</b> dòng.",
        reply_markup=main_menu())
    _last_bot_msg[m.chat.id] = sent.message_id


@dp.message(ItemFlow.target)
async def save_target(m: Message, state: FSMContext):
    if not _guard(m):
        return
    await _save_item(m, "target", state)


@dp.message(ItemFlow.message)
async def save_message(m: Message, state: FSMContext):
    if not _guard(m):
        return
    await _save_item(m, "message", state)


@dp.message(ItemFlow.bio)
async def save_bio(m: Message, state: FSMContext):
    if not _guard(m):
        return
    await _save_item(m, "bio", state)


@dp.message(ItemFlow.proxy)
async def save_proxy(m: Message, state: FSMContext):
    if not _guard(m):
        return
    await _save_item(m, "proxy", state)


@dp.callback_query(F.data == "bios:rotate_all")
async def cb_bios_rotate_all(c: CallbackQuery):
    if not _guard(c):
        return
    await c.answer("🛡 Đang đổi…")
    n = await _manager.rotate_bio_all()
    await _wipe_and_menu(c.message.chat.id, extra_ids=[c.message.message_id])
    sent = await bot.send_message(c.message.chat.id,
        f"✅ Đã đổi bio cho <b>{n}</b> tài khoản.", reply_markup=main_menu())
    _last_bot_msg[c.message.chat.id] = sent.message_id


@dp.callback_query(F.data == "settings_menu")
async def cb_settings(c: CallbackQuery):
    if not _guard(c):
        return
    await c.answer()
    await _safe_edit(
        c,
        "⚙️  <b>CÀI ĐẶT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ Delay: <b>{MIN_DELAY}–{MAX_DELAY}s</b>\n"
        f"📊 Cap/ngày/acc: <b>{DAILY_MSG_CAP}</b>\n"
        f"🛡 Đổi bio mỗi: <b>{BIO_ROTATE_EVERY}</b> tin\n"
        f"🌐 Bot proxy: <code>{BOT_PROXY or 'none'}</code>\n\n"
        "<i>Chỉnh trong config.py rồi Ctrl+C, chạy lại.</i>",
        settings_menu(),
    )


async def run_bot():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    await dp.start_polling(bot)

# language: Python, file: bot/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PER_PAGE = 8


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤   GỬI NGAY", callback_data="send_now")],
        [InlineKeyboardButton(text="🚀   BẮT ĐẦU TẤT CẢ", callback_data="start_all")],
        [InlineKeyboardButton(text="⛔   DỪNG TẤT CẢ",   callback_data="stop_all")],
        [
            InlineKeyboardButton(text="⏸ Tạm dừng", callback_data="pause_all"),
            InlineKeyboardButton(text="▶️ Tiếp tục",  callback_data="resume_all"),
        ],
        [
            InlineKeyboardButton(text="📊 Dashboard", callback_data="dashboard"),
            InlineKeyboardButton(text="👥 Tài khoản",  callback_data="accounts"),
        ],
        [
            InlineKeyboardButton(text="🖼 Kho ảnh",   callback_data="images_menu"),
            InlineKeyboardButton(text="📝 Nội dung",  callback_data="messages_menu"),
        ],
        [InlineKeyboardButton(text="🎯 Mục tiêu", callback_data="targets_menu")],
        [
            InlineKeyboardButton(text="🌐 Proxy",     callback_data="proxy_menu"),
            InlineKeyboardButton(text="⚙️ Cài đặt",   callback_data="settings_menu"),
        ],
    ])


def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️  Quay lại", callback_data="back")],
    ])


def accounts_menu(sessions):
    kb = InlineKeyboardBuilder()
    for s in sessions:
        kb.button(text=f"👤  {s}", callback_data=f"acc:show:{s}")
    kb.button(text="➕  Thêm tài khoản", callback_data="acc:add")
    kb.button(text="⬅️  Quay lại", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()


def account_detail_menu(name):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏸ Tạm dừng", callback_data=f"acc:pause:{name}"),
            InlineKeyboardButton(text="▶️ Tiếp tục",  callback_data=f"acc:resume:{name}"),
        ],
        [InlineKeyboardButton(text="✏️  ĐẶT BIO CỤ THỂ", callback_data=f"acc:setbio:{name}")],
        [InlineKeyboardButton(text="🛡 Đổi bio (random pool)", callback_data=f"acc:bio:{name}")],
        [InlineKeyboardButton(text="⬅️ Quay lại",             callback_data="accounts")],
    ])


def images_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕  Thêm ảnh",          callback_data="img:add")],
        [InlineKeyboardButton(text="📋  Xem danh sách ảnh", callback_data="images_menu")],
        [InlineKeyboardButton(text="🗑  Xoá tất cả ảnh",     callback_data="img:wipe")],
        [InlineKeyboardButton(text="⬅️  Quay lại",          callback_data="back")],
    ])


def item_list_menu(kind, items, page=0):
    kb = InlineKeyboardBuilder()
    start = page * PER_PAGE
    chunk = items[start:start + PER_PAGE]
    for i, it in enumerate(chunk):
        idx = start + i
        label = it if len(it) <= 34 else it[:31] + "…"
        kb.button(text=f"🗑  {label}", callback_data=f"{kind}:del:{idx}")
    if page > 0:
        kb.row(InlineKeyboardButton(text="⬅️ Trang trước", callback_data=f"{kind}:page:{page-1}"))
    if start + PER_PAGE < len(items):
        kb.row(InlineKeyboardButton(text="Trang sau ➡️", callback_data=f"{kind}:page:{page+1}"))
    kb.row(InlineKeyboardButton(text="➕  Thêm", callback_data=f"{kind}:add"))
    kb.row(InlineKeyboardButton(text="🗑  Xoá hết", callback_data=f"{kind}:wipe"))
    kb.row(InlineKeyboardButton(text="⬅️  Quay lại", callback_data="back"))
    kb.adjust(1)
    return kb.as_markup()


def confirm_wipe(kind):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑  Xoá hết", callback_data=f"{kind}:wipe_yes"),
            InlineKeyboardButton(text="⬅️  Huỷ",      callback_data="back"),
        ],
    ])


def send_pick_account(sessions):
    kb = InlineKeyboardBuilder()
    for s in sessions:
        kb.button(text=f"👤  {s}", callback_data=f"sn:acc:{s}")
    kb.button(text="⬅️  Huỷ", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()


def send_pick_target(items, page=0):
    kb = InlineKeyboardBuilder()
    start = page * PER_PAGE
    chunk = items[start:start + PER_PAGE]
    for i, it in enumerate(chunk):
        idx = start + i
        label = it if len(it) <= 40 else it[:37] + "…"
        kb.button(text=f"🎯  {label}", callback_data=f"sn:tg:{idx}")
    if page > 0:
        kb.row(InlineKeyboardButton(text="⬅️ Trang trước", callback_data=f"sn:tg_page:{page-1}"))
    if start + PER_PAGE < len(items):
        kb.row(InlineKeyboardButton(text="Trang sau ➡️", callback_data=f"sn:tg_page:{page+1}"))
    kb.row(InlineKeyboardButton(text="✏️  Nhập target khác", callback_data="sn:tg_custom"))
    kb.row(InlineKeyboardButton(text="⬅️  Huỷ", callback_data="back"))
    kb.adjust(1)
    return kb.as_markup()


def send_pick_message(items, page=0):
    kb = InlineKeyboardBuilder()
    start = page * PER_PAGE
    chunk = items[start:start + PER_PAGE]
    for i, it in enumerate(chunk):
        idx = start + i
        label = it if len(it) <= 40 else it[:37] + "…"
        kb.button(text=f"📝  {label}", callback_data=f"sn:msg:{idx}")
    if page > 0:
        kb.row(InlineKeyboardButton(text="⬅️ Trang trước", callback_data=f"sn:msg_page:{page-1}"))
    if start + PER_PAGE < len(items):
        kb.row(InlineKeyboardButton(text="Trang sau ➡️", callback_data=f"sn:msg_page:{page+1}"))
    kb.row(InlineKeyboardButton(text="✏️  Nhập nội dung khác", callback_data="sn:msg_custom"))
    kb.row(InlineKeyboardButton(text="⬅️  Huỷ", callback_data="back"))
    kb.adjust(1)
    return kb.as_markup()


def send_pick_image(has_images: bool):
    rows = [[InlineKeyboardButton(text="⏭  Không kèm ảnh", callback_data="sn:img_none")]]
    if has_images:
        rows.insert(0, [InlineKeyboardButton(text="🖼  Chọn từ kho", callback_data="sn:img_pick")])
    rows.append([InlineKeyboardButton(text="🖼  Gửi ảnh mới", callback_data="sn:img_upload")])
    rows.append([InlineKeyboardButton(text="⬅️  Huỷ",         callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def send_pick_image_from_library(files, page=0):
    kb = InlineKeyboardBuilder()
    start = page * PER_PAGE
    chunk = files[start:start + PER_PAGE]
    for i, f in enumerate(chunk):
        idx = start + i
        label = f if len(f) <= 34 else f[:31] + "…"
        kb.button(text=f"🖼  {label}", callback_data=f"sn:img_use:{idx}")
    if page > 0:
        kb.row(InlineKeyboardButton(text="⬅️ Trang trước", callback_data=f"sn:img_page:{page-1}"))
    if start + PER_PAGE < len(files):
        kb.row(InlineKeyboardButton(text="Trang sau ➡️", callback_data=f"sn:img_page:{page+1}"))
    kb.row(InlineKeyboardButton(text="⬅️  Huỷ", callback_data="back"))
    kb.adjust(1)
    return kb.as_markup()


def send_confirm():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤  BẮN NGAY", callback_data="sn:confirm")],
        [InlineKeyboardButton(text="⬅️  Huỷ",      callback_data="back")],
    ])


def settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️  Quay lại", callback_data="back")],
    ])

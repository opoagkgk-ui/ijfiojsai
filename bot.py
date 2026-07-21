import os
import logging
import random
import json
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==================== ТОКЕН ====================
TOKEN = os.environ.get("API_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения API_TOKEN не установлена!")

# ==================== АДМИН ID ====================
ADMIN_ID = 8371473442

# ==================== ЛОГИРОВАНИЕ ====================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ==================== ФАЙЛЫ ДАННЫХ ====================
CARDS_FILE = "cards_data.json"
USERS_FILE = "users_collection.json"
MESSAGES_FILE = "user_messages.json"

# ==================== ЗАГРУЗКА/СОХРАНЕНИЕ ====================
def load_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==================== ДАННЫЕ КАРТОЧЕК ====================
DEFAULT_CARDS = {
    # Обычные (1-3)
    "1": {"name": "Карточка 1", "rarity": "обычная", "emoji": "🟫"},
    "2": {"name": "Карточка 2", "rarity": "обычная", "emoji": "🟫"},
    "3": {"name": "Карточка 3", "rarity": "обычная", "emoji": "🟫"},
    # Редкие (4-6)
    "4": {"name": "Карточка 4", "rarity": "редкая", "emoji": "🟦"},
    "5": {"name": "Карточка 5", "rarity": "редкая", "emoji": "🟦"},
    "6": {"name": "Карточка 6", "rarity": "редкая", "emoji": "🟦"},
    # Эпические (7-9)
    "7": {"name": "Карточка 7", "rarity": "эпическая", "emoji": "🟪"},
    "8": {"name": "Карточка 8", "rarity": "эпическая", "emoji": "🟪"},
    "9": {"name": "Карточка 9", "rarity": "эпическая", "emoji": "🟪"},
    # Мифические (10-12)
    "10": {"name": "Карточка 10", "rarity": "мифическая", "emoji": "🌟"},
    "11": {"name": "Карточка 11", "rarity": "мифическая", "emoji": "🌟"},
    "12": {"name": "Карточка 12", "rarity": "мифическая", "emoji": "🌟"},
}

# ==================== КОЛОДЫ ====================
PACKS = {
    "common": {
        "name": "Обычная колода",
        "emoji": "📦",
        "rewards": {
            "обычная": 76,
            "редкая": 22,
            "эпическая": 2,
            "мифическая": 0
        }
    },
    "rare": {
        "name": "Редкая колода",
        "emoji": "📦",
        "rewards": {
            "редкая": 73,
            "эпическая": 30,
            "обычная": 6.5,
            "мифическая": 0.5
        }
    },
    "epic": {
        "name": "Эпическая колода",
        "emoji": "📦",
        "rewards": {
            "эпическая": 68,
            "редкая": 22,
            "мифическая": 10,
            "обычная": 0
        }
    }
}

# ==================== ЗАГРУЗКА КАРТОЧЕК ====================
def load_cards():
    data = load_json(CARDS_FILE)
    if not data:
        data = DEFAULT_CARDS
        save_json(CARDS_FILE, data)
    return data

# ==================== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ====================
def get_user_data(user_id):
    users = load_json(USERS_FILE)
    user_id_str = str(user_id)
    if user_id_str not in users:
        users[user_id_str] = {
            "cards": [],
            "packs": {
                "common": 0,
                "rare": 0,
                "epic": 0
            },
            "messages": 0,
            "total_opens": 0,
            "last_open": None,
            "last_common_pack": 0,
            "last_rare_pack": 0,
            "last_epic_pack": 0
        }
        save_json(USERS_FILE, users)
    return users[user_id_str]

def save_user_data(user_id, data):
    users = load_json(USERS_FILE)
    users[str(user_id)] = data
    save_json(USERS_FILE, users)

def add_messages(user_id, count=1):
    """Добавляет сообщения пользователю и выдаёт колоды при достижении порогов."""
    data = get_user_data(user_id)
    data["messages"] += count
    
    # Проверяем, сколько колод нужно выдать
    packs_to_add = {"common": 0, "rare": 0, "epic": 0}
    
    # Обычные колоды за каждые 50 сообщений
    common_count = data["messages"] // 50
    packs_to_add["common"] = common_count - data.get("last_common_pack", 0)
    
    # Редкие колоды за каждые 150 сообщений
    rare_count = data["messages"] // 150
    packs_to_add["rare"] = rare_count - data.get("last_rare_pack", 0)
    
    # Эпические колоды за каждые 250 сообщений
    epic_count = data["messages"] // 250
    packs_to_add["epic"] = epic_count - data.get("last_epic_pack", 0)
    
    # Обновляем последние выданные колоды
    if packs_to_add["common"] > 0:
        data["last_common_pack"] = common_count
    if packs_to_add["rare"] > 0:
        data["last_rare_pack"] = rare_count
    if packs_to_add["epic"] > 0:
        data["last_epic_pack"] = epic_count
    
    # Добавляем колоды в инвентарь
    for pack_type, count in packs_to_add.items():
        if count > 0:
            data["packs"][pack_type] += count
    
    save_user_data(user_id, data)
    return packs_to_add

def add_packs_manual(user_id, pack_type, count):
    """Админская выдача колод."""
    data = get_user_data(user_id)
    if pack_type not in data["packs"]:
        return False, "❌ Неизвестный тип колоды!"
    data["packs"][pack_type] += count
    save_user_data(user_id, data)
    return True, f"✅ Выдано {count} колод типа '{pack_type}' пользователю {user_id}!"

def open_pack(user_id, pack_type):
    """Открывает колоду и возвращает полученные карточки."""
    data = get_user_data(user_id)
    
    if data["packs"].get(pack_type, 0) <= 0:
        return None, "❌ У тебя нет таких колод!"
    
    # Убираем одну колоду
    data["packs"][pack_type] -= 1
    
    # Определяем, какая карточка выпала
    pack_data = PACKS.get(pack_type)
    if not pack_data:
        return None, "❌ Неизвестный тип колоды!"
    
    rewards = pack_data["rewards"]
    rarity = roll_rarity(rewards)
    
    # Выбираем случайную карточку этой редкости
    cards = load_cards()
    available_cards = [card_id for card_id, card in cards.items() if card["rarity"] == rarity]
    
    if not available_cards:
        return None, f"❌ Нет карточек редкости {rarity}!"
    
    card_id = random.choice(available_cards)
    card = cards[card_id]
    
    # Добавляем карточку пользователю
    data["cards"].append(card_id)
    data["total_opens"] += 1
    data["last_open"] = datetime.now().isoformat()
    
    save_user_data(user_id, data)
    
    return card_id, card

def roll_rarity(rewards):
    """Определяет редкость карточки на основе шансов."""
    multiplier = 10
    total = sum(int(v * multiplier) for v in rewards.values())
    roll = random.randint(1, total)
    
    cumulative = 0
    for rarity, chance in rewards.items():
        chance_int = int(chance * multiplier)
        cumulative += chance_int
        if roll <= cumulative:
            return rarity
    
    return "обычная"

def get_collection_stats(user_id):
    data = get_user_data(user_id)
    cards = load_cards()
    
    total = len(data["cards"])
    unique = len(set(data["cards"]))
    available = len(cards)
    
    rarity_counts = {"обычная": 0, "редкая": 0, "эпическая": 0, "мифическая": 0}
    for card_id in data["cards"]:
        card = cards.get(card_id, {})
        rarity = card.get("rarity", "обычная")
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
    
    return {
        "total": total,
        "unique": unique,
        "available": available,
        "rarity_counts": rarity_counts,
        "packs": data["packs"],
        "messages": data["messages"],
        "opens": data["total_opens"]
    }

def get_user_info(user_id):
    """Получает информацию о пользователе для админа."""
    data = get_user_data(user_id)
    return {
        "cards_count": len(data["cards"]),
        "packs": data["packs"],
        "messages": data["messages"],
        "opens": data["total_opens"]
    }

# ==================== КОМАНДЫ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    
    text = f"👋 Привет, {user.first_name}!\n\n"
    text += "🃏 **Добро пожаловать в бот-коллекцию карточек!**\n\n"
    text += "📌 **Команды:**\n"
    text += "/start — это сообщение\n"
    text += "/help — помощь\n"
    text += "/inv — инвентарь (колоды)\n"
    text += "/open <тип> — открыть колоду (common/rare/epic)\n"
    text += "/collection — моя коллекция\n"
    text += "/stats — статистика\n"
    text += "/card <id> — посмотреть карточку\n"
    
    if is_admin:
        text += "\n👑 **Админ-команды:**\n"
        text += "/give <user_id> <тип> <количество> — выдать колоды\n"
        text += "/admin_info <user_id> — информация о пользователе\n"
        text += "/admin_list — список пользователей\n"
    
    text += "\n📦 **Колоды выдаются за активность:**\n"
    text += "• Обычная — за каждые 50 сообщений\n"
    text += "• Редкая — за каждые 150 сообщений\n"
    text += "• Эпическая — за каждые 250 сообщений"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    
    text = "📖 **Помощь:**\n\n"
    text += "/start — приветствие\n"
    text += "/help — эта справка\n"
    text += "/inv — посмотреть инвентарь\n"
    text += "/open common — открыть обычную колоду\n"
    text += "/open rare — открыть редкую колоду\n"
    text += "/open epic — открыть эпическую колоду\n"
    text += "/collection — показать коллекцию\n"
    text += "/stats — статистика\n"
    text += "/card <id> — информация о карточке\n"
    
    if is_admin:
        text += "\n👑 **Админ-команды:**\n"
        text += "/give <user_id> <тип> <количество> — выдать колоды\n"
        text += "  Типы: common, rare, epic\n"
        text += "  Пример: `/give 123456789 common 5`\n"
        text += "/admin_info <user_id> — информация о пользователе\n"
        text += "/admin_list — список пользователей\n"
    
    text += "\n📦 **Редкости карточек:**\n"
    text += "⬜ Обычная\n"
    text += "🟦 Редкая\n"
    text += "🟪 Эпическая\n"
    text += "🌟 Мифическая"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ==================== АДМИН-КОМАНДЫ ====================
async def give_packs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выдаёт колоды пользователю (только для админа)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав для этой команды!")
        return
    
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Использование: `/give <user_id> <тип> <количество>`\n"
            "Типы: common, rare, epic\n"
            "Пример: `/give 123456789 common 5`",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(args[0])
        pack_type = args[1].lower()
        count = int(args[2])
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! ID и количество должны быть числами.")
        return
    
    if pack_type not in ["common", "rare", "epic"]:
        await update.message.reply_text("❌ Неизвестный тип колоды! Доступны: common, rare, epic")
        return
    
    if count <= 0:
        await update.message.reply_text("❌ Количество должно быть больше 0!")
        return
    
    success, msg = add_packs_manual(target_user_id, pack_type, count)
    await update.message.reply_text(msg)

async def admin_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о пользователе (только для админа)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав для этой команды!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ Использование: `/admin_info <user_id>`", parse_mode="Markdown")
        return
    
    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")
        return
    
    info = get_user_info(target_user_id)
    
    await update.message.reply_text(
        f"👤 **Информация о пользователе:** `{target_user_id}`\n\n"
        f"🃏 Карточек: {info['cards_count']}\n"
        f"📦 Колод в инвентаре:\n"
        f"  • Обычных: {info['packs'].get('common', 0)}\n"
        f"  • Редких: {info['packs'].get('rare', 0)}\n"
        f"  • Эпических: {info['packs'].get('epic', 0)}\n"
        f"💬 Сообщений: {info['messages']}\n"
        f"📦 Открыто колод: {info['opens']}",
        parse_mode="Markdown"
    )

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех пользователей (только для админа)."""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ У тебя нет прав для этой команды!")
        return
    
    users = load_json(USERS_FILE)
    
    if not users:
        await update.message.reply_text("📭 Пока нет пользователей!")
        return
    
    # Сортируем по количеству сообщений
    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("messages", 0),
        reverse=True
    )[:20]  # Показываем топ-20
    
    text = "👥 **Топ-20 пользователей:**\n\n"
    for idx, (user_id, data) in enumerate(sorted_users, 1):
        cards_count = len(data.get("cards", []))
        messages = data.get("messages", 0)
        text += f"{idx}. `{user_id}` — {messages} сообщений, {cards_count} карточек\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ==================== ОБЫЧНЫЕ КОМАНДЫ ====================
async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает инвентарь (колоды)."""
    user_id = update.effective_user.id
    stats = get_collection_stats(user_id)
    
    packs = stats["packs"]
    
    kb = []
    if packs.get("common", 0) > 0:
        kb.append([InlineKeyboardButton(f"📦 Обычная ({packs['common']})", callback_data="open_common")])
    if packs.get("rare", 0) > 0:
        kb.append([InlineKeyboardButton(f"📦 Редкая ({packs['rare']})", callback_data="open_rare")])
    if packs.get("epic", 0) > 0:
        kb.append([InlineKeyboardButton(f"📦 Эпическая ({packs['epic']})", callback_data="open_epic")])
    
    if not kb:
        await update.message.reply_text(
            "📭 **Инвентарь пуст!**\n\n"
            "Колоды выдаются за активность в чате:\n"
            "• Обычная — за 50 сообщений\n"
            "• Редкая — за 150 сообщений\n"
            "• Эпическая — за 250 сообщений",
            parse_mode="Markdown"
        )
        return
    
    kb.append([InlineKeyboardButton("🔄 Обновить", callback_data="refresh_inv")])
    
    await update.message.reply_text(
        f"📦 **Твой инвентарь:**\n\n"
        f"• Обычные колоды: {packs.get('common', 0)}\n"
        f"• Редкие колоды: {packs.get('rare', 0)}\n"
        f"• Эпические колоды: {packs.get('epic', 0)}\n\n"
        f"📊 Всего сообщений: {stats['messages']}",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown"
    )

async def open_pack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает колоду по команде /open <тип>."""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "❌ Укажи тип колоды:\n"
            "`/open common` — обычная\n"
            "`/open rare` — редкая\n"
            "`/open epic` — эпическая",
            parse_mode="Markdown"
        )
        return
    
    pack_type = args[0].lower()
    if pack_type not in ["common", "rare", "epic"]:
        await update.message.reply_text("❌ Неизвестный тип колоды! Доступны: common, rare, epic")
        return
    
    result, card = open_pack(user_id, pack_type)
    if result is None:
        await update.message.reply_text(card)
        return
    
    card_data = load_cards()
    card_info_data = card_data.get(result, {})
    
    rarity_emoji = {"обычная": "⬜", "редкая": "🟦", "эпическая": "🟪", "мифическая": "🌟"}.get(card_info_data.get("rarity", "обычная"), "⬜")
    
    await update.message.reply_text(
        f"🎴 **Ты открыл колоду!**\n\n"
        f"{rarity_emoji} **{card_info_data.get('name', 'Неизвестно')}**\n"
        f"📊 Редкость: {card_info_data.get('rarity', 'обычная')}\n"
        f"🆔 ID: `{result}`\n\n"
        f"📦 Осталось колод:\n"
        f"• Обычных: {get_collection_stats(user_id)['packs'].get('common', 0)}\n"
        f"• Редких: {get_collection_stats(user_id)['packs'].get('rare', 0)}\n"
        f"• Эпических: {get_collection_stats(user_id)['packs'].get('epic', 0)}",
        parse_mode="Markdown"
    )

async def collection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает коллекцию карточек."""
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    cards = load_cards()
    
    if not data["cards"]:
        await update.message.reply_text(
            "📭 У тебя пока нет карточек!\n"
            "Открывай колоды через `/inv` или `/open`",
            parse_mode="Markdown"
        )
        return
    
    grouped = {"обычная": [], "редкая": [], "эпическая": [], "мифическая": []}
    
    for card_id in set(data["cards"]):
        card = cards.get(card_id, {})
        rarity = card.get("rarity", "обычная")
        count = data["cards"].count(card_id)
        grouped[rarity].append((card_id, card, count))
    
    result = "🎴 **Моя коллекция:**\n\n"
    rarity_emoji = {"обычная": "⬜", "редкая": "🟦", "эпическая": "🟪", "мифическая": "🌟"}
    
    for rarity in ["мифическая", "эпическая", "редкая", "обычная"]:
        if grouped[rarity]:
            result += f"{rarity_emoji.get(rarity, '')} **{rarity.upper()}**\n"
            for card_id, card, count in grouped[rarity]:
                result += f"  {card.get('emoji', '🃏')} {card.get('name', 'Неизвестно')} ×{count}\n"
            result += "\n"
    
    stats = get_collection_stats(user_id)
    result += f"📊 **Всего:** {stats['total']} | **Уникальных:** {stats['unique']} / {stats['available']}"
    
    await update.message.reply_text(result, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику."""
    user_id = update.effective_user.id
    stats = get_collection_stats(user_id)
    data = get_user_data(user_id)
    
    await update.message.reply_text(
        f"📊 **Твоя статистика:**\n\n"
        f"🃏 **Всего карточек:** {stats['total']}\n"
        f"⭐ **Уникальных:** {stats['unique']} / {stats['available']}\n"
        f"📊 **По редкости:**\n"
        f"  • Обычных: {stats['rarity_counts'].get('обычная', 0)}\n"
        f"  • Редких: {stats['rarity_counts'].get('редкая', 0)}\n"
        f"  • Эпических: {stats['rarity_counts'].get('эпическая', 0)}\n"
        f"  • Мифических: {stats['rarity_counts'].get('мифическая', 0)}\n"
        f"📦 **Колод в инвентаре:**\n"
        f"  • Обычных: {stats['packs'].get('common', 0)}\n"
        f"  • Редких: {stats['packs'].get('rare', 0)}\n"
        f"  • Эпических: {stats['packs'].get('epic', 0)}\n"
        f"💬 **Всего сообщений:** {stats['messages']}\n"
        f"📦 **Всего открыто:** {stats['opens']}\n"
        f"📅 **Последнее открытие:** {data.get('last_open', 'никогда')[:19] if data.get('last_open') else 'никогда'}",
        parse_mode="Markdown"
    )

async def card_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о карточке."""
    args = context.args
    if not args:
        await update.message.reply_text("❌ Напиши ID карточки: `/card 1`", parse_mode="Markdown")
        return
    
    card_id = args[0]
    cards = load_cards()
    card = cards.get(card_id)
    
    if not card:
        await update.message.reply_text(f"❌ Карточка с ID `{card_id}` не найдена!", parse_mode="Markdown")
        return
    
    rarity_emoji = {"обычная": "⬜", "редкая": "🟦", "эпическая": "🟪", "мифическая": "🌟"}.get(card.get("rarity", "обычная"), "⬜")
    
    await update.message.reply_text(
        f"{rarity_emoji} **{card.get('name', 'Неизвестно')}**\n\n"
        f"🆔 ID: `{card_id}`\n"
        f"📊 Редкость: {card.get('rarity', 'обычная')}\n"
        f"{card.get('emoji', '🃏')} Символ: {card.get('emoji', '🃏')}",
        parse_mode="Markdown"
    )

# ==================== ОБРАБОТЧИК КНОПОК ====================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "refresh_inv":
        await inventory(update, context)
        return
    
    if data.startswith("open_"):
        pack_type = data.replace("open_", "")
        result, card = open_pack(user_id, pack_type)
        
        if result is None:
            await query.edit_message_text(card)
            return
        
        card_data = load_cards()
        card_info_data = card_data.get(result, {})
        
        rarity_emoji = {"обычная": "⬜", "редкая": "🟦", "эпическая": "🟪", "мифическая": "🌟"}.get(card_info_data.get("rarity", "обычная"), "⬜")
        
        await query.edit_message_text(
            f"🎴 **Ты открыл колоду!**\n\n"
            f"{rarity_emoji} **{card_info_data.get('name', 'Неизвестно')}**\n"
            f"📊 Редкость: {card_info_data.get('rarity', 'обычная')}\n"
            f"🆔 ID: `{result}`\n\n"
            f"📦 Осталось колод:\n"
            f"• Обычных: {get_collection_stats(user_id)['packs'].get('common', 0)}\n"
            f"• Редких: {get_collection_stats(user_id)['packs'].get('rare', 0)}\n"
            f"• Эпических: {get_collection_stats(user_id)['packs'].get('epic', 0)}",
            parse_mode="Markdown"
        )
        return

# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Считает сообщения пользователя."""
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    
    if update.message.text.startswith('/'):
        return
    
    packs_added = add_messages(user_id, 1)
    
    if any(packs_added.values()):
        msg = "🎁 **Ты получил колоды за активность!**\n\n"
        if packs_added["common"] > 0:
            msg += f"📦 Обычная ×{packs_added['common']} (за 50 сообщений)\n"
        if packs_added["rare"] > 0:
            msg += f"📦 Редкая ×{packs_added['rare']} (за 150 сообщений)\n"
        if packs_added["epic"] > 0:
            msg += f"📦 Эпическая ×{packs_added['epic']} (за 250 сообщений)\n"
        msg += "\nИспользуй `/inv` чтобы открыть!"
        await update.message.reply_text(msg, parse_mode="Markdown")

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Неизвестная команда.\n"
        "Используй /help для списка команд."
    )

# ==================== ЗАПУСК ====================
def main():
    print("🃏 Бот-коллекция карточек запускается...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    
    load_cards()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("inv", inventory))
    app.add_handler(CommandHandler("open", open_pack_command))
    app.add_handler(CommandHandler("collection", collection))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("card", card_info))
    
    # Админ-команды
    app.add_handler(CommandHandler("give", give_packs))
    app.add_handler(CommandHandler("admin_info", admin_info))
    app.add_handler(CommandHandler("admin_list", admin_list))
    
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    print("✅ Бот готов!")
    app.run_polling()

if __name__ == "__main__":
    main()

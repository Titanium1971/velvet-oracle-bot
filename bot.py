# bot.py
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass
class UserSession:
    mode: Optional[str] = None           # ex: "DECOUVERTE", "DISCIPLINE", "EXCELLENCE"
    level: Optional[int] = None          # 1 à 5
    collection_size: int = 10            # 10, 30 ou 60
    current_index: int = 0               # index du rituel dans la collection
    streak: int = 0                      # rituels d'affilée sans interruption
    correct_count: int = 0
    wrong_count: int = 0
    in_ritual: bool = False              # True si un rituel est en cours
    last_ritual_id: Optional[str] = None # pour reprendre en cas d’interruption

SESSIONS: Dict[int, UserSession] = {}

MESSAGES = {
    "SYS_START": "Velvet Oracle s’ouvre.\nUn espace réservé à ceux qui cherchent à affiner leur esprit.\nPrêt à entrer ?",
    "SYS_WELCOME": "Bienvenue dans Velvet Oracle.\nIci, chaque rituel devient un miroir.\nChaque réponse, un tracé vers plus de maîtrise.",
    "SYS_SELECT_MODE": "Choisis la voie que tu souhaites arpenter.\nTrois chemins, trois rythmes.\nLe tien t’attend.",
    "SYS_SELECT_LEVEL": "Quel degré d’intensité veux-tu affronter ?\nDu premier éclat… jusqu’au sommet.\nSélectionne ton niveau.",
    # … ici tu injecteras progressivement tous tes SYS_*
}

import json
import os
from typing import Any, List

RITUALS: Dict[int, List[Dict[str, Any]]] = {}  # 10 → [...], 30 → [...], 60 → [...]

def load_rituals():
    base_dir = os.path.dirname(__file__)
    for size in (10, 30, 60):
        path = os.path.join(base_dir, f"rituals_{size}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                RITUALS[size] = json.load(f)
        else:
            RITUALS[size] = []

{
  "id": "RIT_10_001",
  "prompt": "Texte du rituel…",
  "choices": ["A", "B", "C", "D"],
  "answer_index": 1
}

def get_session(chat_id: int) -> UserSession:
    if chat_id not in SESSIONS:
        SESSIONS[chat_id] = UserSession()
    return SESSIONS[chat_id]

def msg(key: str) -> str:
    return MESSAGES.get(key, f"[{key}]")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

# --- HANDLER /start ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = get_session(chat_id)
    session.__dict__.update(UserSession().__dict__)  # reset propre de la session

    await update.message.reply_text(msg("SYS_START"))
    await update.message.reply_text(msg("SYS_WELCOME"))

    # On propose les modes
    keyboard = [
        [
            InlineKeyboardButton("Découverte", callback_data="MODE_DECOUVERTE"),
            InlineKeyboardButton("Discipline", callback_data="MODE_DISCIPLINE"),
            InlineKeyboardButton("Excellence", callback_data="MODE_EXCELLENCE"),
        ]
    ]
    await update.message.reply_text(
        msg("SYS_SELECT_MODE"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- HANDLER sélection de mode ---

async def mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    session = get_session(chat_id)

    data = query.data  # ex: MODE_DECOUVERTE
    session.mode = data.replace("MODE_", "")

    # Message d’introduction du mode
    if session.mode == "DECOUVERTE":
        await query.message.reply_text(msg("SYS_MODE_DECO"))
    elif session.mode == "DISCIPLINE":
        await query.message.reply_text(msg("SYS_MODE_DISC"))
    elif session.mode == "EXCELLENCE":
        await query.message.reply_text(msg("SYS_MODE_EXC"))

    # On enchaîne sur la sélection du niveau
    keyboard = [
        [
            InlineKeyboardButton("Niveau I", callback_data="LEVEL_1"),
            InlineKeyboardButton("II", callback_data="LEVEL_2"),
            InlineKeyboardButton("III", callback_data="LEVEL_3"),
            InlineKeyboardButton("IV", callback_data="LEVEL_4"),
            InlineKeyboardButton("V", callback_data="LEVEL_5"),
        ]
    ]
    await query.message.reply_text(
        msg("SYS_SELECT_LEVEL"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- HANDLER sélection de niveau ---

async def level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    session = get_session(chat_id)

    data = query.data  # ex: LEVEL_3
    session.level = int(data.split("_")[1])

    # Intro du niveau
    sys_key = f"SYS_LEVEL_{session.level}"
    await query.message.reply_text(msg(sys_key))

    # Définir la première collection (10 par défaut pour tous les modes au début)
    session.collection_size = 10
    session.current_index = 0
    session.streak = 0
    session.in_ritual = False

    # Intro Collection 10
    await query.message.reply_text(msg("SYS_ENTER_10"))

    # Lancer le premier rituel
    await start_next_ritual(chat_id, context)

async def start_next_ritual(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(chat_id)
    rituals = RITUALS.get(session.collection_size, [])
    if session.current_index >= len(rituals):
        # Fin de collection
        await handle_collection_end(chat_id, context)
        return

    ritual = rituals[session.current_index]
    session.in_ritual = True
    session.last_ritual_id = ritual["id"]

    # Construction des boutons de réponses
    buttons = []
    for idx, choice_text in enumerate(ritual["choices"]):
        buttons.append([InlineKeyboardButton(choice_text, callback_data=f"ANSWER_{idx}")])

    await context.bot.send_message(
        chat_id=chat_id,
        text=ritual["prompt"],
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    session = get_session(chat_id)

    if not session.in_ritual:
        # Pas de rituel en cours → message navigation
        await query.message.reply_text(msg("SYS_ERR_EMPTY"))
        return

    rituals = RITUALS.get(session.collection_size, [])
    if session.current_index >= len(rituals):
        await handle_collection_end(chat_id, context)
        return

    ritual = rituals[session.collection_size][session.current_index]  # à adapter selon ta structure réelle

    data = query.data  # ex: ANSWER_1
    answer_index = int(data.split("_")[1])

    if answer_index == ritual["answer_index"]:
        # Bonne réponse
        session.correct_count += 1
        session.streak += 1
        await query.message.reply_text(msg("SYS_CORRECT"))
        # Intensité (streak)
        await maybe_send_streak_message(chat_id, context, session.streak)
    else:
        # Mauvaise réponse
        session.wrong_count += 1
        session.streak = 0
        await query.message.reply_text(msg("SYS_WRONG"))

    # Clôture du rituel
    await query.message.reply_text(msg("SYS_END_RITUAL"))
    session.in_ritual = False
    session.current_index += 1

    # Enchaîner vers le prochain
    await start_next_ritual(chat_id, context)

async def maybe_send_streak_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE, streak: int):
    mapping = {
        3: "SYS_STREAK_3",
        5: "SYS_STREAK_5",
        10: "SYS_STREAK_10",
        20: "SYS_STREAK_20",
        30: "SYS_STREAK_30",
        50: "SYS_STREAK_50",
    }
    key = mapping.get(streak)
    if key:
        await context.bot.send_message(chat_id=chat_id, text=msg(key))

async def handle_collection_end(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(chat_id)
    size = session.collection_size

    if size == 10:
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_FIN_10"))
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_SWITCH_10_30"))
        session.collection_size = 30
        session.current_index = 0
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_ENTER_30"))
        await start_next_ritual(chat_id, context)

    elif size == 30:
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_FIN_30"))
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_SWITCH_30_60"))
        session.collection_size = 60
        session.current_index = 0
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_ENTER_60"))
        await start_next_ritual(chat_id, context)

    elif size == 60:
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_FIN_60"))
        await context.bot.send_message(chat_id=chat_id, text=msg("SYS_SWITCH_60_CYCLE"))
        # Ici soit on repart sur 10, soit on laisse l’utilisateur choisir.
        session.collection_size = 10
        session.current_index = 0
        session.streak = 0
        session.in_ritual = False

async def main():
    load_rituals()

    app = ApplicationBuilder().token("TON_TELEGRAM_TOKEN").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(mode_selection, pattern="^MODE_"))
    app.add_handler(CallbackQueryHandler(level_selection, pattern="^LEVEL_"))
    app.add_handler(CallbackQueryHandler(answer_handler, pattern="^ANSWER_"))

    # Ici tu pourras ajouter d’autres handlers pour navigation, reset, menu, etc.

    await app.run_polling()


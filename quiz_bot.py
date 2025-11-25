import sys
import types

# Patch pour Python 3.13 : certains packages attendent encore le module standard 'imghdr'
try:
    import imghdr  # type: ignore
except ModuleNotFoundError:
    imghdr = types.ModuleType("imghdr")

    def what(file, h=None):
        return None

    imghdr.what = what
    sys.modules["imghdr"] = imghdr

import os
import logging
from typing import Dict, Any, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

# ----------------------------------------------------
# CONFIGURATION DE BASE
# ----------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ⚠️ METS TON TOKEN ICI (ENTRE GUILLEMETS)
BOT_TOKEN = "8360941682:AAHe21iKKvbfVrty43-TspiYGU8vXGcS008"

# Token de paiement (optionnel pour l’instant)
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "TON_PROVIDER_TOKEN_ICI")

# ----------------------------------------------------
# QUESTIONS DU QUIZ (MVP)
# ----------------------------------------------------

QUESTIONS: List[Dict[str, Any]] = [
    {
        "question": "Dans quelle ville se trouve la Tour Eiffel ?",
        "options": ["Rome", "Paris", "Londres", "Madrid"],
        "correct_index": 1,
    },
    {
        "question": "Qui a peint la Joconde ?",
        "options": ["Picasso", "Van Gogh", "Léonard de Vinci", "Monet"],
        "correct_index": 2,
    },
    {
        "question": "Combien font 9 x 7 ?",
        "options": ["54", "56", "63", "72"],
        "correct_index": 2,
    },
]

# ----------------------------------------------------
# ETAT UTILISATEUR
# ----------------------------------------------------

def init_user_state(context: CallbackContext) -> None:
    user_data = context.user_data
    user_data.setdefault("score", 0)
    user_data.setdefault("current_q_index", 0)
    user_data.setdefault("credits", 3)  # 3 parties offertes
    user_data.setdefault("games_played", 0)


# ----------------------------------------------------
# ENVOI DES QUESTIONS & FIN DE PARTIE
# ----------------------------------------------------

def send_question(update: Update, context: CallbackContext) -> None:
    user_data = context.user_data
    q_index = user_data["current_q_index"]

    if q_index >= len(QUESTIONS):
        end_game(update, context)
        return

    question = QUESTIONS[q_index]
    options = question["options"]

    keyboard = [
        [InlineKeyboardButton(text=opt, callback_data=f"answer:{q_index}:{i}")]
        for i, opt in enumerate(options)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        update.callback_query.edit_message_text(
            text=f"❓ {question['question']}",
            reply_markup=reply_markup,
        )
    elif update.message:
        update.message.reply_text(
            text=f"❓ {question['question']}",
            reply_markup=reply_markup,
        )


def end_game(update: Update, context: CallbackContext) -> None:
    user_data = context.user_data
    score = user_data.get("score", 0)
    total = len(QUESTIONS)

    msg = (
        "🎉 Partie terminée !\n\n"
        f"Score : {score} / {total}\n"
    )

    user_data["games_played"] += 1
    user_data["credits"] = max(user_data["credits"] - 1, 0)
    msg += f"Crédits restants : {user_data['credits']}\n"

    if user_data["credits"] <= 0:
        msg += (
            "\n💎 Vous n'avez plus de jetons Velvet.\n"
            "Utilisez /buy_credits pour recharger."
        )

    if update.callback_query:
        update.callback_query.edit_message_text(msg)
    elif update.message:
        update.message.reply_text(msg)

    user_data["score"] = 0
    user_data["current_q_index"] = 0


# ----------------------------------------------------
# COMMANDES PRINCIPALES
# ----------------------------------------------------

def start(update: Update, context: CallbackContext) -> None:
    init_user_state(context)
    user_data = context.user_data

    msg = (
        "🎩 *Bienvenue dans Velvet Oracle.*\n\n"
        "Ici, chaque question ouvre une porte.\n"
        "Chaque bonne réponse révèle un peu plus de votre discernement.\n\n"
        "Vous entrez dans un quiz réservé à celles et ceux qui apprécient la "
        "précision, la maîtrise\n"
        "et le silence des cercles choisis.\n\n"
        f"_Jetons Velvet disponibles :_ *{user_data['credits']}*\n\n"
        "• 🎯 */quiz* — lancer une partie\n"
        "• 💎 */buy_credits* — acquérir des jetons Velvet\n\n"
        "Prenez place. L’Oracle vous attend."
    )

    update.message.reply_markdown(msg)


def quiz(update: Update, context: CallbackContext) -> None:
    init_user_state(context)
    user_data = context.user_data

    if user_data["credits"] <= 0:
        update.message.reply_text(
            "💡 Vous n'avez plus de jetons Velvet.\n"
            "Utilisez /buy_credits pour recharger et continuer à jouer."
        )
        return

    user_data["score"] = 0
    user_data["current_q_index"] = 0
    send_question(update, context)


# ----------------------------------------------------
# GESTION DES RÉPONSES AUX QUESTIONS
# ----------------------------------------------------

def answer_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    user_data = context.user_data
    init_user_state(context)

    data = query.data  # "answer:q_index:option_index"
    try:
        _, q_str, opt_str = data.split(":")
        q_index = int(q_str)
        chosen_index = int(opt_str)
    except ValueError:
        query.edit_message_text("Erreur de format de réponse.")
        return

    if q_index != user_data["current_q_index"]:
        query.edit_message_text("Cette question est déjà passée.")
        return

    question = QUESTIONS[q_index]
    correct_index = question["correct_index"]

    if chosen_index == correct_index:
        user_data["score"] += 1
        feedback = "✅ Bonne réponse !"
    else:
        correct_option = question["options"][correct_index]
        feedback = f"❌ Mauvaise réponse.\nLa bonne réponse était : {correct_option}"

    user_data["current_q_index"] += 1
    query.edit_message_text(feedback)

    send_question(update, context)


# ----------------------------------------------------
# PAIEMENTS TELEGRAM (ACHAT DE JETONS)
# ----------------------------------------------------

def buy_credits(update: Update, context: CallbackContext) -> None:
    if PAYMENT_PROVIDER_TOKEN == "TON_PROVIDER_TOKEN_ICI":
        update.message.reply_text(
            "⚠️ Le paiement n'est pas encore configuré.\n"
            "Ajoutez votre PAYMENT_PROVIDER_TOKEN pour activer cette fonction."
        )
        return

    title = "Pack de jetons Velvet"
    description = "Recharge de 10 jetons Velvet pour Velvet Oracle."
    payload = "quiz-credit-purchase"
    currency = "EUR"
    price_in_eur = 3
    prices = [LabeledPrice("Pack 10 jetons Velvet", price_in_eur * 100)]

    update.message.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=title,
        description=description,
        payload=payload,
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency=currency,
        prices=prices,
        start_parameter="velvet-oracle-credits",
    )


def precheckout_callback(update: Update, context: CallbackContext) -> None:
    query = update.pre_checkout_query
    if query.invoice_payload != "quiz-credit-purchase":
        query.answer(ok=False, error_message="Payload invalide.")
    else:
        query.answer(ok=True)


def successful_payment_callback(update: Update, context: CallbackContext) -> None:
    user_data = context.user_data
    init_user_state(context)

    user_data["credits"] += 10

    update.message.reply_text(
        f"✅ Paiement reçu !\n"
        f"Vous avez maintenant {user_data['credits']} jetons Velvet.\n"
        "Utilisez /quiz pour lancer une nouvelle partie."
    )


# ----------------------------------------------------
# MAIN : LANCEMENT DU BOT
# ----------------------------------------------------

def main() -> None:
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("quiz", quiz))
    dp.add_handler(CommandHandler("buy_credits", buy_credits))

    dp.add_handler(CallbackQueryHandler(answer_callback, pattern=r"^answer:"))

    dp.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    dp.add_handler(
        MessageHandler(Filters.successful_payment, successful_payment_callback)
    )

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()

import os
import random
import time
import json
import logging
import requests

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------

BOT_TOKEN = "8360941682:AAHe21iKKvbfVrty43-TspiYGU8vXGcS008"  # ← mets ton token ici
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# état simple en mémoire : user_id -> dict
USER_STATE = {}

# questions de base
QUESTIONS = []

def load_questions():
    """Charge les questions depuis questions.json une fois au démarrage."""
    global QUESTIONS
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "questions.json")
    with open(path, "r", encoding="utf-8") as f:
        QUESTIONS = json.load(f)
    logging.info("Questions chargées : %s", len(QUESTIONS))
    QUESTIONS_PER_GAME = 20  # par exemple

# ----------------------------------------------------
# HELPERS API TELEGRAM
# ----------------------------------------------------

def tg_request(method: str, params: dict | None = None):
    url = BASE_URL + method
    try:
        resp = requests.post(url, json=params or {}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok", False):
            logger.warning("Telegram error: %s", data)
        return data
    except Exception as e:
        logger.error("Request error on %s: %s", method, e)
        return None


def send_message(chat_id: int, text: str, reply_markup: dict | None = None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return tg_request("sendMessage", payload)


def answer_callback_query(callback_query_id: str, text: str | None = None):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    return tg_request("answerCallbackQuery", payload)


# ----------------------------------------------------
# LOGIQUE DE JEU
# ----------------------------------------------------

def init_user_state(user_id: int):
    st = USER_STATE.get(user_id, {})
    st.setdefault("score", 0)
    st.setdefault("current_index", 0)
    st.setdefault("credits", 10)
    st.setdefault("games_played", 0)
    st.setdefault("question_ids", [])
    USER_STATE[user_id] = st
    return st



def start_game(chat_id: int, user_id: int):
    st = init_user_state(user_id)

    if st["credits"] <= 0:
        send_message(
            chat_id,
            "💡 Vous n'avez plus de jetons Velvet.\n"
            "La partie gratuite est terminée pour l’instant.",
        )
        return

    if len(QUESTIONS) == 0:
        send_message(chat_id, "Aucune question disponible pour le moment.")
        return

    # On tire au hasard les questions de la partie
    nb = min(QUESTIONS_PER_GAME, len(QUESTIONS))
    st["question_ids"] = random.sample(range(len(QUESTIONS)), nb)
    st["score"] = 0
    st["current_index"] = 0

    send_question(chat_id, user_id)



def send_question(chat_id: int, user_id: int):
    st = USER_STATE[user_id]
    idx = st["current_index"]
    if idx >= len(st["question_ids"]):
        end_game(chat_id, user_id)
        return

    q_idx = st["question_ids"][idx]
    q = QUESTIONS[q_idx]

    keyboard = [
        [
            {
                "text": opt,
                "callback_data": f"answer:{idx}:{i}",
            }
        ]
        for i, opt in enumerate(q["options"])
    ]

    text = f"❓ {q['question']}"
    send_message(chat_id, text, reply_markup={"inline_keyboard": keyboard})



def end_game(chat_id: int, user_id: int):
    st = USER_STATE[user_id]
    score = st["score"]
    total = len(QUESTIONS)

    st["games_played"] += 1
    st["credits"] = max(st["credits"] - 1, 0)

    msg = (
        "🎉 Partie terminée !\n\n"
        f"Score : {score} / {total}\n"
        f"Jetons Velvet restants : {st['credits']}\n"
    )
    if st["credits"] <= 0:
        msg += (
            "\n💎 La réserve de jetons est vide pour l’instant.\n"
            "Velvet Oracle restera accessible pour une prochaine session."
        )

    send_message(chat_id, msg)


# ----------------------------------------------------
# HANDLERS
# ----------------------------------------------------

def handle_start(chat_id: int, user_id: int):
    st = init_user_state(user_id)
    text = (
        "🎩 *Bienvenue dans Velvet Oracle.*\n\n"
        "Ici, chaque question ouvre une porte.\n"
        "Chaque bonne réponse révèle un peu plus de votre discernement.\n\n"
        "Vous entrez dans un quiz réservé à celles et ceux qui apprécient la "
        "précision, la maîtrise et le silence des cercles choisis.\n\n"
        f"_Jetons Velvet disponibles :_ *{st['credits']}*\n\n"
        "• 🎯 /quiz — lancer une partie\n"
        "Prenez place. L’Oracle vous attend."
    )
    # markdown simple
    tg_request(
        "sendMessage",
        {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
    )


def handle_text_message(chat_id: int, user_id: int, text: str):
    text = text.strip()
    if text == "/start":
        handle_start(chat_id, user_id)
    elif text == "/quiz":
        start_game(chat_id, user_id)
    else:
        send_message(
            chat_id,
            "Commande non reconnue.\n"
            "Utilisez /start pour l’accueil ou /quiz pour lancer une partie.",
        )


    if data.startswith("answer:"):
        try:
            _, idx_str, opt_str = data.split(":")
            idx = int(idx_str)          # index dans la séquence de la partie
            chosen_index = int(opt_str)
        except Exception:
            answer_callback_query(cq_id, "Erreur de format.")
            return

        if idx != st["current_index"]:
            answer_callback_query(cq_id, "Cette question est déjà passée.")
            return

        q_idx = st["question_ids"][idx]
        question = QUESTIONS[q_idx]
        correct_index = question["correct_index"]

        if chosen_index == correct_index:
            st["score"] += 1
            feedback = "✅ Bonne réponse !"
        else:
            correct_opt = question["options"][correct_index]
            feedback = f"❌ Mauvaise réponse.\nLa bonne réponse était : {correct_opt}"

        answer_callback_query(cq_id)
        send_message(chat_id, feedback)

        st["current_index"] += 1
        send_question(chat_id, user_id)



# ----------------------------------------------------
# BOUCLE PRINCIPALE (LONG POLLING)
# ----------------------------------------------------

def main():
    logger.info("Velvet Oracle bot démarré (mode minimal, sans paiements).")
    offset = None

    while True:
        try:
            params = {"timeout": 50}
            if offset is not None:
                params["offset"] = offset

            resp = requests.get(
                BASE_URL + "getUpdates", params=params, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("ok", False):
                logger.warning("getUpdates error: %s", data)
                time.sleep(2)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    if "message" in update:
                        msg = update["message"]
                        chat_id = msg["chat"]["id"]
                        user = msg.get("from", {})
                        user_id = user.get("id")
                        text = msg.get("text", "")

                        if user_id is None or text is None:
                            continue

                        handle_text_message(chat_id, user_id, text)

                    elif "callback_query" in update:
                        handle_callback_query(update)

                except Exception as e:
                    logger.exception("Erreur en traitant un update: %s", e)

        except Exception as e:
            logger.error("Erreur dans la boucle principale: %s", e)
            time.sleep(5)  # évite de spammer Telegram / planter la machine


if __name__ == "__main__":
    main()

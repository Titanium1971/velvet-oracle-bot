# ----------------------------------------------------
# MAIN : LANCEMENT DU BOT
# ----------------------------------------------------

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "8360941682:AAHe21iKKvbfVrty43-TspiYGU8vXGcS008":
        raise RuntimeError(
            "Ajoutez votre TELEGRAM_BOT_TOKEN dans BOT_TOKEN avant de lancer le script."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    # Commandes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(CommandHandler("buy_credits", buy_credits))

    # Réponses du quiz
    application.add_handler(CallbackQueryHandler(answer_callback, pattern=r"^answer:"))

    # Paiements
    application.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback)
    )

    # Lancement en mode polling
    application.run_polling()


if __name__ == "__main__":
    main()

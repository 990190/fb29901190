
@flask_app.route("/webhook", methods=["POST"])
def telegram_webhook():
    json_data = request.get_json()
    if json_data:
        asyncio.run(app.update_queue.put(Update.de_json(json_data, app.bot)))
    return jsonify({"status": "ok"})

@flask_app.route("/")
def health_check():
    return "OK"

if __name__ == "__main__":
    import threading
    def run_bot():
        asyncio.run(app.bot.set_webhook(url=WEBHOOK_URL))
        app.run_polling()
    threading.Thread(target=run_bot, daemon=True).start()
    flask_app.run(host="0.0.0.0", port=PORT)

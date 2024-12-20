from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import openai
from datetime import datetime
import json
import os

# Configura OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Verifica se il token è presente
if TELEGRAM_TOKEN is None:
    print("Errore: il TOKEN di Telegram non è stato trovato.")
else:
    print("Token di Telegram caricato correttamente.")

# Verifica se la chiave è presente
if openai.api_key is None:
    print("Errore: la chiave API di OpenAI non è stata trovata.")
else:
    print("Chiave API di OpenAI caricata correttamente.")

# Percorso del file JSON per salvare i messaggi
MESSAGES_FILE = 'messages.json'

# ID della chat da impostare una volta che lo ottieni tramite il comando `/getchatid`
CHAT_ID = os.getenv("CHAT_ID")  # Per ora lascia vuoto, verrà settato dopo aver ottenuto l'ID della chat

# Contatore dei messaggi
message_counter = 0
MESSAGE_LIMIT = 50  # Numero massimo di messaggi prima di eseguire il riassunto


# Funzione per ottenere l'ID della chat
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    chat_id = update.message.chat_id  # Ottieni l'ID della chat
    CHAT_ID = chat_id  # Salva l'ID
    await update.message.reply_text(f"Ho capito.. alora l'ID della chat è: {chat_id}")


# Funzione di avvio del bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Risponde con un messaggio di benvenuto quando l'utente invia il comando /start
    await update.message.reply_text(
        "Ciao! Lo voi l'pallone? Io ti posso aiutare a sintetizzare le conversazioni, e ti posso dire di che cosa si è parlato oggi."
    )


# Funzione per salvare i messaggi nel file JSON e controllare il limite
async def save_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global message_counter

    if not update.message or not update.message.text:
        return  # Ignora aggiornamenti senza messaggi di testo

    user = update.message.from_user.full_name  # Nome dell'utente
    text = update.message.text  # Testo del messaggio

    today = datetime.now().strftime('%Y-%m-%d')

    # Se il file non esiste o è vuoto, crealo
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump({}, f)

    # Leggi i messaggi già salvati nel file JSON
    try:
        with open(MESSAGES_FILE, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = {}

    # Aggiungi il messaggio alla lista del giorno corrente
    if today not in data:
        data[today] = []
    data[today].append(f"{user}: {text}")

    # Salva nuovamente i dati nel file JSON
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    # Incrementa il contatore dei messaggi
    message_counter += 1

    # Se il limite è raggiunto, genera il riassunto
    if message_counter >= MESSAGE_LIMIT:
        await riassunto_automatico(context)
        message_counter = 0  # Resetta il contatore


# Funzione per fare il riassunto su richiesta
async def riassumi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        await update.message.reply_text("Mi dispiace, ma tu l'ID non l'è messo.")
        return

    await genera_riassunto(context)


# Funzione per il riassunto automatico
async def riassunto_automatico(context: ContextTypes.DEFAULT_TYPE):
    if not CHAT_ID:
        return

    await genera_riassunto(context)


# Funzione per generare il riassunto
async def genera_riassunto(context: ContextTypes.DEFAULT_TYPE):
    # Leggi i messaggi dal file JSON
    with open(MESSAGES_FILE, 'r') as f:
        data = json.load(f)

    today = datetime.now().strftime('%Y-%m-%d')
    if today not in data or not data[today]:
        await context.bot.send_message(
            CHAT_ID,
            "Mi dispiace, nessun ascoltatore ha chiamato per lasciare un messaggio."
        )
        return

    # Gestione della lunghezza dei messaggi
    max_message_length = 3500  # Limite di token per il modello GPT-3.5
    conversation = "\n".join(data[today])
    while len(conversation.encode('utf-8')) > max_message_length:  # Verifica il numero di byte
        # Elimina i messaggi più vecchi per fare spazio
        data[today].pop(0)
        conversation = "\n".join(data[today])

    # Usa OpenAI per generare un riassunto
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Usa il modello di chat
            messages=[{
                "role": "system",
                "content": "Sei un assistente che crea riassunti brevi, chiari e diretti. Evita di essere vago e fornisci risposte concrete. Puoi anche citare direttamente qualche messaggio. Inoltre non essere rigido, mantieni un tono umoristico. Riporta brevemente le opinioni di ciascun partecipante alla discussione, indicandone il nome."
            }, {
                "role": "user",
                "content": f"Riassumi questa conversazione in modo conciso e preciso:\n\n{conversation}"
            }],
            max_tokens=300,  # Aumenta il numero di token per la risposta
        )
        riassunto = response['choices'][0]['message']['content'].strip()
    except Exception as e:
        riassunto = f"Errore: {e}"

    # Invia il riassunto
    await context.bot.send_message(CHAT_ID, f"DI CHE COSA SI E' PARLATO..:\n{riassunto}")

    # Svuota i messaggi per oggi
    data[today] = []
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(data, f)


# Funzione principale
def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_message))
    application.add_handler(CommandHandler("getchatid", get_chat_id))
    #application.add_handler(CommandHandler("riassumi", riassumi))

    application.run_polling()


if __name__ == "__main__":
    main()

from typing import List

from telegram import Update, Bot
from telegram.ext import run_async, CommandHandler, Filters

import tg_bot.modules.sql.spam_shield_sql as sql
from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.chat_status import user_admin


@run_async
@user_admin
def spamshield(bot: Bot, update: Update, args: List[str]):
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_spam_shield(update.effective_chat.id)
            update.effective_message.reply_text("Chat #SPAM_SHIELD turned on ")
        elif args[0].lower() in ["off", "no"]:
            sql.disable_spam_shield(update.effective_chat.id)
            update.effective_message.reply_text("Chat #SPAM_SHIELD turned off")
    else:
        update.effective_message.reply_text("Give me some arguments to choose a setting! on/off, yes/no!\n\n"
                                            "Your current setting is: {}\n"
                                            "When True, your group will be protected from spammers. "
                                            "When False, they won't, leaving you at the possible mercy of "
                                            "spammers.".format(sql.does_chat_spamshield(update.effective_chat.id)))


__help__ = """
*Admin only:*
  /spamshield <on/off/yes/no>: Will disable or enable the effect of Spam protection in your group.\n
  Spam shield uses Combot Anti Spam, @Spamwatch API and Global bans to remove Spammers as much as possible from your chatroom!
"""

__mod_name__ = "Spam Shield"

SMSHIELD_STATUS = CommandHandler("spamshield", spamshield, pass_args=True, filters=Filters.group)

dispatcher.add_handler(SMSHIELD_STATUS)

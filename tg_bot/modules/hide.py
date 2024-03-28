import html
import re
from typing import Optional, List

from telegram import (
    Message, Chat, Update, Bot, ParseMode,
    InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler, MessageHandler, Filters, run_async
from telegram.utils.helpers import mention_html, escape_markdown

import tg_bot.modules.sql.hide_sql as sql
from tg_bot import dispatcher, LOGGER, updater
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import user_admin, user_not_admin, bot_admin
from tg_bot.modules.helper_funcs.extraction import extract_text
from tg_bot.modules.helper_funcs.misc import split_message
from tg_bot.modules.helper_funcs.msg_types import get_welcome_type
from tg_bot.modules.helper_funcs.string_handling import extract_time_interval, escape_invalid_curly_brackets
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.captcha import tlg_autodelete_msg

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video
}

HIDEKEYWORD_GROUP = 12

BASE_HIDEKEYWORDS_STRING = "Current <b>hide keywords</b> words:\n"

VALID_HELP_FORMATTERS = ['help']

original_messages = {}
chat_data = {}


@run_async
def hidekeyword(bot: Bot, update: Update, args: List[str]):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]

    all_hidekeywords = sql.get_chat_hidewords(chat.id)

    filter_list = BASE_HIDEKEYWORDS_STRING

    if len(args) > 0 and args[0].lower() == 'copy':
        for trigger in all_hidekeywords:
            filter_list += "<code>{}</code>\n".format(html.escape(trigger))
    else:
        for trigger in all_hidekeywords:
            filter_list += " - <code>{}</code>\n".format(html.escape(trigger))

    split_text = split_message(filter_list)
    for text in split_text:
        if text == BASE_HIDEKEYWORDS_STRING:
            msg.reply_text("There are no hide keywords messages here!")
            return
        msg.reply_text(text, parse_mode=ParseMode.HTML)


@run_async
@user_admin
def add_hidekeyword(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    words = msg.text.split(None, 1)
    if len(words) > 1:
        text = words[1]
        to_hidekeyword = list(set(trigger.strip() for trigger in text.split("\n") if trigger.strip()))
        for trigger in to_hidekeyword:
            sql.add_to_hidewords(chat.id, trigger.lower())

        if len(to_hidekeyword) == 1:
            msg.reply_text("Added <code>{}</code> to the hide keywords!".format(html.escape(to_hidekeyword[0])),
                           parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(
                "Added <code>{}</code> triggers to the hide keywords.".format(len(to_hidekeyword)), parse_mode=ParseMode.HTML)

    else:
        msg.reply_text("Tell me which words you would like to remove from the hide keywords.")


@run_async
@user_admin
def unhidekeyword(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    words = msg.text.split(None, 1)
    if len(words) > 1:
        text = words[1]
        to_unhidekeyword = list(set(trigger.strip() for trigger in text.split("\n") if trigger.strip()))
        successful = 0
        for trigger in to_unhidekeyword:
            success = sql.rm_from_hidewords(chat.id, trigger.lower())
            if success:
                successful += 1

        if len(to_unhidekeyword) == 1:
            if successful:
                msg.reply_text("Removed <code>{}</code> from the hide keywords!".format(html.escape(to_unhidekeyword[0])),
                               parse_mode=ParseMode.HTML)
            else:
                msg.reply_text("This isn't a hide keywords trigger...!")

        elif successful == len(to_unhidekeyword):
            msg.reply_text(
                "Removed <code>{}</code> triggers from the hide keywords.".format(
                    successful), parse_mode=ParseMode.HTML)

        elif not successful:
            msg.reply_text(
                "None of these triggers exist, so they weren't removed.".format(
                    successful, len(to_unhidekeyword) - successful), parse_mode=ParseMode.HTML)

        else:
            msg.reply_text(
                "Removed <code>{}</code> triggers from the hide keywords. {} did not exist, "
                "so were not removed.".format(successful, len(to_unhidekeyword) - successful),
                parse_mode=ParseMode.HTML)
    else:
        msg.reply_text("Tell me which words you would like to remove from the hide keywords.")


@run_async
@user_not_admin
def del_hidekeyword(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user
    if user.username:
        user_name = "@" + escape_markdown(user.username)
        # user_name = user.username
    else:
        user_name = escape_markdown(user.full_name)

    to_match = extract_text(message)
    if not to_match:
        return

    chat_id = chat.id

    chat_filters = sql.get_chat_hidewords(chat.id)
    for trigger in chat_filters:
        pattern = r"( |^|[^\w])" + re.escape(trigger) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            # reported_user = message.reply_to_message.from_user  # type: Optional[User]
            chat_name = chat.title or chat.first or chat.username
            admin_list = chat.get_administrators()

            msg = "{} is calling for admins in \"{}\"!".format(mention_html(user.id, user_name),
                                                               html.escape(chat_name))
            # link = ""
            should_forward = True

            for admin in admin_list:
                if admin.user.is_bot:  # can't message bots
                    continue

                try:
                    bot.send_message(admin.user.id, msg, parse_mode=ParseMode.HTML)

                    if should_forward:
                        message.forward(admin.user.id)
                        # message.reply_to_message.forward(admin.user.id)

                        # if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
                        #     message.forward(admin.user.id)

                except Unauthorized:
                    pass
                except BadRequest as excp:  # TODO: cleanup exceptions
                    LOGGER.exception("Exception while reporting user")

            # return msg

            # Store the original message
            if chat_id not in original_messages:
                original_messages[chat_id] = {}
            original_messages[chat_id][message.message_id] = message

            # Create an inline keyboard button for admins to view the message
            # keyboard = [[InlineKeyboardButton("Admins View Message", url="t.me/{}?start=view_{}_{}".format(bot.username, chat_id, message.message_id))]]
            # reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                message.delete()
            except BadRequest as excp:
                if excp.message == "Message to delete not found":
                    pass
                else:
                    LOGGER.exception("Error while deleting hide keywords message.")

            # Send a new message to include the inline keyboard button
            msg = bot.send_message(chat_id=chat_id,
                             text=f"{mention_html(user.id, user_name)}, Your message have been forwarded to the Admins. Admins will review it shortly.", parse_mode=ParseMode.HTML)
            tlg_autodelete_msg(msg, 60)
            break


# def send_msg_to_admin(msg_id, chat, admin_id):
#     chat_id = chat.id
#     message = original_messages[chat_id][int(msg_id)]
#     if message.message_id == int(msg_id):
#         to_match = extract_text(message)
#         if chat.title is not None:
#             chat_title = chat.title
#         else:
#             chat_title = f"@{chat.username}"
#
#         if message.from_user.username is not None:
#             user_name = message.from_user.username
#         else:
#             user_name = message.from_user.full_name
#
#         chat_filters = sql.get_chat_hidewords(chat.id)
#         for trigger in chat_filters:
#             pattern = r"( |^|[^\w])" + re.escape(trigger) + r"( |$|[^\w])"
#             users_msg = re.sub(pattern, " ", to_match, flags=re.IGNORECASE)
#
#         if to_match.startswith(trigger):
#             users_msg = users_msg.lstrip()
#
#         text = "{} from this group {}, sent the message below please attend to the user: \n\n{}".format(user_name, chat_title, users_msg)
#
#         sent_result: dict = {}
#         sent_result["msg"] = None
#         sent_result["error"] = ""
#         try:
#             msg = dispatcher.bot.send_message(chat_id=admin_id, text=text)
#             LOGGER.debug("[%s] TLG text msg %d sent", str(admin_id), message.message_id)
#             sent_result["msg"] = msg
#         except TelegramError as error:
#             sent_result["error"] = str(error)
#             LOGGER.error("[%s] %s", str(chat_id), str(error))


@run_async
@bot_admin
@user_admin
# @loggable
def set_help_msg(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("You didn't specify the help message")
        return ""

    sql.set_help_msg(chat.id, content or text, data_type)
    msg.reply_text("Successfully set help message!")

    return "<b>{}:</b>" \
           "\n#SET_HELP" \
           "\n<b>Admin:</b> {}" \
           "\nSet the help message.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@bot_admin
@user_admin
@loggable
def set_interval(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    chat_id = chat.id

    # user_id, reason = extract_user_and_text(message, args)
    time_interval = None
    if len(args) > 0:
        time_interval = extract_time_interval(message, args[0])
    else:
        message.reply_text("You haven't specified a time interval to send the message")

    if time_interval is None:
        return ""

    log = "<b>{}:</b>" \
          "\n#HIDE MESSAGE TIME INTERVAL" \
          "\n<b>Admin:</b> {}" \
          "\n<b>Time:</b> {}".format(html.escape(chat.title),
                        mention_html(user.id, user.first_name), time_interval)

    if chat_id in chat_data:
        # Cancel the existing job if it exists
        if 'job' in chat_data[chat_id]:
            chat_data[chat_id]['job'].schedule_removal()

        # Create a new job with the updated interval
        job = updater.job_queue.run_repeating(send_help_msg, time_interval, first=60, context=chat_id)
        chat_data[chat_id]['job'] = job
        job.enabled = True

    try:
        sql.set_time_interval(chat.id, time_interval)
        message.reply_text(f"time interval for the help message successfully changed to {time_interval}secs.")

    except Exception as e:
        LOGGER.warning(update)
        LOGGER.exception("ERROR setting time interval %s in chat %s (%s) due to %s", str(time_interval), chat.title, chat.id,
                         e)
        message.reply_text("An Error Occured.")

    return ""


@run_async
@bot_admin
@user_admin
def toggle_sending(bot: Bot, update: Update, args: List[str]):
    chat_id = update.effective_chat.id
    if len(args) > 0:
        if args[0].lower() in ["on", "yes"]:
            sql.enable_help_msg(chat_id)
            help_msg, help_msg_type, time_interval, setting = sql.get_help_msg(chat_id)

            if chat_id not in chat_data:
                chat_data[chat_id] = {}

            # Cancel the existing job if it exists
            if 'job' in chat_data[chat_id]:
                chat_data[chat_id]['job'].schedule_removal()

            job = updater.job_queue.run_repeating(send_help_msg, time_interval, first=60, context=chat_id)

            chat_data[chat_id]['job'] = job
            job.enabled = True
            print(chat_data)
            update.effective_message.reply_text("Sending help messages is now On in this group.")
        elif args[0].lower() in ["off", "no"]:
            sql.disable_help_msg(chat_id)
            if chat_id in chat_data:
                # Cancel the existing job if it exists
                if 'job' in chat_data[chat_id]:
                    chat_data[chat_id]['job'].schedule_removal()
                    del chat_data[chat_id]
                    update.effective_message.reply_text("I've disabled the help message!")
            else:
                update.effective_message.reply_text("help message is already Off!")
    else:
        help_msg, help_msg_type, time_interval, setting = sql.get_help_msg(chat_id)
        update.effective_message.reply_text("Give me some arguments to choose a setting! on/off, yes/no!\n\n"
                                            f"Your current setting is: {setting}\n"
                                            f"When True, '{help_msg}' will be sent in this group in an interval of {time_interval}secs")


def send(bot, chat_id, message, backup_message, keyboard=None):
    msg = None
    try:
        msg = bot.send_message(chat_id, message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard, api_kwargs={"allow_sending_without_reply": True})
    except IndexError:
        msg = bot.send_message(chat_id, markdown_parser(backup_message +
                                                                  "\nNote: the current message was "
                                                                  "invalid due to markdown issues. Could be "
                                                                  "due to the user's name."),
                                                  parse_mode=ParseMode.MARKDOWN)
    except KeyError:
        msg = bot.send_message(chat_id, markdown_parser(backup_message +
                                                                  "\nNote: the current message is "
                                                                  "invalid due to an issue with some misplaced "
                                                                  "curly brackets. Please update"),
                                                  parse_mode=ParseMode.MARKDOWN)
    except BadRequest as excp:
        if excp.message == "Button_url_invalid":
            msg = bot.send_message(chat_id, markdown_parser(backup_message +
                                                                      "\nNote: the current message has an invalid url "
                                                                      "in one of its buttons. Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Unsupported url protocol":
            msg = bot.send_message(chat_id, markdown_parser(backup_message +
                                                                      "\nNote: the current message has buttons which "
                                                                      "use url protocols that are unsupported by "
                                                                      "telegram. Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Wrong url host":
            msg = bot.send_message(chat_id, markdown_parser(backup_message +
                                                                      "\nNote: the current message has some bad urls. "
                                                                      "Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.warning(message)
            LOGGER.exception("Could not parse! got invalid url host errors")
        elif excp.message == "Replied message not found":
            LOGGER.warning("Original message deleted")
        elif excp.message == "Have no rights to send a message":
            LOGGER.warning("Muted in below chat")
            print(update.effective_message.chat.id)
        else:
            msg = bot.send_message(chat_id, markdown_parser(backup_message +
                                                                      "\nNote: An error occured when sending the "
                                                                      "custom message. Please update."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.exception()

    return msg


def send_help_msg(bot, job):
    chat_id = job.context
    help_msg, help_msg_type, time_interval, setting = sql.get_help_msg(chat_id)

    if help_msg_type != sql.Types.TEXT:
        ENUM_FUNC_MAP[help_msg_type](chat_id, help_msg)
        return

    if help_msg:
        valid_format = escape_invalid_curly_brackets(help_msg, VALID_HELP_FORMATTERS)

        if not valid_format:
            return

        all_hidekeywords = sql.get_chat_hidewords(chat_id)
        triggers = ', '.join(all_hidekeywords)
        res = valid_format.format(help=triggers)
    else:
        res = sql.DEFAULT_HIDE_MSG.format(help=triggers)

    sent = send(bot, chat_id, res, sql.DEFAULT_HIDE_MSG.format(help=triggers))  # type: Optional[Message]

def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    hide_keywords = sql.num_hidewords_chat_filters(chat_id)
    return "There are {} hide keywords.".format(hide_keywords)


def __stats__():
    return "{} hide keywords triggers, across {} chats.".format(sql.num_hidewords_filters(),
                                                            sql.num_hidewords_filter_chats())


__mod_name__ = "Hide"

__help__ = """
The "hide" module ensures secure message transmission within group chats. Users' messages are hidden upon sending, in the chat.
this messsage will be forwarded to authorized users.
This feature enhances privacy and confidentiality, safeguarding sensitive information exchanged within the group.

*NOTE:* hide do not affect group admins.

 - /hidekeywords: View the current hide keywords.

*Admin only:*
 - /addhidekeyword <triggers>: Add a trigger to the hide keywords. Each line is considered one trigger, so using different \
lines will allow you to add multiple triggers.
 - /unhidekeyword <triggers>: Remove triggers from the hide keywords. Same newline logic applies here, so you can remove \
multiple triggers at once.
 - /rmhidekeyword <triggers>: Same as above.
 - /sethelpmsg <sometext>: set a custom help message.
 - /settimeinterval x(m/h/d): set message interval for x time. m = minutes, h = hours, d = days.
 - /sendhelpmsg <on/off/yes/no>: Will disable the status of the help message on your group, or return your current settings.
"""

# job = updater.job_queue
#
# # job_rss_set = job.run_once(rss_set, 5)
# job_hide_msg = job.run_repeating(hide_msg, interval=60, first=60)
# # job_rss_set.enabled = True
# job_hide_msg.enabled = True

HIDEKEYWORD_HANDLER = DisableAbleCommandHandler("hidekeywords", hidekeyword, filters=Filters.group, pass_args=True,
                                              admin_ok=True)
SETINTERVAL = CommandHandler("settimeinterval", set_interval, filters=Filters.group, pass_args=True)
SETHELPMSG = CommandHandler("sethelpmsg", set_help_msg, filters=Filters.group)
SENDHELPMSG = CommandHandler("sendhelpmsg", toggle_sending, pass_args=True, filters=Filters.group)
ADD_HIDEKEYWORD_HANDLER = CommandHandler("addhidekeyword", add_hidekeyword, filters=Filters.group)
UNHIDEKEYWORD_HANDLER = CommandHandler(["unhidekeyword", "rmhidekeyword"], unhidekeyword, filters=Filters.group)
HIDEKEYWORD_DEL_HANDLER = MessageHandler(
    (Filters.text | Filters.command | Filters.sticker | Filters.photo) & Filters.group, del_hidekeyword)

dispatcher.add_handler(HIDEKEYWORD_HANDLER)
dispatcher.add_handler(SETHELPMSG)
dispatcher.add_handler(SETINTERVAL)
dispatcher.add_handler(SENDHELPMSG)
dispatcher.add_handler(ADD_HIDEKEYWORD_HANDLER)
dispatcher.add_handler(UNHIDEKEYWORD_HANDLER)
dispatcher.add_handler(HIDEKEYWORD_DEL_HANDLER, group=HIDEKEYWORD_GROUP)

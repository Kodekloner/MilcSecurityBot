import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import run_async, CommandHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery

import tg_bot.modules.sql.approval_sql as sql
from tg_bot import dispatcher, BAN_STICKER, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_ban_protected, can_restrict, \
    is_user_admin, is_user_in_chat, is_bot_admin, _TELE_GRAM_ID_S
from tg_bot.modules.helper_funcs.extraction import extract_user_and_text, extract_user
from tg_bot.modules.helper_funcs.string_handling import extract_time
# from tg_bot.modules.log_channel import loggable
from tg_bot.modules.helper_funcs.connection import check_conn
from tg_bot.modules.helper_funcs.filters import CustomFilters


@run_async
def approval(bot: Bot, update: Update, args: List[str]) -> str:
    msg = update.effective_message  # type: Optional[Message]
    user_id = extract_user(update.effective_message, args)

    if user_id:
        user = bot.get_chat(user_id)

    elif not msg.reply_to_message and not args:
        user = msg.from_user

    elif not msg.reply_to_message and (not args or (
            len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
        [MessageEntity.TEXT_MENTION]))):
        msg.reply_text("I can't extract a user from this.")
        return

    else:
        return

    user_username = user.username

    # first_name = join_user.first_name

    if user_username is not None:
        user_name = "@" + user_username
    else:
        user_name = user.full_name


    if sql.is_user_approved(user_id):
        text = "{} is an approved user." \
                "\nLocks, antiflood, and blocklists won't apply to them.".format(html.escape(user_name))
    else:
        text = "{} is not an approved user." \
                "\nThey are affected by normal commands.".format(html.escape(user_name))
    msg.reply_text(text)


@run_async
@bot_admin
@user_admin
def approve(bot: Bot, update: Update, args: List[str]) -> str:
    msg = update.effective_message  # type: Optional[Message]
    user_id = extract_user(update.effective_message, args)

    if user_id:
        user = bot.get_chat(user_id)

    elif not msg.reply_to_message and not args:
        user = msg.from_user

    elif not msg.reply_to_message and (not args or (
            len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
        [MessageEntity.TEXT_MENTION]))):
        msg.reply_text("I can't extract a user from this.")
        return

    else:
        return

    user_username = user.username

    # first_name = join_user.first_name

    if user_username is not None:
        user_name = "@" + user_username
    else:
        user_name = user.full_name


    if sql.is_user_approved(user_id):
        text = "{} is already approved.".format(html.escape(user_name))
        message.reply_text(text)
        return

    sql.approve_user(user_id, user_name)
    text = "{} has been approved! They will now be ignored by automated admin actions like locks, blocklists, and antiflood.".format(html.escape(user_name))
    msg.reply_text(text)


@run_async
@bot_admin
@user_admin
def approved(bot: Bot, update: Update):
    approved_users = sql.get_approved_list()

    if not approved_users:
        update.effective_message.reply_text("No users are approved in this group")
        return

    text = 'The following users are approved:\n'
    for user in approved_users:
        text += "{}: {}\n".format(user["user_id"], user["name"])

    update.effective_message.reply_text(text)


@run_async
@bot_admin
@user_admin
def unapproveall(bot: Bot, update: Update):
    chat = update.effective_chat
    approved_users = sql.get_approved_list()

    if not approved_users:
        update.effective_message.reply_text("No users are approved in this group")
        return

    text = "Are you sure would like to unapprove ALL users in {}? This action cannot be undone".format(chat.title)
    keyboard = [[
            InlineKeyboardButton("Unapprove all users", callback_data=f"unapprove_users")
            ],
            [InlineKeyboardButton("Cancel", callback_data=f"unapprove_cancel")
            ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


@run_async
def button(bot: Bot, update: Update):
    query = update.callback_query
    msg_id = query.message.message_id
    chat_id = query.message.chat_id
    # Confirm query received
    query_ans_result: dict = {}
    query_ans_result["error"] = ""
    try:
        bot.answer_callback_query(query.id)
    except Exception as error:
        query_ans_result["error"] = str(error)
        LOGGER.error("[%s] %s", str(query.message.chat_id), str(error))

    if query_ans_result["error"] != "":
        return

    bot.delete_message(chat_id, msg_id)

    if query.data == "unapprove_users":
        approved_users = sql.get_approved_list()
        for user in approved_users:
            sql.unapprove_user(user["user_id"])
        bot.send_message(chat_id=chat_id, text="Unapproved all users in chat. All users will now be affected by locks, blocklists, and antiflood.")

    if query.data == "unapprove_cancel":
        bot.send_message(chat_id=chat_id, text="Unapproval of all users has been cancelled.")


@run_async
@bot_admin
@user_admin
def unapprove(bot: Bot, update: Update, args: List[str]) -> str:
    msg = update.effective_message  # type: Optional[Message]
    user_id = extract_user(update.effective_message, args)

    if user_id:
        user = bot.get_chat(user_id)

    elif not msg.reply_to_message and not args:
        user = msg.from_user

    elif not msg.reply_to_message and (not args or (
            len(args) >= 1 and not args[0].startswith("@") and not args[0].isdigit() and not msg.parse_entities(
        [MessageEntity.TEXT_MENTION]))):
        msg.reply_text("I can't extract a user from this.")
        return

    else:
        return

    user_username = user.username

    # first_name = join_user.first_name

    if user_username is not None:
        user_name = "@" + user_username
    else:
        user_name = user.full_name


    if not sql.is_user_approved(user_id):
        text = "{} isn't approved yet!.".format(html.escape(user_name))
        message.reply_text(text)
        return

    sql.unapprove_user(user_id)
    text = "{} is no longer approved.".format(html.escape(user_name))
    msg.reply_text(text)


__help__ = """
 Sometimes, you might trust a user not to send unwanted content.
 Maybe not enough to make them admin, but you might be ok with locks, blocklists, and antiflood not applying to them.

 That's what approvals are for - approve of trustworthy users to allow them to send

 *User commands:*
 - /approval: Checks a User's approval status in this chat.

 *Admin commands:*
 - /approve: Approve of a user. Locks, blacklists, and antiflood won't apply to them anymore
 - /unapprove: Unapprove of a user. They will now be subjected to locks, blocklists, and antiflood again
 - /approved: List all approved users.
 - /unapproveall: Unapprove ALL users in a chat. This cannot be undone
"""

__mod_name__ = "Approval"

APPROVAL = CommandHandler("approval", approval, pass_args=True)
UNAPPROVE = CommandHandler("unapprove", unapprove, pass_args=True)
APPROVE = CommandHandler("approve", approve, pass_args=True)
APPROVED = CommandHandler("approved", approved)
UNAPPROVEALL = CommandHandler("unapproveall", unapproveall, filters=CustomFilters.sudo_filter)
BUTTON_UNAPPROVE = CallbackQueryHandler(button, pattern=r"unapprove_")



dispatcher.add_handler(APPROVAL)
dispatcher.add_handler(UNAPPROVE)
dispatcher.add_handler(APPROVE)
dispatcher.add_handler(APPROVED)
dispatcher.add_handler(UNAPPROVEALL)
dispatcher.add_handler(BUTTON_UNAPPROVE)


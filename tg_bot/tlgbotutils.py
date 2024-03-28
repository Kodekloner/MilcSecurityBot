# Date and Time Library
from datetime import datetime

from tg_bot import LOGGER
from typing import List, Optional, Union
from telegram.error import TelegramError
from telegram import (
    Message, Update, Bot, User, Chat, InlineKeyboardMarkup,
    InlineKeyboardButton, ParseMode, InputMediaPhoto, ReplyMarkup
)


def tlg_get_msg(update: Update):
    '''Get Telegram message data from the Update element.'''
    msg = getattr(update, "message", None)
    if msg is None:
        msg = getattr(update, "edited_message", None)
    if msg is None:
        msg = getattr(update, "channel_post", None)
    return msg

def tlg_kick_user(
        bot: Bot,
        chat_id: Union[str, int],
        user_id: Union[str, int]
        ):
    '''Telegram Kick a user of an specified chat'''
    kick_result: dict = {}
    kick_result["error"] = ""
    # Get chat member info
    # Do nothing if user left the group or has been kick/ban by an Admin
    member_info_result = tlg_get_chat_member(bot, chat_id, user_id)
    if member_info_result["member"] is None:
        kick_result["error"] = member_info_result["error"]
        return kick_result
    if member_info_result["member"]["status"] == "left":
        kick_result["error"] = "The user has left the group"
        return kick_result
    if member_info_result["member"]["status"] == "kicked":
        kick_result["error"] = "The user was already kicked"
        return kick_result
    # Kick User (remove restrictions with only_if_banned=False make
    # it kick)
    try:
        bot.unban_chat_member(
                chat_id=chat_id, user_id=user_id, only_if_banned=False)
    except Exception as error:
        kick_result["error"] = str(error)
        LOGGER.error("[%s] %s", str(chat_id), str(error))
    return kick_result

def tlg_get_chat_member(
        bot: Bot,
        chat_id: Union[str, int],
        user_id: Union[str, int]
        ):
    '''Telegram Get Chat member info.'''
    result: dict = {}
    result["member"] = None
    result["error"] = ""
    try:
        result["member"] = bot.get_chat_member(
            chat_id=chat_id, user_id=user_id)
    except Exception as error:
        result["error"] = str(error)
        LOGGER.error("[%s] %s", str(chat_id), str(error))
    return result


def tlg_ban_user(
        bot: Bot,
        chat_id: Union[str, int],
        user_id: Union[str, int],
        until_date: Union[int, datetime, None] = None
        ):
    '''Telegram Ban a user of an specified chat'''
    ban_result: dict = {}
    ban_result["error"] = ""
    # Get chat member info
    member_info_result = tlg_get_chat_member(bot, chat_id, user_id)
    if member_info_result["member"] is None:
        ban_result["error"] = member_info_result["error"]
        return ban_result
    # Check if user is not in the group
    if member_info_result["member"]["status"] == "left":
        ban_result["error"] = "The user has left the group"
        return ban_result
    if member_info_result["member"]["status"] == "kicked":
        ban_result["error"] = "The user was already kicked"
        return ban_result
    # Ban User
    try:
        if until_date is None:
            bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        else:
            bot.ban_chat_member(
                    chat_id=chat_id, user_id=user_id, until_date=until_date)
    except Exception as error:
        ban_result["error"] = str(error)
        LOGGER.error("[%s] %s", str(chat_id), str(error))
    return ban_result

def tlg_send_msg(
        bot: Bot,
        chat_id: Union[str, int],
        text: str,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: Optional[bool] = None,
        disable_notification: Optional[bool] = None,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[ReplyMarkup] = None,
        topic_id: Optional[int] = None
        ):
    '''Bot try to send a text message.'''
    sent_result: dict = {}
    sent_result["msg"] = None
    sent_result["error"] = ""
    if parse_mode == "HTML":
        parse_mode = ParseMode.HTML
    elif parse_mode == "MARKDOWN":
        parse_mode = ParseMode.MARKDOWN
    try:
        msg = bot.send_message(
                chat_id=chat_id, text=text, parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
                disable_notification=disable_notification,
                reply_to_message_id=reply_to_message_id,
                message_thread_id=topic_id)
        LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
        sent_result["msg"] = msg
    except TelegramError as error:
        sent_result["error"] = str(error)
        LOGGER.error("[%s] %s", str(chat_id), str(error))
    return sent_result

def tlg_delete_msg(
        bot: Bot,
        chat_id: Union[int, str],
        msg_id: int
        ):
    '''Try to remove a telegram message'''
    delete_result: dict = {}
    delete_result["error"] = ""
    if msg_id is not None:
        LOGGER.debug("[%s] TLG deleting msg %d", chat_id, msg_id)
        try:
            bot.delete_message(chat_id=chat_id, message_id=msg_id)
            LOGGER.debug("[%s] TLG msg %d deleted", str(chat_id), msg_id)
        except Exception as error:
            delete_result["error"] = str(error)
            LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])
    return delete_result

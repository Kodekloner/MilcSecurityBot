import requests
import re
from time import time, sleep
from random import choice, randint
from os import path, remove, makedirs, listdir
# JSON Library
from json import JSONDecodeError, dumps as json_dumps
from typing import Optional, List

from multicolorcaptcha import CaptchaGenerator

from telegram import (
    Message, Update, Bot, User, Chat, InlineKeyboardMarkup,
    InlineKeyboardButton, ParseMode, InputMediaPhoto
)

from telegram.error import TelegramError, BadRequest

from telegram.ext import (
    run_async, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
)

from tg_bot.modules.helper_funcs.filters import CustomFilters
from tg_bot.modules.helper_funcs.commons import is_int
from tg_bot.modules.helper_funcs.misc import build_keyboard, revert_buttons
from telegram.utils.helpers import escape_markdown, mention_markdown
from tg_bot.modules.helper_funcs.string_handling import markdown_parser, \
    escape_invalid_curly_brackets

from tg_bot.modules.sql import spam_shield_sql
from tg_bot.modules.sql import rules_sql
from tg_bot.modules.sql import welcome_sql
from tg_bot.modules.welcome import (
    ENUM_FUNC_MAP, VALID_WELCOME_FORMATTERS
)

from tg_bot import (
    dispatcher,
    LOGGER,
    OWNER_ID,
    CAPTCHAS_DIR,
    CHATS_DIR,
    INIT_CAPTCHA_DIFFICULTY_LEVEL,
    INIT_CAPTCHA_TIME_MIN,
    F_CONF,
    INIT_CAPTCHA_CHARS_MODE,
    MAX_CONFIG_CAPTCHA_TIME,
    INIT_TITLE,
    INIT_LINK,
    INIT_ENABLE,
    MAX_FAIL_BAN_POLL,
    SW_API
)
from tg_bot.modules.helper_funcs.chat_status import (
    user_admin,
    is_user_admin,
    bot_admin,
    can_delete
)
from tg_bot.modules.log_channel import loggable

# Error Traceback Library
from traceback import format_exc

# Thread-Safe JSON Library
from tg_bot.tsjson import TSjson

# Commons Library
from tg_bot.commons import add_lrm, list_remove_element

from tg_bot.tlgbotutils import (
    tlg_get_msg,
    tlg_ban_user,
    tlg_delete_msg,
    tlg_send_msg,
    tlg_kick_user
)

# Collections Data Types Library
from collections import OrderedDict

class Globals():
    '''Global Elements Container.'''

    files_config_list: list = []
    to_delete_in_time_messages_list: list = []
    new_users: dict = {}
    # connections: dict = {}
    # async_captcha_timeout: Optional[CoroutineType] = None
    # async_auto_delete_messages: Optional[CoroutineType] = None
    force_exit: bool = False

# Global Data Elements
Global = Globals()

# Create Captcha Generator object of specified size (2 -> 640x360)
CaptchaGen = CaptchaGenerator(2)

def get_default_config_data():
    '''
    Get default config data structure.
    '''
    config_data = OrderedDict([
        ("Title", INIT_TITLE),
        ("Link", INIT_LINK),
        # ("Language", CONST["INIT_LANG"]),
        ("Enabled", INIT_ENABLE),
        # ("URL_Enabled", CONST["INIT_URL_ENABLE"]),
        # ("RM_All_Msg", CONST["INIT_RM_ALL_MSG"]),
        ("Captcha_Chars_Mode", INIT_CAPTCHA_CHARS_MODE),
        ("Captcha_Time", INIT_CAPTCHA_TIME_MIN * 60),
        ("Captcha_Difficulty_Level", INIT_CAPTCHA_DIFFICULTY_LEVEL),
        ("Fail_Restriction", "kick"),
        # ("Restrict_Non_Text", CONST["INIT_RESTRICT_NON_TEXT_MSG"]),
        # ("Rm_Welcome_Msg", CONST["INIT_RM_WELCOME_MSG"]),
        # ("Welcome_Msg", "-"),
        # ("Welcome_Time", CONST["T_DEL_WELCOME_MSG"]),
        # ("Ignore_List", [])
    ])
    return config_data

def get_chat_config(chat_id, param):
    '''
    Get specific stored chat configuration property.
    '''
    file = get_chat_config_file(chat_id)
    if file:
        config_data = file.read()
        if (not config_data) or (param not in config_data):
            config_data = get_default_config_data()
            save_config_property(chat_id, param, config_data[param])
    else:
        config_data = get_default_config_data()
        save_config_property(chat_id, param, config_data[param])
    return config_data[param]

def get_chat_config_file(chat_id):
    '''
    Determine chat config file from the list by ID. Get the file if
    exists or create it if not.
    '''
    file = OrderedDict([("ID", chat_id), ("File", None)])
    found = False
    if Global.files_config_list:
        for chat_file in Global.files_config_list:
            if chat_file["ID"] == chat_id:
                file = chat_file
                found = True
                break
        if not found:
            chat_config_file_name = \
                    f'{CHATS_DIR}/{chat_id}/{F_CONF}'
            file["ID"] = chat_id
            file["File"] = TSjson(chat_config_file_name)
            Global.files_config_list.append(file)
    else:
        chat_config_file_name = \
                f'{CHATS_DIR}/{chat_id}/{F_CONF}'
        file["ID"] = chat_id
        file["File"] = TSjson(chat_config_file_name)
        Global.files_config_list.append(file)
    return file["File"]

def save_config_property(chat_id, param, value):
    '''
    Store actual chat configuration in file.
    '''
    fjson_config = get_chat_config_file(chat_id)
    config_data = fjson_config.read()
    if not config_data:
        config_data = get_default_config_data()
    if (param in config_data) and (value == config_data[param]):
        return
    config_data[param] = value
    fjson_config.write(config_data)

def get_all_chat_config(chat_id):
    '''
    Get specific stored chat configuration property.
    '''
    file = get_chat_config_file(chat_id)
    if file:
        config_data = file.read()
        if not config_data:
            config_data = get_default_config_data()
    else:
        config_data = get_default_config_data()
    return config_data

def cmd_checkcfg(bot: Bot, update: Update):
    '''
    Command /captchacfg message handler.
    '''
    chat_id = update.effective_chat.id  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user_id = update.effective_user.id  # type: Optional[User]

    tlg_autodelete_msg(message)
    # Get Group Chat ID
    group_id = chat_id
    group_cfg = get_all_chat_config(group_id)
    group_cfg = json_dumps(group_cfg, indent=4, sort_keys=True)
    tlg_send_msg(
            bot, chat_id,
            "Group Captcha Configuration:\n————————————————\n```\n{}\n```".format(group_cfg),
            parse_mode="MARKDOWN")

def auto_delete_messages(bot):
    '''
    Handle remove messages sent by the Bot with the timed auto-delete
    function.
    '''
    while not Global.force_exit:
        # Release CPU sleeping on each iteration
        sleep(0.01)
        # Check each Bot sent message
        i = 0
        while i < len(Global.to_delete_in_time_messages_list):
            # Check for break iterating if script must exit
            if Global.force_exit:
                return
            sent_msg = Global.to_delete_in_time_messages_list[i]
            # Sleep each 100 iterations
            i = i + 1
            if (i > 1) and ((i % 1000) == 0):
                sleep(0.01)
            # Check if delete time has arrive for this message
            if time() - sent_msg["time"] < sent_msg["delete_time"]:
                continue
            # Delete message
            delete_result: dict = {}
            delete_result["error"] = ""
            if sent_msg["Msg_id"] is not None:
                try:
                    bot.delete_message(sent_msg["Chat_id"], sent_msg["Msg_id"])
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(sent_msg["Chat_id"]), delete_result["error"])
            list_remove_element(
                    Global.to_delete_in_time_messages_list, sent_msg)
            sleep(0.01)
    LOGGER.info("Auto-delete messages coroutine finished")

def create_image_captcha(chat_id, file_name, difficult_level, captcha_mode):
    '''
    Generate an image captcha from pseudo numbers.
    '''
    # If it doesn't exists, create captchas folder to store them
    img_dir_path = f'{CAPTCHAS_DIR}/{chat_id}'
    img_file_path = f'{img_dir_path}/{file_name}.png'
    # if not path.exists(CAPTCHABOT_CAPTCHAS_DIR):
    #     makedirs(CAPTCHABOT_CAPTCHAS_DIR)
    # else:
    if not path.exists(img_dir_path):
        makedirs(img_dir_path)
    else:
        # If the captcha file exists remove it
        if path.exists(img_file_path):
            remove(img_file_path)
    # Generate and save the captcha with a random background
    # mono-color or multi-color
    captcha_result = {
        "image": img_file_path,
        "characters": "",
        "equation_str": "",
        "equation_result": ""
    }
    if captcha_mode == "math":
        captcha = CaptchaGen.gen_math_captcha_image(2, bool(randint(0, 1)))
        captcha_result["equation_str"] = captcha["equation_str"]
        captcha_result["equation_result"] = captcha["equation_result"]
    else:
        captcha = CaptchaGen.gen_captcha_image(
            difficult_level, captcha_mode, bool(randint(0, 1)))
        captcha_result["characters"] = captcha["characters"]
    captcha["image"].save(img_file_path, "png")
    return captcha_result

@run_async
@bot_admin
def cmd_captcha(bot: Bot, update: Update):
    '''
    Command /captcha message handler. Useful to test.
    Just Bot Owner can use it.
    '''
    user_alias = ""
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]

    if user.username is not None:
        user_alias = f"@{user.username}"

    if (int(user.id) != OWNER_ID):
        message.reply_text("Only Bot Owners can use this command")
        return
    # Generate a random difficulty captcha
    difficulty = randint(1, 5)
    captcha_mode = choice(["nums", "hex", "ascii", "math"])
    captcha = create_image_captcha(chat.id, user.id, difficulty, captcha_mode)
    if captcha_mode == "math":
        captcha_code = \
                f'{captcha["equation_str"]} = {captcha["equation_result"]}'
    else:
        captcha_code = captcha["characters"]
    LOGGER.info("[%s] Sending captcha msg: %s", chat.id, captcha_code)
    # Note: Img caption must be <= 1024 chars
    img_caption = (f"Captcha Level: {difficulty}\n"
                   f"Captcha Mode: {captcha_mode}\n"
                   f"Captcha Code: {captcha_code}")
    # Send the image
    sent_result: dict = {}
    sent_result["msg"] = None
    try:
        with open(captcha["image"], "rb") as file_image:
            update.effective_message.reply_photo(
                caption=img_caption,
                photo=file_image
            )
    except Exception:
        LOGGER.error(format_exc())
        LOGGER.error("Fail to send image to Telegram")
    # Remove sent captcha image file from file system
    if path.exists(captcha["image"]):
        remove(captcha["image"])

@run_async
@user_admin
@bot_admin
def cmd_enable(bot: Bot, update: Update):
    '''
    Command /captchaenable message handler.
    '''
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]

    chat_id = chat.id
    user_id = user.id

    # Check and enable captcha protection in the chat
    enable = get_chat_config(chat_id, "Enabled")
    if enable:
        bot_msg = "The captcha protection is already enabled."
    else:
        enable = True
        save_config_property(chat_id, "Enabled", enable)
        bot_msg = "Captcha protection enabled. Disable it with /captchadisable command."
    tlg_send_autodelete_msg(
            bot, chat_id, bot_msg)

@run_async
@user_admin
@bot_admin
def cmd_disable(bot: Bot, update: Update):
    '''
    Command /captchadisable message handler.
    '''
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]

    chat_id = chat.id
    user_id = user.id
    # Check and disable captcha protection in the chat
    enable = get_chat_config(chat_id, "Enabled")
    if not enable:
        bot_msg = "The captcha protection is already disabled."
    else:
        enable = False
        save_config_property(chat_id, "Enabled", enable)
        bot_msg = "Captcha protection disabled. Enable it with /captchaenable command."
    tlg_send_autodelete_msg(
            bot, chat_id, bot_msg)

@run_async
@user_admin
@bot_admin
def cmd_difficulty(bot: Bot, update: Update, args: List[str]):
    '''
    Command /captchadifficulty message handler.
    '''
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    chat_id = chat.id
    user_id = user.id
    group_id = chat_id
    # Check if no argument was provided with the command
    if len(args) > 0:
        if is_int(args[0]):
            new_difficulty = int(args[0])
            new_difficulty = max(new_difficulty, 1)
            new_difficulty = min(new_difficulty, 5)
            save_config_property(
                    group_id, "Captcha_Difficulty_Level", new_difficulty)
            bot_msg = "Captcha difficulty successfully changed to level {}.".format(new_difficulty)
        else:
            bot_msg = "The provided captcha difficulty is not a number."

        message.reply_text(bot_msg)
    else:
        message.reply_text("The command needs a difficulty level to set (from 1 to 5). Has no effect in \"button\" mode.\n\nExamples:\n/captchadifficulty 1\n/captchadifficulty 2\n/captchadifficulty 3\n/captchadifficulty 4\n/captchadifficulty 5")

@run_async
@user_admin
@bot_admin
def cmd_captcha_mode(bot: Bot, update: Update, args: List[str]):
    '''
    Command /captchamode message handler.
    '''
    chat_id = update.effective_chat.id  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user_id = update.effective_user.id  # type: Optional[User]

    group_id = chat_id
    # Check if no argument was provided with the command
    if (args is None) or (len(args) == 0):
        message.reply_text("The command needs a mode to set.\nAvailable modes are:\n\n- Numeric Captchas (\"nums\").\n- Hexadecimal Captchas, numbers and characters A-F (\"hex\").\n- Numbers and characters A-Z Captchas (\"ascii\").\n- Math equation to be solved Captchas (\"math\").\n- Button-only challenge (\"button\").\n- Random challenge (\"random\").\n\nExamples:\n/captchamode nums\n/captchamode hex\n/captchamode ascii\n/captchamode math\n/captchamode button\n/captchamode random"
        )
        return
    # Get and configure chat to provided captcha mode
    new_captcha_mode = args[0].lower()
    if (new_captcha_mode in
            {"button", "nums", "hex", "ascii", "math", "random"}):
        save_config_property(group_id, "Captcha_Chars_Mode", new_captcha_mode)
        bot_msg = "Captcha mode successfully changed to \"{}\".".format(new_captcha_mode)
    else:
        bot_msg = "Invalid captcha mode. Supported modes are: \"nums\", \"hex\", \"ascii\", \"math\", \"button\" and \"random\".\n\nExample:\n/captchamode nums\n/captchamode hex\n/captchamode ascii\n/captchamode math\n/captchamode button\n/captchamode random"
    message.reply_text(bot_msg)

@run_async
@user_admin
@bot_admin
def cmd_time(bot: Bot, update: Update, args: List[str]):
    '''
    Command /captchatime message handler.
    '''
    chat_id = update.effective_chat.id  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]
    user_id = update.effective_user.id  # type: Optional[User]
    group_id = chat_id
    if (args is None) or (len(args) == 0):
        message.reply_text("The command needs a time value to set.\n\nExamples:\n/captchatime 30 sec\n/captchatime 5 min\n/captchatime 1 min")
        return
    # Check if provided time argument is not a number
    if not is_int(args[0]):
        message.reply_text("The provided time is not an integer number.")
        return
    # Get time arguments
    new_time = int(args[0])
    min_sec = "min"
    if len(args) > 1:
        min_sec = args[1].lower()
    # Check if time format is not minutes or seconds
    # Convert time value to seconds if min format
    if min_sec in ["m", "min", "mins", "minutes"]:
        min_sec = "min"
        new_time_str = f"{new_time} min"
        new_time = new_time * 60
    elif min_sec in ["s", "sec", "secs", "seconds"]:
        min_sec = "sec"
        new_time_str = f"{new_time} sec"
    else:
        message.reply_text("The command needs a time value to set.\n\nExamples:\n/time 30 sec\n/time 5 min\n/time 1 min")
        return
    # Check if time value is out of limits (less than 10s)
    if new_time < 10:
        msg_text = "Invalid time, it needs to be in range 10 sec to {} min.".format(
                MAX_CONFIG_CAPTCHA_TIME)
        message.reply_text(msg_text)
        return
    if new_time > MAX_CONFIG_CAPTCHA_TIME * 60:
        msg_text = "Invalid time, it needs to be in range 10 sec to {} min.".format(
                MAX_CONFIG_CAPTCHA_TIME)
        message.reply_text(msg_text)
        return
    # Set the new captcha time
    save_config_property(group_id, "Captcha_Time", new_time)
    msg_text = "Time to solve the captcha successfully changed to {}.".format(new_time_str)
    message.reply_text(msg_text)

def tlg_send_autodelete_msg(
        bot,
        chat_id,
        message,
        time_delete_sec=20
        ):
    '''
    Send a telegram message that will be auto-delete in specified time.
    '''
    sent_result: dict = {}
    sent_result["msg"] = None
    sent_result["error"] = ""
    try:
        msg = bot.send_message(chat_id=chat_id, text=message)
        LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
        sent_result["msg"] = msg
    except TelegramError as error:
        sent_result["error"] = str(error)
        LOGGER.error("[%s] %s", str(chat_id), str(error))
    if sent_result["msg"] is None:
        return None
    tlg_autodelete_msg(sent_result["msg"], time_delete_sec)
    return sent_result["msg"].message_id

def button_request_another_captcha_press(bot, query, chat_id):
    '''
    Button "Another captcha" pressed handler.
    '''
    # Get query data
    chat = bot.get_chat(chat_id)
    user_id = query.from_user.id
    msg_id = query.message.message_id
    user_name = query.from_user.full_name
    # If has an alias, just use the alias
    if query.from_user.username is not None:
        user_name = f"@{query.from_user.username}"
    chat_title = chat.title
    # Add an unicode Left to Right Mark (LRM) to chat title
    # (fix for arabic, hebrew, etc.)
    chat_title = add_lrm(chat_title)
    # Ignore if message is not from a new user that has not
    # completed the captcha yet
    if int(chat_id) not in Global.new_users:
        return
    if int(user_id) not in Global.new_users[int(chat_id)]:
        return

    LOGGER.info("[%s] User %s requested a new captcha.", chat_id, user_name)
    # Prepare inline keyboard button to let user request another captcha
    keyboard = [[
            InlineKeyboardButton(
                    "Other Captcha",
                    callback_data=f"captcha_image({int(query.from_user.id)},{chat_id})")
            ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Get captcha timeout
    captcha_timeout = get_chat_config(chat_id, "Captcha_Time")
    if captcha_timeout < 60:
        timeout_str = f"{captcha_timeout} sec"
    else:
        timeout_min = int(captcha_timeout / 60)
        timeout_str = f"{timeout_min} min"
    # Get current chat configurations
    captcha_level = get_chat_config(chat_id, "Captcha_Difficulty_Level")
    captcha_mode = \
        Global.new_users[int(chat_id)][int(user_id)]["join_data"]["captcha_mode"]
    # Use nums mode if captcha_mode was changed while captcha was
    # in progress
    if captcha_mode not in {"nums", "hex", "ascii", "math"}:
        captcha_mode = "nums"
    # Generate a new captcha and edit previous captcha image message
    captcha = create_image_captcha(
                chat_id, user_id, captcha_level, captcha_mode)
    if captcha_mode == "math":
        captcha_num = captcha["equation_result"]
        LOGGER.info(
                "[%s] Sending new captcha msg: %s = %s...",
                chat_id, captcha["equation_str"], captcha_num)
        img_caption = "Hello {}, welcome to {}. Please write a message with the result of this math equation to verify that you are a human. If you don't solve this captcha in {}, you will be automatically kicked out of the group.".format(
                user_name, chat_title, timeout_str)
    else:
        captcha_num = captcha["characters"]
        LOGGER.info(
                "[%s] Sending new captcha msg: %s...",
                chat_id, captcha_num)
        img_caption = "Hello {}, welcome to {}. Please write a message with the numbers and/or letters that appear in this image to verify that you are a human. If you don't solve this captcha in {}, you will be automatically kicked out of the group.".format(
                user_name, chat_title, timeout_str)
    # Read and send image
    edit_result = {}
    try:
        with open(captcha["image"], "rb") as file_img:
            input_media = InputMediaPhoto(media=file_img, caption=img_caption)
            edit_result: dict = {}
            edit_result["error"] = ""
            try:
                bot.edit_message_media(
                                    user_id, msg_id, media=input_media,
                                    reply_markup=reply_markup)
            except Exception as error:
                edit_result["error"] = str(error)
                LOGGER.error("[%s] %s", str(chat_id), str(error))

        if edit_result["error"] == "":
            # Set and modified to new expected captcha number
            Global.new_users[int(chat_id)][int(user_id)]["join_data"]["captcha_num"] = \
                    captcha_num
            # Remove sent captcha image file from file system
            if path.exists(captcha["image"]):
                remove(captcha["image"])
    except Exception:
        LOGGER.error(format_exc())
        LOGGER.error("Fail to update image for Telegram")
    LOGGER.info("[%s] New captcha request process completed.", chat_id)

def send(bot, chat_id, message, keyboard, backup_message):
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
            LOGGER.warning(keyboard)
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

def welcome_message(bot, chat_id, user_id):
    chat = bot.get_chat(chat_id)

    should_welc, cust_welcome, welc_type = welcome_sql.get_welc_pref(chat_id)
    if should_welc:
        sent = None
        new_mem = bot.get_chat(user_id)
        # for new_mem in new_members:
            # Give the owner a special welcome
            # if new_mem.id == OWNER_ID:
            #     update.effective_message.reply_text("Master is in the houseeee, let's get this party started!")
            #     continue

            # Don't welcome yourself
            # elif new_mem.id == bot.id:
            #     continue

            # else:
        # If welcome message is media, send with appropriate function
        if welc_type != welcome_sql.Types.TEXT and welc_type != welcome_sql.Types.BUTTON_TEXT:
            ENUM_FUNC_MAP[welc_type](chat_id, cust_welcome)
            return
        # else, move on
        first_name = new_mem.first_name or "PersonWithNoName"  # edge case of empty name - occurs for some bugs.

        if cust_welcome:
            if new_mem.last_name:
                fullname = "{} {}".format(first_name, new_mem.last_name)
            else:
                fullname = first_name
            count = chat.get_members_count()
            mention = mention_markdown(user_id, escape_markdown(first_name))
            if new_mem.username:
                username = "@" + escape_markdown(new_mem.username)
            else:
                username = mention

            valid_format = escape_invalid_curly_brackets(cust_welcome, VALID_WELCOME_FORMATTERS)

            if not valid_format:
                return

            res = valid_format.format(first=escape_markdown(first_name),
                                      last=escape_markdown(new_mem.last_name or first_name),
                                      fullname=escape_markdown(fullname), username=username, mention=mention,
                                      count=count, chatname=escape_markdown(chat.title), id=new_mem.id)
            buttons = welcome_sql.get_welc_buttons(chat_id)
            keyb = build_keyboard(buttons)
        else:
            res = welcome_sql.DEFAULT_WELCOME.format(first=first_name)
            keyb = []

        keyboard = InlineKeyboardMarkup(keyb)

        sent = send(bot, chat_id, res, keyboard,
                    welcome_sql.DEFAULT_WELCOME.format(first=first_name))  # type: Optional[Message]

        if can_delete(chat, bot.id):
            del_join = welcome_sql.get_del_pref(chat_id)
            if del_join:
                bot.delete_message(chat_id, sent.message_id)
                try:
                    sent.delete()
                except BadRequest as excp:
                    pass

        prev_welc = welcome_sql.get_clean_pref(chat_id)
        if prev_welc:
            try:
                bot.delete_message(chat_id, prev_welc)
            except BadRequest as excp:
                pass

            if sent:
                welcome_sql.set_clean_welcome(chat_id, sent.message_id)

@run_async
def button(bot: Bot, update: Update):
    query = update.callback_query
    msg_id = query.message.message_id
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

    rules_accepted = re.match(r"rules_accept\((.+?),(.+?)\)", query.data)
    rules_declined = re.match(r"rules_decline\((.+?),(.+?)\)", query.data)

    if rules_accepted:
        user_id = rules_accepted.group(1)
        chat_id = rules_accepted.group(2)
        user_name = Global.new_users[int(chat_id)][int(user_id)]["join_data"]["user_name"]
        chat = bot.get_chat(chat_id)
        chat_title = chat.title

        bot.delete_message(user_id, msg_id)
        # Ignore if request doesn't come from a new user in captcha process
        if int(chat_id) not in Global.new_users:
            return
        if int(user_id) not in Global.new_users[int(chat_id)]:
            return
        # Remove previous join messages in group
        if "msg_to_rm" in Global.new_users[int(chat_id)][int(user_id)]:
            for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm"]:
                delete_result: dict = {}
                delete_result["error"] = ""
                try:
                    bot.delete_message(chat_id, msg)
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        # Remove captcha messages in PM
        if "msg_to_rm_pm" in Global.new_users[int(chat_id)][int(user_id)]:
            for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm_pm"]:
                delete_result: dict = {}
                delete_result["error"] = ""
                try:
                    bot.delete_message(user_id, msg)
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        # Remove user from captcha process
        del Global.new_users[int(chat_id)][int(user_id)]

        # Remove all restrictions on the user
        bot.restrict_chat_member(chat_id, user_id, until_date=None, can_send_messages=True)
        # Send captcha solved message
        bot_msg = "User verified.\nYou can now return to the <a href='{}'>@{}</a> group, {}".format(chat.invite_link, chat_title, user_name)
        bot.send_message(user_id, bot_msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        LOGGER.info("[%s] User verified and rules accepted.", chat_id)
        welcome_message(bot, chat_id, user_id)


    if rules_declined:
        user_id = rules_declined.group(1)
        chat_id = rules_declined.group(2)
        user_name = Global.new_users[int(chat_id)][int(user_id)]["join_data"]["user_name"]
        bot.delete_message(user_id, msg_id)
        # Ignore if request doesn't come from a new user in captcha process
        if int(chat_id) not in Global.new_users:
            return
        if int(user_id) not in Global.new_users[int(chat_id)]:
            return
        # Remove previous join messages in group
        if "msg_to_rm" in Global.new_users[int(chat_id)][int(user_id)]:
            for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm"]:
                delete_result: dict = {}
                delete_result["error"] = ""
                try:
                    bot.delete_message(chat_id, msg)
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        # Remove captcha messages in PM
        if "msg_to_rm_pm" in Global.new_users[int(chat_id)][int(user_id)]:
            for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm_pm"]:
                delete_result: dict = {}
                delete_result["error"] = ""
                try:
                    bot.delete_message(user_id, msg)
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        LOGGER.info(
                "[%s] User %s declined rules.",
                chat_id, user_name)
        captcha_fail_member_kick(bot, int(chat_id), int(user_id), user_name)

# Do not async - not from a handler
def join_send_rules(bot, chat_id, user_id, user_name):
    chat = bot.get_chat(chat_id)
    rules = rules_sql.get_rules(chat_id)
    chat_title = chat.title
    # Add an unicode Left to Right Mark (LRM) to chat title (fix for
    # arabic, hebrew, etc.)
    chat_title = add_lrm(chat_title)
    text = "Please read the rules for *{}* and accept to continue:\n\n{}".format(escape_markdown(chat.title), rules)

    keyboard = [[InlineKeyboardButton("Accept", callback_data=f"rules_accept({int(user_id)},{chat_id})"),
                 InlineKeyboardButton("Decline", callback_data=f"rules_decline({int(user_id)},{chat_id})")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # if there is rules and captcha is enable or disabled
    if rules:
        bot.send_message(user_id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else: # if no rules but captcha is enabled
        # Ignore if request doesn't come from a new user in captcha process
        if int(chat_id) not in Global.new_users:
            return
        if int(user_id) not in Global.new_users[int(chat_id)]:
            return
        # Remove previous join messages in group
        if "msg_to_rm" in Global.new_users[int(chat_id)][int(user_id)]:
            for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm"]:
                delete_result: dict = {}
                delete_result["error"] = ""
                try:
                    bot.delete_message(chat_id, msg)
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        # Remove captcha messages in PM
        if "msg_to_rm_pm" in Global.new_users[int(chat_id)][int(user_id)]:
            for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm_pm"]:
                delete_result: dict = {}
                delete_result["error"] = ""
                try:
                    bot.delete_message(user_id, msg)
                except Exception as error:
                    delete_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        # Remove user from captcha process
        del Global.new_users[int(chat_id)][int(user_id)]
        # Remove all restrictions on the user
        bot.restrict_chat_member(chat_id, user_id, until_date=None, can_send_messages=True)
        # Send captcha solved message
        bot_msg = "User verified.\nYou can now return to the <a href='{}'>@{}</a> group, {}".format(chat.invite_link, chat_title, user_name)
        bot.send_message(user_id, bot_msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        LOGGER.info("[%s] User verified and rules accepted.", chat_id)

        welcome_message(bot, chat_id, user_id)

def button_im_not_a_bot_press(bot, query, chat_id):
    '''
    Button "I'm not a bot" pressed handler.
    '''
    # Get query data
    chat = bot.get_chat(chat_id)
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    # If has an alias, just use the alias
    if query.from_user.username is not None:
        user_name = f"@{query.from_user.username}"
    chat_title = chat.title
    # Add an unicode Left to Right Mark (LRM) to chat title (fix for
    # arabic, hebrew, etc.)
    chat_title = add_lrm(chat_title)
    # Ignore if request doesn't come from a new user in captcha process
    # if int(chat_id) not in Global.new_users:
    #     return
    # if int(user_id) not in Global.new_users[int(chat_id)]:
    #     return
    # # Remove previous join messages in group
    # for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm"]:
    #     delete_result: dict = {}
    #     delete_result["error"] = ""
    #     try:
    #         bot.delete_message(chat_id, msg)
    #     except Exception as error:
    #         delete_result["error"] = str(error)
    #         LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])
    #
    # Remove captcha messages in PM
    for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm_pm"]:
        delete_result: dict = {}
        delete_result["error"] = ""
        try:
            bot.delete_message(user_id, msg)
        except Exception as error:
            delete_result["error"] = str(error)
            LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

    LOGGER.info(
            "[%s] User %s solved a button-only challenge.",
            chat_id, user_name)
    join_send_rules(bot, chat_id, user_id, user_name)

@run_async
def button_press_rx(bot: Bot, update: Update):
    '''
    Inline Keyboard Button pressed handler.
    '''
    query = update.callback_query
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
    # Convert query provided data into list
    another_captcha = re.match(r"captcha_image\((.+?),(.+?)\)", query.data)
    button_pressed = re.match(r"captcha_button\((.+?),(.+?)\)", query.data)
    if another_captcha:
        user_id = another_captcha.group(1)
        chat_id = another_captcha.group(2)
        if user_id != str(query.from_user.id):
            return
        button_request_another_captcha_press(bot, query, chat_id)

    if button_pressed:
        user_id = button_pressed.group(1)
        chat_id = button_pressed.group(2)
        if user_id != str(query.from_user.id):
            return
        button_im_not_a_bot_press(bot, query, chat_id)

def tlg_autodelete_msg(message, time_delete_sec=10):
    '''
    Add a telegram message to be auto-delete in specified time.
    '''
    # Check if provided message has all necessary attributes
    if message is None:
        return False
    if not hasattr(message, "chat_id"):
        return False
    if not hasattr(message, "message_id"):
        return False
    if not hasattr(message, "from_user"):
        return False
    if not hasattr(message.from_user, "id"):
        return False
    # Get sent message ID and calculate delete time
    chat_id = message.chat_id
    user_id = message.from_user.id
    msg_id = message.message_id
    _t0 = time()
    # Add sent message data to to-delete messages list
    sent_msg_data = OrderedDict(
        [
            ("Chat_id", None), ("User_id", None), ("Msg_id", None),
            ("time", None), ("delete_time", None)
        ]
    )
    sent_msg_data["Chat_id"] = chat_id
    sent_msg_data["User_id"] = user_id
    sent_msg_data["Msg_id"] = msg_id
    sent_msg_data["time"] = _t0
    sent_msg_data["delete_time"] = time_delete_sec
    Global.to_delete_in_time_messages_list.append(sent_msg_data)
    return True

def is_captcha_num_solve(captcha_mode, msg_text, solve_num):
    '''
    Check if number send by user solves a num/hex/ascii/math captcha.
    - For "math", the message must be the exact math equation result
    number.
    - For other mode, the message must contains the numbers.
    '''
    if captcha_mode == "math":
        if msg_text == solve_num:
            return True
    else:
        if solve_num.lower() in msg_text.lower():
            return True
        # Check if the message is the valid number but with spaces
        if len(msg_text) == len("1 2 3 4"):
            solve_num_with_spaces = " ".join(solve_num)
            if solve_num_with_spaces.lower() == msg_text.lower():
                return True
    return False

def captcha_fail_member_mute(bot, chat_id, user_id, user_name):
    '''
    Restrict the user to deny send any kind of message for 24h.
    '''
    user_name = Global.new_users[chat_id][user_id]["join_data"]["user_name"]
    mute_until_24h = get_unix_epoch() + 86400
    LOGGER.info("[%s] Captcha Fail - Mute - %s (%s)",
                chat_id, user_name, user_id)
    success = bot.restrict_chat_member(chat_id, join_user_id, until_date=mute_until_24h, can_send_messages=False)
    if success:
        msg_text = "The user {} failed to resolve the captcha. The \"user\" was muted and won't be able to send messages for 24h.".format(user_name)
    else:
        msg_text = "Warning: User {} fail to solve the captcha, but I was not able to restrict/remove the user.".format(user_name)
    sent_result: dict = {}
    sent_result["msg"] = None
    sent_result["error"] = ""
    try:
        msg = bot.send_message(
                        chat_id=chat_id,
                        text=msg_text)
        LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
        sent_result["msg"] = msg
    except TelegramError as error:
        sent_result["error"] = str(error)
        LOGGER.error("[%s] %s", str(chat_id), str(error))

def captcha_fail_member_kick(bot, chat_id, user_id, user_name):
    '''
    Kick or Ban the user from the group.
    '''
    banned = False
    max_join_retries = MAX_FAIL_BAN_POLL
    # Get parameters
    join_retries = \
        Global.new_users[chat_id][user_id]["join_data"]["join_retries"]
    LOGGER.info("[%s] %s join_retries: %d", chat_id, user_id, join_retries)
    # Kick if user has fail to solve the captcha less than
    # "max_join_retries"
    if join_retries < max_join_retries:
        LOGGER.info("[%s] Captcha Fail - Kick - %s (%s)",
                    chat_id, user_name, user_id)
        # Try to kick the user
        kick_result = tlg_kick_user(bot, chat_id, user_id)
        if kick_result["error"] == "":
            # Kick success
            join_retries = join_retries + 1
            msg_text = "The user {} failed to resolve the captcha. The \"user\" was kicked out.".format(user_name)
            sent_result: dict = {}
            sent_result["msg"] = None
            sent_result["error"] = ""
            try:
                msg = bot.send_message(
                                chat_id=chat_id,
                                text=msg_text)
                LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
                sent_result["msg"] = msg
            except TelegramError as error:
                sent_result["error"] = str(error)
                LOGGER.error("[%s] %s", str(chat_id), str(error))
        else:
            # Kick fail
            LOGGER.info("[%s] Unable to kick", chat_id)
            if ((kick_result["error"] == "The user has left the group") or
                    (kick_result["error"] == "The user was already kicked")):
                # The user is not in the chat
                msg_text = "I tried to kick out \"User\" {}, but is not in the group any more (has left the group or has been kicked out by an Admin).".format(
                        user_name)
                sent_result: dict = {}
                sent_result["msg"] = None
                sent_result["error"] = ""
                try:
                    msg = bot.send_message(
                                    chat_id=chat_id,
                                    text=msg_text)
                    LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
                    sent_result["msg"] = msg
                except TelegramError as error:
                    sent_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), str(error))
            elif kick_result["error"] == \
                    "Not enough rights to restrict/unrestrict chat member":
                # Bot has no privileges to kick
                msg_text = "I tried to kick out \"User\" {}, but I don't have administration rights to kick out users from the group.".format(
                        user_name)
                # Send no rights for kick message without auto-remove
                sent_result: dict = {}
                sent_result["msg"] = None
                sent_result["error"] = ""
                try:
                    msg = bot.send_message(
                                    chat_id=chat_id,
                                    text=msg_text)
                    LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
                    sent_result["msg"] = msg
                except TelegramError as error:
                    sent_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), str(error))
            else:
                # For other reason, the Bot can't ban
                msg_text = "I tried to kick out \"User\" {}, but due to an unexpected problem (maybe network/server related), I can't do it.".format(user_name)
                sent_result: dict = {}
                sent_result["msg"] = None
                sent_result["error"] = ""
                try:
                    msg = bot.send_message(
                                    chat_id=chat_id,
                                    text=msg_text)
                    LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
                    sent_result["msg"] = msg
                except TelegramError as error:
                    sent_result["error"] = str(error)
                    LOGGER.error("[%s] %s", str(chat_id), str(error))
    # Ban if user has join "max_join_retries" times without solving
    # the captcha
    else:
        LOGGER.info("[%s] Captcha Fail - Ban - %s (%s)",
                    chat_id, user_name, user_id)
        # Try to ban the user and notify Admins
        ban_result = tlg_ban_user(bot, chat_id, user_id)
        if ban_result["error"] == "":
            # Ban success
            banned = True
            msg_text = "Warning: The user {} tried and failed to resolve the captcha {} times. The \"user\" was considered a Bot and banned. To let this \"user\" enter again, an Admin has to manually remove it restrictions from the group settings.".format(
                    user_name, max_join_retries)
        else:
            # Ban fail
            if ban_result["error"] == "User not found":
                # The user is not in the chat
                msg_text = "Warning: The user {} tried and failed to resolve the captcha {} times. I tried to ban the \"user\", but the user is not in the group any more (has left the group or has been kicked out/banned by an Admin).".format(
                        user_name, max_join_retries)
            elif ban_result["error"] \
                    == "Not enough rights to restrict/un-restrict chat member":
                # Bot has no privileges to ban
                msg_text = "Warning: The user {} tried and failed to resolve the captcha {} times. I tried to ban the \"user\", but I don't have administration rights to ban users in the group.".format(
                        user_name, max_join_retries)
            else:
                # For other reason, the Bot can't ban
                msg_text = "Warning: The user {} tried and failed to resolve the captcha {} times. I tried to ban the \"user\", but due to an unexpected problem (maybe network/server related), I can't do it.".format(
                        user_name, max_join_retries)
        # Send ban notify message
        LOGGER.info("[%s] %s", chat_id, msg_text)
        if rm_result_msg:
            tlg_send_autodelete_msg(bot, chat_id, msg_text)
        else:
            tlg_send_msg(bot, chat_id, msg_text)
    # Update user info (join_retries & kick_ban)
    try:
        Global.new_users[chat_id][user_id]["join_data"]["kicked_ban"] = True
        Global.new_users[chat_id][user_id]["join_data"]["join_retries"] = \
            join_retries
        # Delete user join info if ban was success
        if banned:
            del Global.new_users[chat_id][user_id]
    except KeyError:
        LOGGER.warning(
                "[%s] %s (%d) not in new_users list (already solve captcha)",
                chat_id, user_name, user_id)

def captcha_fail_member(bot, chat_id, user_id):
    '''
    Restrict (Kick, Ban, mute, etc) a new member that has fail to solve
    the captcha.
    '''
    user_name = Global.new_users[chat_id][user_id]["join_data"]["user_name"]
    restriction = get_chat_config(chat_id, "Fail_Restriction")
    if restriction == "mute":
        captcha_fail_member_mute(bot, chat_id, user_id, user_name)
    else:  # restriction == CMD["RESTRICTION"]["KICK"]
        captcha_fail_member_kick(bot, chat_id, user_id, user_name)
    # Remove join messages
    try:
        LOGGER.info("[%s] Removing msgs from user %s...", chat_id, user_name)
        join_msg = Global.new_users[chat_id][user_id]["join_msg"]
        if join_msg is not None:
            tlg_delete_msg(bot, chat_id, join_msg)
        for msg in Global.new_users[chat_id][user_id]["msg_to_rm"]:
            tlg_delete_msg(bot, chat_id, msg)
        Global.new_users[chat_id][user_id]["msg_to_rm"].clear()
        for msg in Global.new_users[chat_id][user_id]["msg_to_rm_on_kick"]:
            tlg_delete_msg(bot, chat_id, msg)
        Global.new_users[chat_id][user_id]["msg_to_rm_on_kick"].clear()
        if restriction != "kick":
            del Global.new_users[chat_id][user_id]
    except KeyError:
        LOGGER.warning(
                "[%s] %s (%d) not in new_users list (already solve captcha)",
                chat_id, user_name, user_id)

def captcha_timeout(bot):
    '''
    Check if the time for ban new users that has not completed the
    captcha has arrived.
    '''
    while not Global.force_exit:
        # Release CPU sleeping on each iteration
        sleep(0.01)
        # Get all id from users in captcha process (list shallow copy)
        users_id = []
        chats_id_list = list(Global.new_users.keys()).copy()
        for chat_id in chats_id_list:
            users_id_list = list(Global.new_users[chat_id].keys()).copy()
            for user_id in users_id_list:
                if user_id not in users_id:
                    users_id.append(user_id)
        # For each user id check for time to kick in each chat
        i = 0
        for user_id in users_id:
            for chat_id in chats_id_list:
                # Sleep each 1000 iterations
                i = i + 1
                if i > 1000:
                    i = 0
                    sleep(0.01)
                # Check if script must exit for end coroutine
                if Global.force_exit:
                    return
                # Ignore if user is not in this chat
                if user_id not in Global.new_users[chat_id]:
                    continue
                try:
                    user_join_data = \
                            Global.new_users[chat_id][user_id]["join_data"]
                    user_join_time = user_join_data["join_time"]
                    captcha_timeout = user_join_data["captcha_timeout"]
                    if user_join_data["kicked_ban"]:
                        # Remove from new users list the remaining
                        # kicked users that have not solve the captcha
                        # in 30 mins (user ban just happen if a user try
                        # to join the group and fail to solve the
                        # captcha 5 times in the past 30 mins)
                        if time() - user_join_time < captcha_timeout + 1800:
                            continue
                        LOGGER.info(
                                "Removing kicked user %s after 30 mins",
                                user_id)
                        del Global.new_users[chat_id][user_id]
                    else:
                        # If time for kick/ban has not arrived yet
                        if time() - user_join_time < captcha_timeout:
                            continue
                        user_name = user_join_data["user_name"]
                        LOGGER.info(
                                "[%s] Captcha reply timeout for user %s.",
                                chat_id, user_name)
                        captcha_fail_member(bot, chat_id, user_id)
                        sleep(0.01)
                except Exception:
                    LOGGER.error(format_exc())
                    LOGGER.error("Fail to kick/ban an user")
    LOGGER.info("Captcha timeout coroutine finished")

def get_ban(user_id):
    LOGGER.info(f"checking the spamwatch")
    if not SW_API:
        LOGGER.info(f"Add SW_API in config file")
        return {}

    path = f"https://api.spamwat.ch/banlist/{user_id}"
    headers = {"Authorization": f"Bearer {SW_API}"}
    try:
        resp = requests.get(path, headers=headers)
        resp = resp.json()
        if resp['code'] in {200, 201}:
            return resp

        if resp['code'] == 404:
            return {}

        if resp['code'] == 401:
            LOGGER.error("Make sure your Spamwatch API token is corret")
            return {}

        if resp['code'] == 403:
            LOGGER.error("Forbidden, your token permissions is not valid")
            return {}

        if resp['code'] == 429:
            LOGGER.error("There were problems with request... Too many.")
            return {}

        LOGGER.error(f"Unknown Spamwatch API error: Received {resp['code']}")
        return {}
    except Exception as error:
        return error

def cas_check(user_id):
    """Check on CAS"""
    LOGGER.info(f"Checking if {user_id} is banned in cas.chat")
    retry = 0
    while True:
        try:
            res = requests.get(f"https://api.cas.chat/check?user_id={user_id}")
            data = res.json()
            if data["ok"]:
                reason = f"https://cas.chat/query?u={user_id}"
                LOGGER.info(f"{user_id} is banned in cas.chat")
                return reason

            LOGGER.info(f"{user_id} is not banned in cas.chat")
            return None
        except (JSONDecodeError):
            if retry == 5:
                LOGGER.warning("Error parsing CAS response")
                return None

            retry += 1
            sleep(1)
            LOGGER.warning("Invalid data received from CAS server, retrying...")
        except Exception as e:
            if retry == 10:
                LOGGER.warning("Error connecting to CAS API")
                return None

            retry += 1
            sleep(0.5)
            LOGGER.warning(f"Retrying CAS check for {user_id}")

def check_new_members(update, user_id, should_message=True):
    """Shield checker action."""
    cas = cas_check(user_id)
    sw = get_ban(user_id)

    if not (cas or sw):
        return False

    update.effective_chat.kick_member(user_id)
    update.effective_message.reply_text("This is a bad person, they shouldn't be here!")

@run_async
def chat_member_status_change(bot: Bot, update: Update):
    '''
    Get Members chats status changes (user join/leave/added/removed
    to/from group/channel) event handler. Note: if Bot is not an Admin,
    "chat_member" update won't be received.
    '''
    # Get Chat data
    chat = update.effective_chat
    msg = update.effective_message  # type: Optional[Message]
    join_users = update.effective_message.new_chat_members
    chat_id = chat.id
    # Get User ID and Name
    for join_user in join_users:
        join_user_id = join_user.id
        join_user_username = join_user.username

        # first_name = join_user.first_name

        if join_user_username is not None:
            join_user_name = join_user_username
        else:
            join_user_name = join_user.full_name

        LOGGER.info(
            "[%s] New join detected: %s (%s)",
            chat_id, join_user_name, join_user_id)

        # Check if the user is an admin.
        if is_user_admin(chat, join_user_id):
            LOGGER.info("[%s] User is an admin.", join_user_name)
            LOGGER.info("Skipping the captcha process.")
            if join_user_id != bot.id:
                welcome_message(bot, chat_id, join_user_id)
            continue

        if join_user_id == bot.id:
            LOGGER.info("User is the bot.")
            continue

        if spam_shield_sql.does_chat_spamshield(chat_id):
            LOGGER.info("[%s] Spam Shield active on this %s.", str(chat_id), chat.title)
            LOGGER.info("[%s] Spam Shield checking %s.", str(chat_id), join_user_name)
            check_new_members(update, join_user_id)

        # Get and update chat data
        chat_title = chat.title
        if chat_title:
            save_config_property(chat_id, "Title", chat_title)

        # Add an unicode Left to Right Mark (LRM) to chat title (fix for
        # arabic, hebrew, etc.)
        chat_title = add_lrm(chat_title)
        chat_link = chat.username
        if chat_link:
            chat_link = f"@{chat_link}"
            save_config_property(chat_id, "Link", chat_link)

        # Check and remove previous join messages of that user (if any)
        if int(chat_id) in Global.new_users:
            if int(join_user_id) in Global.new_users[int(chat_id)]:
                if "msg_to_rm" in Global.new_users[int(chat_id)][int(join_user_id)]:
                    for msg in \
                            Global.new_users[int(chat_id)][int(join_user_id)]["msg_to_rm"]:
                        try:
                            bot.delete_message(chat_id, msg)
                        except Exception as error:
                            LOGGER.error("[%s] %s", str(chat_id), str(error))
                    Global.new_users[int(chat_id)][int(join_user_id)]["msg_to_rm"].clear()

        # Ignore if the captcha protection is not enable in this chat
        captcha_enable = get_chat_config(chat_id, "Enabled")
        if not captcha_enable:
            LOGGER.info("[%s] Captcha is not enabled in this chat", chat_id)
            rules = rules_sql.get_rules(chat_id)

            if not rules:
                welcome_message(bot, chat_id, join_user_id)
                continue

            send_problem = False
            sent_result: dict = {}
            sent_result["msg"] = None
            sent_result["error"] = ""
            text = "Hey {} Please read and accept the rules with MILC SECURITY BOT to Speak in the group".format(join_user_name)
            try:
                msg = bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                reply_markup=InlineKeyboardMarkup(
                                    [[InlineKeyboardButton(text="T&C!",
                                            url="t.me/{}?start=joinrules_{}_{}".format(
                                                bot.username, chat_id, join_user_id
                                            ))
                                    ]]))
                LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
                sent_result["msg"] = msg
            except TelegramError as error:
                sent_result["error"] = str(error)
                LOGGER.error("[%s] %s", str(chat_id), str(error))

            if sent_result["msg"] is None:
                send_problem = True

            if not send_problem:
                if sent_result["msg"] is not None:
                    tlg_autodelete_msg(sent_result["msg"], 300)

            join_data = {
                "user_name": join_user_name,
                "join_time": time(),
                "captcha_timeout": 300,
                "join_retries": 1,
                "kicked_ban": False
            }
            # Create dict keys for new user
            if chat_id not in Global.new_users:
                Global.new_users[chat_id] = {}
            if join_user_id not in Global.new_users[chat_id]:
                Global.new_users[chat_id][join_user_id] = {}
            if "join_data" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["join_data"] = {}
            if "join_msg" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["join_msg"] = None
            if "msg_to_rm" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["msg_to_rm"] = []
            if "msg_to_rm_on_kick" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["msg_to_rm_on_kick"] = []
            # Check if this user was before in the chat without solve the
            # captcha and restore previous join_retries
            if len(Global.new_users[chat_id][join_user_id]["join_data"]) != 0:
                user_join_data = \
                        Global.new_users[chat_id][join_user_id]["join_data"]
                join_data["join_retries"] = user_join_data["join_retries"]
            # Add new user join data and messages to be removed
            Global.new_users[chat_id][join_user_id]["join_data"] = join_data
            if update.message:
                Global.new_users[chat_id][join_user_id]["join_msg"] = \
                        update.message.message_id
            if sent_result["msg"]:
                Global.new_users[chat_id][join_user_id]["msg_to_rm"].append(
                        sent_result["msg"].message_id)

            bot.restrict_chat_member(chat_id, join_user_id, until_date=320, can_send_messages=False)
            continue
        # Determine configured language and captcha settings
        captcha_level = get_chat_config(chat_id, "Captcha_Difficulty_Level")
        captcha_mode = get_chat_config(chat_id, "Captcha_Chars_Mode")
        captcha_timeout = get_chat_config(chat_id, "Captcha_Time")
        if captcha_timeout < 60:
            timeout = captcha_timeout * 60
        else:
            timeout = captcha_timeout

        send_problem = False
        sent_result: dict = {}
        sent_result["msg"] = None
        sent_result["error"] = ""
        text = "Hey {} Please pass the captcha with MILC SECURITY BOT to Speak in the group".format(join_user_name)
        try:
            msg = bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton(text="Verify me!",
                                        url="t.me/{}?start=captcha_{}_{}".format(
                                            bot.username, chat_id, join_user_id
                                        ))
                                ]]))
            LOGGER.debug("[%s] TLG text msg %d sent", str(chat_id), msg.message_id)
            sent_result["msg"] = msg
        except TelegramError as error:
            sent_result["error"] = str(error)
            LOGGER.error("[%s] %s", str(chat_id), str(error))

        if sent_result["msg"] is None:
            send_problem = True

        if not send_problem:
            if sent_result["msg"] is not None:
                tlg_autodelete_msg(sent_result["msg"], timeout + 10)
            # Default user join data
            join_data = {
                "user_name": join_user_name,
                "join_time": time(),
                "captcha_timeout": captcha_timeout,
                "join_retries": 1,
                "kicked_ban": False
            }

            # Create dict keys for new user
            if chat_id not in Global.new_users:
                Global.new_users[chat_id] = {}
            if join_user_id not in Global.new_users[chat_id]:
                Global.new_users[chat_id][join_user_id] = {}
            if "join_data" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["join_data"] = {}
            if "join_msg" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["join_msg"] = None
            if "msg_to_rm" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["msg_to_rm"] = []
            if "msg_to_rm_on_kick" not in Global.new_users[chat_id][join_user_id]:
                Global.new_users[chat_id][join_user_id]["msg_to_rm_on_kick"] = []
            # Check if this user was before in the chat without solve the
            # captcha and restore previous join_retries
            if len(Global.new_users[chat_id][join_user_id]["join_data"]) != 0:
                user_join_data = \
                        Global.new_users[chat_id][join_user_id]["join_data"]
                join_data["join_retries"] = user_join_data["join_retries"]
            # Add new user join data and messages to be removed
            Global.new_users[chat_id][join_user_id]["join_data"] = join_data
            if update.message:
                Global.new_users[chat_id][join_user_id]["join_msg"] = \
                        update.message.message_id
            if sent_result["msg"]:
                Global.new_users[chat_id][join_user_id]["msg_to_rm"].append(
                        sent_result["msg"].message_id)

        bot.restrict_chat_member(chat_id, join_user_id, until_date=timeout, can_send_messages=False)

def start_captcha(join_user_id, chat, join_user_name):
    '''
    Get Members chats status changes (user join/leave/added/removed
    to/from group/channel) event handler. Note: if Bot is not an Admin,
    "chat_member" update won't be received.
    '''
    # Get Chat data
    chat_id = chat["id"]
    chat_link = chat["invite_link"]
    chat_title = chat["title"]

    captcha_level = get_chat_config(chat_id, "Captcha_Difficulty_Level")
    captcha_mode = get_chat_config(chat_id, "Captcha_Chars_Mode")
    captcha_timeout = get_chat_config(chat_id, "Captcha_Time")
    if captcha_timeout < 60:
        timeout_str = f"{captcha_timeout} sec"
    else:
        timeout_str = f'{int(captcha_timeout / 60)} min'
    send_problem = False
    captcha_num = ""
    if captcha_mode == "random":
        captcha_mode = choice(["nums", "math"])
    if captcha_mode == "button":
        # Send a button-only challenge
        challenge_text = "Hello {}, Please press the button below to verify that you are not a robot. If you don't do this in {}, you will be automatically kicked out of the {} group.".format(
            join_user_name, timeout_str, chat_title)
        # Prepare inline keyboard button to let user pass
        keyboard = [[
               InlineKeyboardButton(
                       "I'm not a Bot",
                       callback_data=f"captcha_button({int(join_user_id)},{chat_id})")
               ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        LOGGER.info(
            "[%s] Sending captcha message to %s: [button]",
            chat_id, join_user_name)
        # Initialize sent_result as a dictionary
        sent_result: dict = {}
        sent_result["msg"] = None
        sent_result["error"] = ""
        try:
            msg = dispatcher.bot.send_message(chat_id=join_user_id,
                                    text=challenge_text,
                                    parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=reply_markup)
            LOGGER.debug("[%s] TLG text msg %d sent", str(join_user_id), msg.message_id)
            sent_result["msg"] = msg
        except TelegramError as error:
            sent_result["error"] = str(error)
            LOGGER.error("[%s] %s", str(chat_id), str(error))

        if sent_result["msg"] is None:
            send_problem = True
    else:
        captcha = create_image_captcha(
            chat_id, join_user_id, captcha_level, captcha_mode)
        if captcha_mode == "math":
            captcha_num = captcha["equation_result"]
            LOGGER.info(
                "[%s] Sending captcha message to %s: %s=%s...",
                chat_id, join_user_name, captcha["equation_str"],
                captcha["equation_result"])
            # Note: Img caption must be <= 1024 chars
            img_caption = "Hello {}, welcome to {}. Please write a message with the result of this math equation to verify that you are a human. If you don't solve this captcha in {}, you will be automatically kicked out of the group.".format(
                join_user_name, chat_title, timeout_str)
        else:
            captcha_num = captcha["characters"]
            LOGGER.info(
                "[%s] Sending captcha message to %s: %s...",
                chat_id, join_user_name, captcha_num)
            # Note: Img caption must be <= 1024 chars
            img_caption = "Hello {}, Please write a message with the numbers and/or letters that appear in this image to verify that you are a human. If you don't solve this captcha in {}, you will be automatically kicked out of the {} group.".format(
                join_user_name, timeout_str, chat_title)
        # Prepare inline keyboard button to let user request another
        # captcha
        keyboard = [[
            InlineKeyboardButton(
                "Other Captcha",
                callback_data=f"captcha_image({int(join_user_id)},{chat_id})")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        # Send the image
        sent_result: dict = {}
        sent_result["msg"] = None
        sent_result["error"] = ""
        try:
            with open(captcha["image"], "rb") as file_image:
                msg = dispatcher.bot.send_photo(
                    join_user_id, photo=file_image, caption=img_caption,
                    reply_markup=reply_markup)
            LOGGER.debug(
                "[%s] TLG image msg %d sent",
                str(join_user_id), msg.message_id)
            sent_result["msg"] = msg
        except Exception as error:
            sent_result["error"] = str(error)
            LOGGER.error(format_exc())
            LOGGER.error("[%s] %s", str(join_user_id), str(error))
            send_problem = True

        if sent_result["msg"] is None:
            send_problem = True
        # Remove sent captcha image file from file system
        if path.exists(captcha["image"]):
            remove(captcha["image"])
    if not send_problem:
        # Add sent captcha message to auto-delete list
        if sent_result["msg"] is not None:
            tlg_autodelete_msg(
                sent_result["msg"], captcha_timeout + 10)
        if "msg_to_rm_pm" not in Global.new_users[chat_id][int(join_user_id)]:
            Global.new_users[chat_id][int(join_user_id)]["msg_to_rm_pm"] = []
        Global.new_users[chat_id][int(join_user_id)]["join_data"]["captcha_num"] = captcha_num
        Global.new_users[chat_id][int(join_user_id)]["join_data"]["captcha_mode"] = captcha_mode
        if sent_result["msg"]:
            Global.new_users[chat_id][int(join_user_id)]["msg_to_rm_pm"].append(
                sent_result["msg"].message_id)
        # Restrict user to deny send any kind of message until captcha
        # is solve. Allow send text messages for image based captchas
        # that requires it
        # bot.restrict_chat_member(chat_id, join_user_id, until_date=timeout_str, can_send_messages=False)
        LOGGER.info("[%s] Captcha send process completed.", chat_id)

@run_async
def text_msg_rx(bot: Bot, update: Update):
    '''
    Text messages reception handler.
    '''
    # Get message data
    pm_chat = None
    chat_id = None
    update_msg = None
    update_msg = tlg_get_msg(update)
    if update_msg is not None:
        pm_chat = getattr(update_msg, "chat", None)
    if (update_msg is None) or (pm_chat is None):
        LOGGER.info("Warning: Received an unexpected update.")
        LOGGER.info(update)
        return

    # Ignore if message is not from a private chat
    if pm_chat.type != "private":
        return

    user_id = update_msg.from_user.id
    msg_id = update_msg.message_id

    for global_chat_id in Global.new_users:
        if user_id not in Global.new_users[global_chat_id]:
            continue
        else:
            chat_id = global_chat_id
            break

    if not chat_id:
        LOGGER.error("users captcha process not found")
        return

    # If message doesn't has text, check for caption fields (for no text
    # msgs and forward ones)
    msg_text = getattr(update_msg, "text", None)

    chat = bot.get_chat(chat_id)

    # Ignore if captcha protection is not enable in this chat
    captcha_enable = get_chat_config(chat_id, "Enabled")
    if not captcha_enable:
        return

    captcha_mode = \
        Global.new_users[chat_id][user_id]["join_data"]["captcha_mode"]

    # Get and update chat data
    chat_title = chat.title
    if chat_title:
        save_config_property(chat_id, "Title", chat_title)
    chat_link = chat.username
    if chat_link:
        chat_link = f"@{chat_link}"
        save_config_property(chat_id, "Link", chat_link)
    user_name = update_msg.from_user.full_name
    # If has an alias, just use the alias
    if update_msg.from_user.username is not None:
        user_name = f"@{update_msg.from_user.username}"
    # Set default text message if not received
    if msg_text is None:
        msg_text = "[Not a text message]"
    # End here if no image captcha mode
    if captcha_mode not in {"nums", "hex", "ascii", "math"}:
        return
    LOGGER.info(
            "[%s] Received captcha reply from %s: %s",
            chat_id, user_name, msg_text)
    # Check if the expected captcha solve number is in the message
    solve_num = Global.new_users[chat_id][user_id]["join_data"]["captcha_num"]
    if is_captcha_num_solve(captcha_mode, msg_text, solve_num):
        LOGGER.info("[%s] Captcha solved by %s", chat_id, user_name)

        # # Remove previous join messages in group
        # for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm"]:
        #     delete_result: dict = {}
        #     delete_result["error"] = ""
        #     try:
        #         bot.delete_message(chat_id, msg)
        #     except Exception as error:
        #         delete_result["error"] = str(error)
        #         LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])
        #
        # Remove captcha messages in PM
        for msg in Global.new_users[int(chat_id)][int(user_id)]["msg_to_rm_pm"]:
            delete_result: dict = {}
            delete_result["error"] = ""
            try:
                bot.delete_message(user_id, msg)
            except Exception as error:
                delete_result["error"] = str(error)
                LOGGER.error("[%s] %s", str(chat_id), delete_result["error"])

        # Global.new_users[chat_id][user_id]["msg_to_rm"].clear()
        # Global.new_users[chat_id][user_id]["msg_to_rm_on_kick"].clear()

        # Remove user captcha numbers message
        bot.delete_message(user_id, msg_id)
        join_send_rules(bot, chat_id, user_id, user_name)
    # The provided message doesn't has the valid captcha number
    else:
        # Check if the message is for a math equation captcha
        if captcha_mode == "math":
            clueless_user = False
            # Check if message is just 4 numbers
            if is_int(msg_text) and (len(msg_text) == 4):
                clueless_user = True
            # Check if message is "NN+NN" or "NN-NN"
            elif ((len(msg_text) == 5) and (is_int(msg_text[:2])) and
                    (is_int(msg_text[3:])) and (msg_text[2] in ["+", "-"])):
                clueless_user = True
            # Tell the user that is wrong
            if clueless_user:
                tlg_autodelete_msg(update_msg, 3)
                sent_msg_id = tlg_send_autodelete_msg(
                        bot, user_id, "That is not the correct number. Check closely, you need to solve the math equation...",
                        30)
                Global.new_users[chat_id][user_id]["msg_to_rm_pm"].append(
                        sent_msg_id)
                Global.new_users[chat_id][user_id]["msg_to_rm_pm"].append(msg_id)
        # If "nums", "hex" or "ascii" captcha
        else:
            # Check if the message has 4 chars
            if len(msg_text) == 4:
                tlg_autodelete_msg(update_msg, 3)
                sent_msg_id = tlg_send_autodelete_msg(
                        bot, user_id, "That is not the correct code. Try again...",
                        30)
                Global.new_users[chat_id][user_id]["msg_to_rm_pm"].append(
                        sent_msg_id)
                Global.new_users[chat_id][user_id]["msg_to_rm_pm"].append(msg_id)
            # Check if the message was just a 4 numbers msg
            elif is_int(msg_text):
                tlg_autodelete_msg(update_msg, 3)
                sent_msg_id = tlg_send_autodelete_msg(
                        bot, user_id, "That is not the correct number. Check closely, the captcha has 4 numbers...",
                        30)
                Global.new_users[chat_id][user_id]["msg_to_rm_pm"].append(
                        sent_msg_id)
                Global.new_users[chat_id][user_id]["msg_to_rm_pm"].append(msg_id)
    LOGGER.info("[%s] Captcha reply process completed.", chat_id)


__help__ = """
 Some chats get a lot of users joining just to spam. This could be because
 thry're trolls, or part of a spam network.
 To slow them down, you could try enabling CAPTCHAs. New users joining your chat will be required to complete a test to confirm that they're real people.

  *Admin only:*
- /captchadifficulty <X>: the difficulty level of captch from 1-5
- /captchamode <button/math/nums/hex/ascii/random>: Choose which CAPTCHA type to use for your chat.
- /captchatime <X s/X m>: Unmute new users after X time. If a user hasn't solved the CAPTCHA yet, they get automatically unmuted after this period.
- /captchadisable: Disable captcha in a particular group chat.
- /captchaenable: Enable Captcha in a particular group chat.
- /captchacfg: Display the Captcha configuration for a particular group chat

Examples:
- Sets the CAPTCHAs difficulty level to 3
-> /captchadifficulty 3

- Change the CAPTCHA mode to button.
-> /captchamode button

- Disable captcha time; users will stay muted until they solve the captcha.
-> /captchatime 10 min

- Disable captcha.
-> /captchadisable

- Enable captcha.
-> /captchaenable

- Display configuration.
-> /captchacfg
"""

__mod_name__ = "CAPTCHA"

CAPTCHA = CommandHandler("captcha", cmd_captcha, filters=CustomFilters.sudo_filter)
CAPTCHADIFFICULTY = CommandHandler("captchadifficulty", cmd_difficulty, pass_args=True, filters=Filters.group)
CAPTCHAMODE = CommandHandler("captchamode", cmd_captcha_mode, pass_args=True, filters=Filters.group)
CAPTCHATIME = CommandHandler("captchatime", cmd_time, pass_args=True, filters=Filters.group)
CAPTCHAENABLE = CommandHandler("captchaenable", cmd_enable, filters=Filters.group)
CAPTCHADISABLE = CommandHandler("captchadisable", cmd_disable, filters=Filters.group)
CAPTCHACFG = CommandHandler("captchacfg", cmd_checkcfg, filters=Filters.group)
NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members, chat_member_status_change)
BUTTON_PRESSED = CallbackQueryHandler(button_press_rx, pattern=r"captcha_")
BUTTON_RULES_PRESSED = CallbackQueryHandler(button, pattern=r"rules_")


dispatcher.add_handler(NEW_MEM_HANDLER, 1)
dispatcher.add_handler(MessageHandler(Filters.text & Filters.private, text_msg_rx), 2)
dispatcher.add_handler(BUTTON_PRESSED)
dispatcher.add_handler(BUTTON_RULES_PRESSED)
dispatcher.add_handler(CAPTCHAENABLE)
dispatcher.add_handler(CAPTCHADISABLE)
dispatcher.add_handler(CAPTCHA)
dispatcher.add_handler(CAPTCHADIFFICULTY)
dispatcher.add_handler(CAPTCHAMODE)
dispatcher.add_handler(CAPTCHATIME)
dispatcher.add_handler(CAPTCHACFG)

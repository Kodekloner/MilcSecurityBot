import threading

from sqlalchemy import func, distinct, Column, String, UnicodeText, Integer, Boolean

from tg_bot.modules.helper_funcs.msg_types import Types

from tg_bot.modules.sql import SESSION, BASE

DEFAULT_HIDE_MSG = "if you need any kind of help write '{help}'"

class HideWords(BASE):
    __tablename__ = "hide"
    chat_id = Column(String(14), primary_key=True)
    trigger = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, chat_id, trigger):
        self.chat_id = str(chat_id)  # ensure string
        self.trigger = trigger

    def __repr__(self):
        return "<Hide words '%s' for %s>" % (self.trigger, self.chat_id)

    def __eq__(self, other):
        return bool(isinstance(other, HideWords)
                    and self.chat_id == other.chat_id
                    and self.trigger == other.trigger)


class HelpMessage(BASE):
    __tablename__ = "help_message"
    chat_id = Column(String(14), primary_key=True)
    setting = Column(Boolean, default=False, nullable=False)
    help_msg = Column(UnicodeText, default=DEFAULT_HIDE_MSG)
    help_msg_type = Column(Integer, default=Types.TEXT.value)
    time_interval = Column(Integer, default=60)

    def __init__(self, chat_id):
        self.chat_id = str(chat_id)  # ensure string

HideWords.__table__.create(checkfirst=True)
HelpMessage.__table__.create(checkfirst=True)

HIDEWORD_INSERTION_LOCK = threading.RLock()
HELPMESSAGE_INSERTION_LOCK = threading.RLock()

CHAT_HIDE_WORDS = {}


def add_to_hidewords(chat_id, trigger):
    with HIDEWORD_INSERTION_LOCK:
        hidewords_filt = HideWords(str(chat_id), trigger)

        SESSION.merge(hidewords_filt)  # merge to avoid duplicate key issues
        SESSION.commit()
        CHAT_HIDE_WORDS.setdefault(str(chat_id), set()).add(trigger)


def rm_from_hidewords(chat_id, trigger):
    with HIDEWORD_INSERTION_LOCK:
        hidewords_filt = SESSION.query(HideWords).get((str(chat_id), trigger))
        if hidewords_filt:
            if trigger in CHAT_HIDE_WORDS.get(str(chat_id), set()):  # sanity check
                CHAT_HIDE_WORDS.get(str(chat_id), set()).remove(trigger)

            SESSION.delete(hidewords_filt)
            SESSION.commit()
            return True

        SESSION.close()
        return False


def get_chat_hidewords(chat_id):
    return CHAT_HIDE_WORDS.get(str(chat_id), set())


def num_hidewords_filters():
    try:
        return SESSION.query(HideWords).count()
    finally:
        SESSION.close()


def num_hidewords_chat_filters(chat_id):
    try:
        return SESSION.query(HideWords.chat_id).filter(HideWords.chat_id == str(chat_id)).count()
    finally:
        SESSION.close()


def num_hidewords_filter_chats():
    try:
        return SESSION.query(func.count(distinct(HideWords.chat_id))).scalar()
    finally:
        SESSION.close()


def set_help_msg(chat_id, help_msg, help_msg_type):
    # if buttons is None:
    #     buttons = []

    with HELPMESSAGE_INSERTION_LOCK:
        help_msg_settings = SESSION.query(HelpMessage).get(str(chat_id))
        if not help_msg_settings:
            help_msg_settings = HelpMessage(str(chat_id))

        if help_msg:
            help_msg_settings.help_msg = help_msg
            help_msg_settings.help_msg_type = help_msg_type.value

        else:
            help_msg_settings.help_msg = DEFAULT_GOODBYE
            help_msg_settings.help_msg_type = Types.TEXT.value

        SESSION.add(help_msg_settings)

        # with WELC_BTN_LOCK:
        #     prev_buttons = SESSION.query(WelcomeButtons).filter(WelcomeButtons.chat_id == str(chat_id)).all()
        #     for btn in prev_buttons:
        #         SESSION.delete(btn)
        #
        #     for b_name, url, same_line in buttons:
        #         button = WelcomeButtons(chat_id, b_name, url, same_line)
        #         SESSION.add(button)

        SESSION.commit()


def set_time_interval(chat_id, time_interval):
    # if buttons is None:
    #     buttons = []

    with HELPMESSAGE_INSERTION_LOCK:
        help_msg_settings = SESSION.query(HelpMessage).get(str(chat_id))
        if not help_msg_settings:
            help_msg_settings = HelpMessage(str(chat_id))

        if time_interval:
            help_msg_settings.time_interval = time_interval

        else:
            help_msg_settings.time_interval = 60

        SESSION.add(help_msg_settings)

        # with WELC_BTN_LOCK:
        #     prev_buttons = SESSION.query(WelcomeButtons).filter(WelcomeButtons.chat_id == str(chat_id)).all()
        #     for btn in prev_buttons:
        #         SESSION.delete(btn)
        #
        #     for b_name, url, same_line in buttons:
        #         button = WelcomeButtons(chat_id, b_name, url, same_line)
        #         SESSION.add(button)

        SESSION.commit()


def enable_help_msg(chat_id):
    with HELPMESSAGE_INSERTION_LOCK:
        chat = SESSION.query(HelpMessage).get(str(chat_id))
        if not chat:
            chat = HelpMessage(chat_id)

        chat.setting = True
        SESSION.add(chat)
        SESSION.commit()


def disable_help_msg(chat_id):
    with HELPMESSAGE_INSERTION_LOCK:
        chat = SESSION.query(HelpMessage).get(str(chat_id))
        if not chat:
            chat = HelpMessage(chat_id)

        chat.setting = False
        SESSION.add(chat)
        SESSION.commit()


def get_help_msg(chat_id):
    help_msg = SESSION.query(HelpMessage).get(str(chat_id))
    SESSION.close()
    if help_msg:
        return help_msg.help_msg, help_msg.help_msg_type, help_msg.time_interval, help_msg.setting
    else:
        # Welcome by default.
        return DEFAULT_HIDE_MSG, Types.TEXT, 60, False


def __load_chat_hidewords():
    global CHAT_HIDE_WORDS
    try:
        chats = SESSION.query(HideWords.chat_id).distinct().all()
        for (chat_id,) in chats:  # remove tuple by ( ,)
            CHAT_HIDE_WORDS[chat_id] = []

        all_filters = SESSION.query(HideWords).all()
        for x in all_filters:
            CHAT_HIDE_WORDS[x.chat_id] += [x.trigger]

        CHAT_HIDE_WORDS = {x: set(y) for x, y in CHAT_HIDE_WORDS.items()}

    finally:
        SESSION.close()


def migrate_chat(old_chat_id, new_chat_id):
    with HIDEWORD_INSERTION_LOCK:
        chat_filters = SESSION.query(HideWords).filter(HideWords.chat_id == str(old_chat_id)).all()
        for filt in chat_filters:
            filt.chat_id = str(new_chat_id)
        SESSION.commit()


__load_chat_hidewords()

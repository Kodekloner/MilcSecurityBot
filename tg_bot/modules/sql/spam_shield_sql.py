import threading

from sqlalchemy import Column, UnicodeText, Integer, String, Boolean, BigInteger

from tg_bot.modules.sql import BASE, SESSION


class SpamSettings(BASE):
    __tablename__ = "spam_settings"
    chat_id = Column(String(14), primary_key=True)
    setting = Column(Boolean, default=True, nullable=False)

    def __init__(self, chat_id, enabled):
        self.chat_id = str(chat_id)
        self.setting = enabled

    def __repr__(self):
        return "<Gban setting {} ({})>".format(self.chat_id, self.setting)


SpamSettings.__table__.create(checkfirst=True)

SPAM_SETTING_LOCK = threading.RLock()
SPAMSHIELDSTAT_LIST = set()

def disable_spam_shield(chat_id):
    with SPAM_SETTING_LOCK:
        chat = SESSION.query(SpamSettings).get(str(chat_id))
        if not chat:
            chat = SpamSettings(chat_id, False)

        chat.setting = False
        SESSION.add(chat)
        SESSION.commit()
        SPAMSHIELDSTAT_LIST.add(str(chat_id))

def enable_spam_shield(chat_id):
    with SPAM_SETTING_LOCK:
        chat = SESSION.query(SpamSettings).get(str(chat_id))
        if not chat:
            chat = SpamSettings(chat_id, True)

        chat.setting = True
        SESSION.add(chat)
        SESSION.commit()
        if str(chat_id) in SPAMSHIELDSTAT_LIST:
            SPAMSHIELDSTAT_LIST.remove(str(chat_id))

def does_chat_spamshield(chat_id):
    return str(chat_id) not in SPAMSHIELDSTAT_LIST

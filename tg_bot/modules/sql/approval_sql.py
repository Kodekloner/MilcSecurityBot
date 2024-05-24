import threading

from sqlalchemy import Column, UnicodeText, Integer, String, Boolean, BigInteger

from tg_bot.modules.sql import BASE, SESSION


class ApprovedUsers(BASE):
    __tablename__ = "approved_users"
    user_id = Column(BigInteger, primary_key=True)
    name = Column(UnicodeText, nullable=False)
    # reason = Column(UnicodeText)

    def __init__(self, user_id, name):
        self.user_id = user_id
        self.name = name
        # self.reason = reason

    def __repr__(self):
        return "<Approved Users {} ({})>".format(self.name, self.user_id)

    def to_dict(self):
        return {"user_id": self.user_id,
                "name": self.name}


# class GbanSettings(BASE):
#     __tablename__ = "gban_settings"
#     chat_id = Column(String(14), primary_key=True)
#     setting = Column(Boolean, default=True, nullable=False)
#
#     def __init__(self, chat_id, enabled):
#         self.chat_id = str(chat_id)
#         self.setting = enabled
#
#     def __repr__(self):
#         return "<Gban setting {} ({})>".format(self.chat_id, self.setting)


ApprovedUsers.__table__.create(checkfirst=True)
# GbanSettings.__table__.create(checkfirst=True)

APPROVED_USERS_LOCK = threading.RLock()
# GBAN_SETTING_LOCK = threading.RLock()
APPROVED_LIST = set()
# GBANSTAT_LIST = set()


def approve_user(user_id, name):
    with APPROVED_USERS_LOCK:
        user = SESSION.query(ApprovedUsers).get(user_id)
        if not user:
            user = ApprovedUsers(user_id, name)
        else:
            user.name = name

        SESSION.merge(user)
        SESSION.commit()
        __load_approved_userid_list()


def unapprove_user(user_id):
    with APPROVED_USERS_LOCK:
        user = SESSION.query(ApprovedUsers).get(user_id)
        if user:
            SESSION.delete(user)

        SESSION.commit()
        __load_approved_userid_list()


def is_user_approved(user_id):
    return user_id in APPROVED_LIST


def get_approve_user(user_id):
    try:
        return SESSION.query(ApprovedUsers).get(user_id)
    finally:
        SESSION.close()


def get_approved_list():
    try:
        return [x.to_dict() for x in SESSION.query(ApprovedUsers).all()]
    finally:
        SESSION.close()


# def enable_gbans(chat_id):
#     with GBAN_SETTING_LOCK:
#         chat = SESSION.query(GbanSettings).get(str(chat_id))
#         if not chat:
#             chat = GbanSettings(chat_id, True)
#
#         chat.setting = True
#         SESSION.add(chat)
#         SESSION.commit()
#         if str(chat_id) in GBANSTAT_LIST:
#             GBANSTAT_LIST.remove(str(chat_id))


# def disable_gbans(chat_id):
#     with GBAN_SETTING_LOCK:
#         chat = SESSION.query(GbanSettings).get(str(chat_id))
#         if not chat:
#             chat = GbanSettings(chat_id, False)
#
#         chat.setting = False
#         SESSION.add(chat)
#         SESSION.commit()
#         GBANSTAT_LIST.add(str(chat_id))


# def does_chat_gban(chat_id):
#     return str(chat_id) not in GBANSTAT_LIST


def num_approved_users():
    return len(APPROVED_LIST)


def __load_approved_userid_list():
    global APPROVED_LIST
    try:
        APPROVED_LIST = {x.user_id for x in SESSION.query(ApprovedUsers).all()}
    finally:
        SESSION.close()


# def __load_gban_stat_list():
#     global GBANSTAT_LIST
#     try:
#         GBANSTAT_LIST = {x.chat_id for x in SESSION.query(GbanSettings).all() if not x.setting}
#     finally:
#         SESSION.close()


# def migrate_chat(old_chat_id, new_chat_id):
#     with GBAN_SETTING_LOCK:
#         chat = SESSION.query(GbanSettings).get(str(old_chat_id))
#         if chat:
#             chat.chat_id = new_chat_id
#             SESSION.add(chat)
#
#         SESSION.commit()


# Create in memory userid to avoid disk access
__load_approved_userid_list()
# __load_gban_stat_list()


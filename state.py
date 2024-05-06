from telebot.handler_backends import StatesGroup, State


class UserState(StatesGroup):
    new_task_title = State()
    new_task_due_date = State()
    tasks_make_done = State()
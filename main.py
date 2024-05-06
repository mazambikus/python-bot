import datetime
from typing import List

from peewee import IntegrityError
from telebot import StateMemoryStorage, TeleBot
from telebot.custom_filters import StateFilter
from telebot.handler_backends import State, StatesGroup
from telebot.types import BotCommand, Message

from config import BOT_TOKEN, DATE_FORMAT, DEFAULT_COMMANDS
from models import Task, User, create_models

state_storage = StateMemoryStorage()

bot = TeleBot(BOT_TOKEN, state_storage=state_storage)


class UserState(StatesGroup):
    new_task_title = State()
    new_task_due_date = State()
    tasks_make_done = State()


@bot.message_handler(commands=["start"])
def handle_start(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name

    try:
        User.create(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        bot.reply_to(message, "Добро пожаловать в менеджер задач!")
    except IntegrityError:
        bot.reply_to(message, f"Рад вас снова видеть, {first_name}!")


@bot.message_handler(state="*", commands=["newtask"])
def handle_new_task(message: Message) -> None:
    user_id = message.from_user.id
    if User.get_or_none(User.user_id == user_id) is None:
        bot.reply_to(message, "Вы не зарегистрированы. Напишите /start")
        return

    bot.send_message(user_id, "Введите название задачи")
    bot.set_state(message.from_user.id, UserState.new_task_title)
    with bot.retrieve_data(message.from_user.id) as data:
        data["new_task"] = {"user_id": user_id}


@bot.message_handler(state="*", commands=["tasks"])
def handle_tasks(message: Message) -> None:
    user_id = message.from_user.id
    user = User.get_or_none(User.user_id == user_id)
    if user is None:
        bot.reply_to(message, "Вы не зарегистрированы. Напишите /start")
        return

    tasks: List[Task] = user.tasks.order_by(-Task.due_date, -Task.task_id).limit(10)

    result = []
    result.extend(map(str, reversed(tasks)))

    if not result:
        bot.send_message(message.from_user.id, "У вас еще нет задач")
        return

    result.append("\nВведите номер задачи, чтобы изменить ее статус.")
    bot.send_message(message.from_user.id, "\n".join(result))
    bot.set_state(message.from_user.id, UserState.tasks_make_done)


@bot.message_handler(state="*", commands=["today"])
def handle_today(message: Message) -> None:
    user_id = message.from_user.id
    user = User.get_or_none(User.user_id == user_id)
    if user is None:
        bot.reply_to(message, "Вы не зарегистрированы. Напишите /start")
        return

    tasks: List[Task] = user.tasks.where(Task.due_date == datetime.date.today())

    result = []
    result.extend(map(str, tasks))

    if not result:
        bot.send_message(message.from_user.id, "У вас еще нет задач")
        return

    result.append("\nВведите номер задачи, чтобы изменить ее статус.")
    bot.send_message(message.from_user.id, "\n".join(result))
    bot.set_state(message.from_user.id, UserState.tasks_make_done)


@bot.message_handler(state=UserState.new_task_title)
def process_task_title(message: Message) -> None:
    with bot.retrieve_data(message.from_user.id) as data:
        data["new_task"]["title"] = message.text
    bot.send_message(message.from_user.id, "Введите дату (ДД.ММ.ГГГГ):")
    bot.set_state(message.from_user.id, UserState.new_task_due_date)


@bot.message_handler(state=UserState.new_task_due_date)
def process_task_due_date(message: Message) -> None:
    due_date_string = message.text
    try:
        due_date = datetime.datetime.strptime(due_date_string, DATE_FORMAT)
    except ValueError:
        bot.send_message(message.from_user.id, "Введите дату (ДД.ММ.ГГГГ):")
        return

    with bot.retrieve_data(message.from_user.id) as data:
        data["new_task"]["due_date"] = due_date

    new_task = Task(**data["new_task"])
    new_task.save()
    bot.send_message(message.from_user.id, f"Задача добавлена:\n{new_task}")
    bot.delete_state(message.from_user.id)


@bot.message_handler(state=UserState.tasks_make_done)
def process_task_done(message: Message) -> None:
    task_id = int(message.text)
    task = Task.get_or_none(Task.task_id == task_id)
    if task is None:
        bot.send_message(message.from_user.id, "Задачи с таким ID не существует.")
        return

    if task.user_id != message.from_user.id:
        bot.send_message(
            message.from_user.id, "Вы не являетесь владельцем данной задачи."
        )
        return

    task.is_done = not task.is_done
    task.save()
    bot.send_message(message.from_user.id, task)


if __name__ == "__main__":
    create_models()
    bot.add_custom_filter(StateFilter(bot))
    bot.set_my_commands([BotCommand(*cmd) for cmd in DEFAULT_COMMANDS])
    bot.polling()

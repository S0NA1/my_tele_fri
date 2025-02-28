import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, CallbackQuery
from config import BOT_TOKEN
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3
import kbs
import logging
from fnmatch import *
import re
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

con = sqlite3.connect("product_db.db")
cur = con.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS Users (
id INTEGER NOT NULL,
product TEXT,
data TEXT)
''')
con.commit()
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO, filename="loggs.log", filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
scheduler_started = False


@dp.message(Command("help"))
async def help_me(messege: Message):
    await messege.answer('''Чтобы открыть главную клавиатуру, выберете в меню команду 
➡️Открыть меню выбора

Чтобы скрыть клавиатуру, выберите команду 
➡️Закрыть меню выбора

Чтобы удалить свой профиль и данные навсегда, вы модете воспользоваться двумя способами:
➡️команда Удалить свой профиль в меню выбора
➡️кнопка Удалить профиль в главном меню
‼️Данные не сохранятся‼️''', reply_markup=kbs.start_key)


async def send_message(bot: Bot, user_id: int, chat_id: int):
    try:
        chek = cur.execute("SELECT product, data FROM Users WHERE id = ?", (user_id,)).fetchall()
        now_data = datetime.datetime.now().date()
        tre_days = []
        week_days = []
        drop_days = []

        for i in chek:
            obj_data = str(i[1]).split("-")
            first = datetime.date(int(obj_data[0]), int(obj_data[1]), int(obj_data[2]))
            how_days = int(str(first - now_data).split()[0])

            if how_days == 3:
                tre_days.append([i[0], i[1]])
            if how_days == 7:
                week_days.append([i[0], i[1]])
            if how_days < 0:
                drop_days.append([i[0], i[1]])

        mess = ''
        if tre_days:
            mess += f"Осталось три дня до окончания срока годности: \n {pping(tre_days)}\n\n"
        if week_days:
            mess += f'Осталась неделя до конца срока годности: \n {pping(week_days)}\n\n'
        if drop_days:
            mess += f"У Вас имеются просроченные продукты: \n {pping(drop_days)}\n"
        if not mess:
            mess += f"У Вас нет продуктов, у которых скоро закончится срок годности или просрочены"

        await bot.send_message(chat_id=chat_id, text=mess.strip())

    except Exception as e:
        logger.error(f"Ошибка в send_message для пользователя {user_id}: {e}")
        await bot.send_message(chat_id=chat_id, text="Произошла ошибка.")


@dp.message(Command("open_choice"))
async def open_menu(message: Message):
    await message.answer('''Меню выбора открылось

Чтобы закрыть меню выбота, выберите в меню команд
➡️Закрыть меню выбора''', reply_markup=kbs.start_key)


@dp.message(Command("close_choice"))
async def close_menu(message: Message):
    await message.answer('''Меню выбора закрылось

Чтобы открыть меню выбота, выберите в меню команд
➡Открыть меню выбора''', reply_markup=ReplyKeyboardRemove())


@dp.message(Command("start"))
async def start_menu(message: Message, bot: Bot = bot):
    global scheduler_started
    try:
        chek = cur.execute("SELECT * FROM Users WHERE id = ?", (message.from_user.id,)).fetchall()

        job_id = f"notify_{message.from_user.id}"
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                send_message,
                trigger="cron",
                hour=18,
                minute=39,
                start_date=datetime.datetime.now(),
                kwargs={
                    "bot": bot,
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                },
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Добавлена задача уведомления для пользователя {message.from_user.id}")

        if not scheduler_started:
            scheduler.start()
            scheduler_started = True
            logger.info("Планировщик запущен")

        if len(chek) == 0:
            await message.answer(f'''Добро пожаловать в бот-холодильник😊
    ‼️ВНИМАНИЕ‼️
    Если возникли какие-то вопросы, отправьте команду /help
    
    Удачного пользования🙂 ''',
                                 reply_markup=kbs.start_key)
        else:
            await message.answer(
                '''Вы повторно нажали на команду /start, ваша работа в боте не прервана. 
    Для удаления данных воспользуйтесь кнопкой "удалить профиль"''',
                reply_markup=kbs.start_key)
    except Exception as e:
        logger.error(f"Ошибка в start_menu для пользователя {message.from_user.id}: {e}")
        await message.answer("Произошла ошибка.")


@dp.message(Command("delete_profile"))
async def delete_datab(message: Message):
    await message.answer(f"Вы уверены, что хотите удалить все свои данные навсегда?😣",
                         reply_markup=kbs.paginator())


@dp.message(F.text.lower() == "удалить профиль")
async def delete_datab(message: Message):
    await message.answer(f"Вы уверены, что хотите удалить все свои данные навсегда?😣",
                         reply_markup=kbs.paginator())


@dp.callback_query(kbs.Pang.filter(F.action.in_(["del", "no_del"])))
async def yes_no_del(call: CallbackQuery, callback_data: kbs.Pang):
    chek = cur.execute("SELECT * FROM Users WHERE id = ?", (call.from_user.id,)).fetchall()
    now_id = call.from_user.id

    if callback_data.action == "no_del":
        await call.message.answer("Вы не удалили данные, продолжайте работу",
                                  reply_markup=kbs.start_key)

    elif callback_data.action == "del":
        if len(chek) == 0:
            await call.message.answer("У вас нет записанных продуктов, поэтому можете начинать работу сначала",
                                      reply_markup=kbs.write_th)
        else:
            cur.execute('DELETE FROM Users WHERE id = ?', (now_id,))
            con.commit()
            await call.message.answer(f'''Ваши данные удалены.

Чтобы возобновить работу бота, нажмите на команду
➡️/start''',
                                      reply_markup=kbs.start_new_profile)
    await call.answer()


def pping(spis):
    result = []
    for k, (prod, date) in enumerate(spis, start=1):
        result.append(f"{k}. {prod} {date}")
    return "\n".join(result)


@dp.message(F.text.lower() == "список моих продуктов")
async def chek_product(message: Message):
    now_product = cur.execute("SELECT product, data FROM Users WHERE id = ?", (message.from_user.id,)).fetchall()
    if len(now_product) == 0:
        await message.answer("Вы еще не записали в таблицу продукты, начните заполнение сейчас!⬇️",
                             reply_markup=kbs.write_th)
    else:
        await message.answer(f'''Ваши продукты:
{pping(now_product)}''',
                             reply_markup=kbs.start_key)


@dp.message(F.text.lower() == "посмотреть просроченное")
async def see_old(messege: Message):
    old_data = cur.execute("SELECT * FROM Users WHERE id = ?", (messege.from_user.id,)).fetchall()
    now_data = datetime.datetime.now().date()
    convert_result = []

    for i in old_data:
        try:
            if not re.match(r"\d{4}-\d{2}-\d{2}", str(i[2])):
                logging.warning(f"Некорректный формат даты: {i[2]}")
                continue

            obj_data = str(i[2]).split("-")
            first = datetime.date(int(obj_data[0]), int(obj_data[1]), int(obj_data[2]))

            delta = (first - now_data).days
            if delta <= 0:
                convert_result.append([i[1], i[2]])
        except (ValueError, IndexError) as e:
            logging.error(f"Ошибка при обработке даты: {e}")
            continue

    if len(convert_result) == 0:
        all_product = len(old_data)
        await messege.answer(f"У вас нет просроченных продуктов🌱 (всего продуктов: {all_product})",
                             reply_markup=kbs.start_key)
    else:
        await messege.answer(f'''Ваши просроченные продукты:
{pping(convert_result)}''',
                             reply_markup=kbs.olginator())


@dp.callback_query(kbs.Old.filter(F.action.in_(["out_del", "no_out"])))
async def old_thing(call: CallbackQuery, callback_data: kbs.Old):
    if callback_data.action == "out_del":
        old_data = cur.execute("SELECT * FROM Users WHERE id = ?", (call.from_user.id,)).fetchall()
        now_data = datetime.datetime.now().date()
        convert_result = []

        if len(old_data) != 0:
            for i in old_data:
                obj_data = str(i[2]).split("-")
                first = datetime.date(int(obj_data[0]), int(obj_data[1]), int(obj_data[2]))
                if int(str(first - now_data).split()[0]) <= 0:
                    convert_result.append([i[1], i[2]])

        for i in convert_result:
            cur.execute("DELETE FROM Users WHERE (product, data) = (?, ?)", (i[0], i[1]))
            con.commit()
        await call.message.answer("Все просроченное удалено✅",
                                  reply_markup=kbs.start_key)

    elif callback_data.action == "no_out":
        await call.message.answer("Вы не удалили просроченное, продолжайте работу",
                                  reply_markup=kbs.start_key)

    await call.answer()


@dp.message(F.text.lower() == "в главное меню")
async def beck_to_men(messege: Message):
    await messege.answer("Выберите действие⬇️",
                         reply_markup=kbs.start_key)


class Dele(StatesGroup):
    del_object = State()


@dp.message(F.text.lower() == "удалить продукт")
async def del_norm(message: Message, state: FSMContext):
    now_product = cur.execute("SELECT product, data FROM Users WHERE id = ?", (message.from_user.id,)).fetchall()
    if len(now_product) > 0:
        await state.set_state(Dele.del_object)
        await message.answer(f"Ваши продукты: \n{pping(now_product)}")
        await message.answer('''Отправьте номер продукта, чтобы удалить его📲''', reply_markup=kbs.otmenator())
    else:
        await message.answer("У вас нет записанных продуктов, начните заполнять таблицу⬇️",
                             reply_markup=kbs.write_th)


@dp.callback_query(kbs.Pang.filter(F.action.in_(["otm"])))
async def otm_or_not(call: CallbackQuery, callback_data: kbs.Pang, state: FSMContext):
    if callback_data.action == "otm":
        await call.message.answer("Вы отменили данное действие, продолжайте работу.",
                                  reply_markup=kbs.start_key)
        await state.clear()
    await call.answer()


@dp.message(Dele.del_object)
async def start_delete(message: Message, state: FSMContext):
    now_product = cur.execute("SELECT id, product, data FROM Users WHERE id = ?",
                              (message.from_user.id,)).fetchall()

    if message.text.lower() == "отмена":
        await message.answer("Удаление отменено.", reply_markup=kbs.start_key)
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите номер продукта (например, 1, 2, 3).", reply_markup=kbs.otmenator())
        return

    product_index = int(message.text) - 1
    if product_index < 0 or product_index >= len(now_product):
        await message.answer(f"Номер продукта должен быть от 1 до {len(now_product)}. Попробуйте снова.")
        return

    now_work = now_product[product_index]
    cur.execute("DELETE FROM Users WHERE (id, product, data) = (?, ?, ?)", (now_work[0], now_work[1], now_work[2]))
    con.commit()

    await message.answer('''Продукт удалён✅

    Если хотите удалить что-то ещё, снова нажмите на кнопку
    ➡ удалить продукт''',
                         reply_markup=kbs.start_key)

    await state.clear()


class Form(StatesGroup):
    obje = State()
    date = State()


@dp.message(F.text.lower() == "добавить продукт")
async def fill_db(message: Message, state: FSMContext):
    await state.set_state(Form.obje)
    await message.answer("Введите только название продукта⬇️", reply_markup=kbs.otmenator())


@dp.message(Form.obje)
async def name_prod(message: Message, state: FSMContext):
    await state.update_data(obje=message.text)
    await state.set_state(Form.date)
    await message.answer(f'''Введите конец срока годности в виде {datetime.date.today()}
(год, месяц, число)⬇️''', reply_markup=kbs.otmenator())


chis = "0123456789-"


def check_data(n):
    if fnmatch(str(n), "????-??-??"):
        for i in n:
            if i not in chis:
                return 0
        now = n.split("-")
        year = int(now[0])
        month = int(now[1])
        day = int(now[2])
        if month == 2:
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                max_day = 29
            else:
                max_day = 28
            if day > max_day:
                return 0
        if month > 12:
            return 0
        if day > 31:
            return 0
        return 1
    return 0


@dp.message(Form.date)
async def name_da(message: Message, state: FSMContext):
    if check_data(message.text):
        await state.update_data(date=message.text)
        all_data = await state.get_data()
        now = message.from_user.id

        if "obje" not in all_data or "date" not in all_data:
            await message.answer("Произошла ошибка.")
            return

        product_name = all_data["obje"]
        expiration_date = all_data["date"]

        try:
            cur.execute("INSERT INTO Users (id, product, data) VALUES (?, ?, ?)",
                        (now, product_name, expiration_date))
            con.commit()

        except Exception as e:
            logger.error(f"Ошибка при вставке в базу данных: {e}")
            await message.answer("Произошла ошибка.")
            return

        await state.clear()
        await message.answer("Супер, запись создана👍\nЧто дальше?🤔", reply_markup=kbs.start_key)
    else:
        await message.reply(f'''Вы ввели дату в неправильном формате.😢

‼️Попытайтесь еще раз в формате {datetime.date.today()}
(год, месяц, число)⬇️''', reply_markup=kbs.back_to_me)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

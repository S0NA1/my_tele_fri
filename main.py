import asyncio
from aiogram import Dispatcher
from aiogram import types
from aiogram import F
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.types import CallbackQuery
from config import BOT_TOKEN
from config import UNSPLASH_ACCESS_KEY
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import sqlite3
from aiogram.filters import StateFilter
import kbs
import logging
from fnmatch import *
import re
import requests
import warnings
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram_calendar import SimpleCalendarCallback
from aiogram_calendar import SimpleCalendar
from aiogram_calendar import get_user_locale
from datetime import datetime
from datetime import date


warnings.filterwarnings("ignore",
                        category=ResourceWarning)

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

logging.basicConfig(level=logging.INFO, 
                    filename="loggs.log", 
                    filemode="w",
                    format="%(asctime)s %(levelname)s %(message)s")

logger = logging.getLogger(__name__)


scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
scheduler_started = False


@dp.message(Command("help"))
async def help_me(message: Message):
    logger.info(f"Пользователю {message.from_user.id} нужна помощь")
    await message.answer('''Чтобы открыть главную клавиатуру, выберите в меню команду: 
⭕️ Открыть меню выбора       /open_choice

Чтобы скрыть клавиатуру, выберите команду:
⭕️ Закрыть меню выбора       /close_choice

Чтобы удалить свой профиль и данные навсегда, вы модете воспользоваться двумя способами:
➡️команда Удалить свой профиль в меню выбора        /delete_profile

➡️Нажать кнопку "удалить профиль". Будьте внимательны, Ваши ‼️Данные не сохранятся‼️

🦞Если вдруг у Вас НЕ РАБОТАЮТ УВЕДОМЛЕНИЯ по какой-то причине, возможно, бот был пережапущен и требует обновления. Просто отправьте команду /start ещё раз. Все данные останутся неизменными, уведомления заработают🐥''',
                         reply_markup=kbs.start_key)


async def send_message(bot: Bot, user_id: int, chat_id: int):
    logger.info(f"Начало выполнения send_message для user_id={user_id}, chat_id={chat_id}")
    try:
        chek = cur.execute("SELECT product, data FROM Users WHERE id = ?",
                           (user_id,)).fetchall()
        logger.info(f"Получено {len(chek)} записей из базы данных для user_id={user_id}")

        now_data = datetime.now().date()
        tre_days = []
        week_days = []
        drop_days = []

        for i in chek:
            logger.info(f"Обработка записи: product={i[0]}, data={i[1]}")
            try:
                obj_data = str(i[1]).split("-")
                first = date(int(obj_data[0]), int(obj_data[1]), int(obj_data[2]))
                how_days = (first - now_data).days

                if how_days == 3:
                    tre_days.append([i[0], i[1]])
                if how_days == 7:
                    week_days.append([i[0], i[1]])
                if how_days < 0:
                    drop_days.append([i[0], i[1]])
            except (ValueError, IndexError) as e:
                logger.error(f"Ошибка обработки даты для записи {i}: {e}")
                continue

        mess = ''
        if tre_days:
            mess += f"Осталось три дня до окончания срока годности: \n {pping(tre_days)}\n\n"

        if week_days:
            mess += f'Осталась неделя до конца срока годности: \n {pping(week_days)}\n\n'

        if drop_days:
            mess += f"У Вас имеются просроченные продукты: \n {pping(drop_days)}\n"

        if not mess:
            mess += f"У Вас нет продуктов, у которых скоро закончится срок годности или просрочены"

        logger.info(f"Формирование сообщения: {mess}")
        try:
            await bot.send_message(chat_id=chat_id,
                                   text=mess.strip())

            logger.info(f"Сообщение успешно отправлено в chat_id={chat_id}")

        except Exception as send_error:
            logger.error(f"Ошибка при отправке сообщения в chat_id={chat_id}: {send_error}")

    except Exception as e:
        logger.error(f"Общая ошибка в send_message для пользователя {user_id}: {e}")

        try:
            await bot.send_message(chat_id=chat_id, text="Произошла ошибка.")

        except Exception as send_error:
            logger.error(f"Ошибка при отправке сообщения об ошибке в chat_id={chat_id}: {send_error}")


@dp.message(Command("open_choice"))
async def open_menu(message: Message):
    logger.info(f"Пользователь {message.from_user.id} открыл меню выбора.")
    await message.answer('''Меню выбора открылось 🌺

Чтобы закрыть меню выбота, выберите в меню команд
➡️Закрыть меню выбора       /close_choice''',
                         reply_markup=kbs.start_key)


@dp.message(Command("close_choice"))
async def close_menu(message: Message):
    logger.info(f"Пользователь {message.from_user.id} закрыл меню выбора.")
    await message.answer('''Меню выбора закрылось 🌷

Чтобы открыть меню выбота, выберите в меню команд
➡️Открыть меню выбора       /open_choice''',
                         reply_markup=ReplyKeyboardRemove())


@dp.message(Command("start"))
async def start_menu(message: Message, bot: Bot = bot):
    global scheduler_started
    try:
        chek = cur.execute("SELECT * FROM Users WHERE id = ?",
                           (message.from_user.id,)).fetchall()

        job_id = f"notify_{message.from_user.id}"
        if not scheduler.get_job(job_id):
            scheduler.add_job(
                send_message,
                trigger="cron",
                hour=17,
                minute=45,
                start_date=datetime.now(),
                kwargs={
                    "bot": bot,
                    "user_id": message.from_user.id,
                    "chat_id": message.chat.id,
                },
                id=job_id,
                replace_existing=True
            )
            logger.info(f"Уведомления для пользователя {message.from_user.id} запущены")

        if not scheduler_started:
            scheduler.start()
            scheduler_started = True
            logger.info("Планировщик запущен")

        if len(chek) == 0:
            await message.answer(f'''Добро пожаловать в бот-холодильник😊
            
С этим телеграмм-ботом Вы можете не беспокоиться о сроке годности своих продуктов. Он всё сделает за вас️ ☀️

Уведомления об окончании сроков годности будут приходить за неделю, за три дня и в день окончания срока годности.

Для качественной работы бота Вам потребуется всего 5 минут времени. Необходимо выбрать нужную команду из мегю кнопок и следовать инструкции.
Для начала советую выбрать "Добавить продукт", чтобы разобраться в работе бота.

При вводе продуктов, на некоторые из них будет высвечиваться картинка. Если вы будете вводить название на английском, картинки будут точнее.😊

В любой момент Вы можете удалить свой профиль, но будьте внимательны, ❗️Ваши данные не сохранятся❗️, всё придётся заполнять снова 😫

Также у Вас есть возможность просмотреть свои просроченные продукты и удалить их.

‼️ВНИМАНИЕ‼

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
    logger.info(f"Пользователь хочет {message.from_user.id} удалить профиль.")
    await message.answer(f"Вы уверены, что хотите удалить все свои данные навсегда?😣",
                         reply_markup=kbs.yes_or_no())


@dp.message(F.text.lower() == "удалить профиль")
async def delete_datab(message: Message):
    logger.info(f"Пользователь {message.from_user.id} хочет удалить профиль.")
    await message.answer(f"Вы уверены, что хотите удалить все свои данные навсегда?😣",
                         reply_markup=kbs.yes_or_no())


@dp.callback_query(kbs.Pang.filter(F.action.in_(["del", "no_del"])))
async def yes_no_del(call: CallbackQuery, callback_data: kbs.Pang):
    chek = cur.execute("SELECT * FROM Users WHERE id = ?",
                       (call.from_user.id,)).fetchall()
    now_id = call.from_user.id

    if callback_data.action == "no_del":
        await call.message.answer("Вы не удалили данные, продолжайте работу",
                                  reply_markup=kbs.start_key)

    elif callback_data.action == "del":
        if len(chek) == 0:
            await call.message.answer("У вас нет записанных продуктов, поэтому можете начинать работу сначала",
                                      reply_markup=kbs.edit_th)
        else:
            cur.execute('DELETE FROM Users WHERE id = ?',
                        (now_id,))
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
    logger.info(f"Пользователь {message.from_user.id} хочет узнать список своих продуктов.")
    now_product = cur.execute("SELECT product, data FROM Users WHERE id = ?",
                              (message.from_user.id,)).fetchall()

    if len(now_product) == 0:
        await message.answer("Вы еще не записали в таблицу продукты, начните заполнение сейчас!⬇️",
                             reply_markup=kbs.edit_th)
    else:
        await message.answer(f'''Ваши продукты:
{pping(now_product)}''',
                             reply_markup=kbs.start_key)


@dp.message(F.text.lower() == "посмотреть просроченное")
async def see_old(message: Message):
    logger.info(f"Пользователь {message.from_user.id} хочет узнать список своих просроченных продуктов.")
    old_data = cur.execute("SELECT * FROM Users WHERE id = ?",
                           (message.from_user.id,)).fetchall()
    now_data = datetime.now().date()
    convert_result = []

    for i in old_data:
        try:
            if not re.match(r"\d{4}-\d{2}-\d{2}", str(i[2])):
                logging.warning(f"Неверный формат даты: {i[2]}")
                continue

            obj_data = str(i[2]).split("-")
            first = date(int(obj_data[0]), int(obj_data[1]), int(obj_data[2]))

            delta = (first - now_data).days
            if delta <= 0:
                convert_result.append([i[1], i[2]])
        except (ValueError, IndexError) as e:
            logging.error(f"Ошибка при обработке даты: {e}")
            continue

    if len(convert_result) == 0:
        all_product = len(old_data)
        await message.answer(f'''У вас нет просроченных продуктов🌱
        
Всего продуктов: {all_product}''',
                             reply_markup=kbs.start_key)

    else:
        await message.answer(f'''Ваши просроченные продукты:
{pping(convert_result)}''',
                             reply_markup=kbs.delete_func())


@dp.callback_query(kbs.Old.filter(F.action.in_(["out_del", "no_out"])))
async def old_thing(call: CallbackQuery, callback_data: kbs.Old):
    if callback_data.action == "out_del":
        old_data = cur.execute("SELECT * FROM Users WHERE id = ?",
                               (call.from_user.id,)).fetchall()
        now_data = datetime.now().date()
        convert_result = []

        if len(old_data) != 0:
            for i in old_data:
                obj_data = str(i[2]).split("-")
                first = date(int(obj_data[0]), int(obj_data[1]), int(obj_data[2]))
                how_days = (first - now_data).days
                if how_days<= 0:
                    convert_result.append([i[1], i[2]])

        for i in convert_result:
            cur.execute("DELETE FROM Users WHERE (product, data) = (?, ?)",
                        (i[0], i[1]))
            con.commit()
        await call.message.answer("Все просроченное удалено✅",
                                  reply_markup=kbs.start_key)

    elif callback_data.action == "no_out":
        await call.message.answer("Вы не удалили просроченное, продолжайте работу",
                                  reply_markup=kbs.start_key)

    await call.answer()


@dp.message(F.text.lower() == "в главное меню")
async def beck_to_men(message: Message):
    logger.info(f"Пользователь {message.from_user.id} хочет вернуться в главное меню.")
    await message.answer("Выберите действие⬇️",
                         reply_markup=kbs.start_key)


class Dele(StatesGroup):
    del_object = State()


@dp.message(F.text.lower() == "удалить продукт")
async def del_norm(message: Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} хочет удалить какой-то продукт.")

    now_product = cur.execute("SELECT product, data FROM Users WHERE id = ?",
                              (message.from_user.id,)).fetchall()

    if len(now_product) > 0:
        await state.set_state(Dele.del_object)
        await message.answer(f"Ваши продукты: \n{pping(now_product)}")

        builder = ReplyKeyboardBuilder()
        for i in range(len(now_product)):
            builder.add(types.KeyboardButton(text=str(i + 1)))
        builder.adjust(3)

        builder.row(types.KeyboardButton(text="Отмена"))

        await message.answer('''Отправьте номер продукта, чтобы удалить его📲''',
                             reply_markup=builder.as_markup(resize_keyboard=True))
    else:
        await message.answer("У вас нет записанных продуктов, начните заполнять таблицу⬇️",
                             reply_markup=kbs.edit_th)


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
        await message.answer("Удаление отменено.",
                             reply_markup=kbs.start_key)
        await state.clear()
        return

    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите номер продукта (например, 1, 2, 3).",
                             reply_markup=kbs.func_otmena())
        return

    product_index = int(message.text) - 1
    if product_index < 0 or product_index >= len(now_product):
        await message.answer(f"Номер продукта должен быть от 1 до {len(now_product)}. Попробуйте снова.")
        return

    now_work = now_product[product_index]
    cur.execute("DELETE FROM Users WHERE (id, product, data) = (?, ?, ?)",
                (now_work[0], now_work[1], now_work[2]))
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
    logger.info(f"Пользователь {message.from_user.id} хочет добавить какой-то продукт.")

    await state.set_state(Form.obje)
    await message.answer("Введите только название продукта⬇️",
                         reply_markup=kbs.func_otmena())


@dp.message(Form.obje)
async def name_prod(message: Message, state: FSMContext):
    logger.info(f"Пользователь {message.from_user.id} хочет указать срок годности нового продукта.")

    calendar = SimpleCalendar(
        locale=await get_user_locale(message.from_user),
        show_alerts=True
    )

    await state.update_data(obje=message.text)
    await state.set_state(Form.date)

    await message.answer(
        f'''📅 Укажите срок годности:

Выберите дату из календаря или введите вручную в формате {date.today()}''',
        reply_markup=await calendar.start_calendar()
    )


@dp.callback_query(SimpleCalendarCallback.filter())
async def process_calendar_selection(callback_query: CallbackQuery, state: FSMContext,
                                     callback_data: SimpleCalendarCallback):
    calendar = SimpleCalendar(
        locale=await get_user_locale(callback_query.from_user),
        show_alerts=True
    )

    selected, date = await calendar.process_selection(callback_query, callback_data)
    if selected:
        formatted_date = date.strftime("%Y-%m-%d")
        await state.update_data(date=formatted_date)

        all_data = await state.get_data()
        user_id = callback_query.from_user.id

        product_name = all_data["obje"]
        expiration_date = all_data["date"]

        try:
            cur.execute("INSERT INTO Users (id, product, data) VALUES (?, ?, ?)",
                        (user_id, product_name, expiration_date))
            con.commit()

            url = "https://api.unsplash.com/search/photos"
            headers = {"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
            params = {"query": product_name, "per_page": 1}

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data["results"]:
                image_url = data["results"][0]["urls"]["regular"]
                await callback_query.message.answer_photo(
                    photo=image_url,
                    caption=f"Продукт '{product_name}' добавлен с сроком годности {expiration_date}!"
                )
            else:
                await callback_query.message.answer(
                    '''Продукт '{product_name}' добавлен с сроком годности {expiration_date}.

Картинка не найдена 🥺

Если хотите увидеть изображение, в следующий раз введите название на английском языке'''
                )

            await callback_query.message.answer('''Супер, запись создана👍

Что дальше?🤔''',
                                                reply_markup=kbs.start_key)
            await state.clear()

        except requests.RequestException as e:
            logger.error(f"Ошибка при поиске изображения: {e}")
            await callback_query.message.answer(
                f'''Продукт '{product_name}' добавлен с сроком годности {expiration_date}
                 
Картинка не найдена 🥺

Если хотите увидеть изображение, в следующий раз введите название на английском языке'''
            )

            await callback_query.message.answer(
                '''Супер, запись создана👍
Что дальше?🤔''',
                reply_markup=kbs.start_key)
            await state.clear()

        except Exception as e:
            logger.error(f"Ошибка при вставке в базу данных: {e}")
            await callback_query.message.answer("Произошла ошибка.")
            await state.clear()

    await callback_query.answer()


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
        if month > 12 or month < 1:
            return 0
        if day > 31 or day < 1:
            return 0
    try:
        date(year, month, day)
        return 1
    except ValueError:
        return 0
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
        await message.answer(
            ''''Супер, запись создана👍

Что дальше?🤔''',
            reply_markup=kbs.start_key)

    else:
        await message.reply(
            f'''Вы ввели дату в неправильном формате.😢

‼️Попытайтесь еще раз в формате {datetime.date.today()}
(год, месяц, число)⬇️''',
            reply_markup=kbs.back_to_menu)


@dp.message(StateFilter(None))
async def handle_unexpected(message: Message):
    if message.text:
        await message.answer(
            '''Я не понимаю эту команду 😢
            
Используйте     ➡️/help для списка справок
или выберите действия из меню    ➡️/open_choice''',
            reply_markup=kbs.start_key
        )
    else:
        await message.answer("Пожалуйста, используйте команды из меню выбора или из меню кнопок",
                             reply_markup=kbs.start_key)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

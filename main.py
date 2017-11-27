# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import sqlite3
import time
import random
import logging
import queue
import json
from enum import Enum
from datetime import datetime
from operator import itemgetter

import telepot
import telepot.aio
from telepot.namedtuple import (
    InlineKeyboardButton, InlineKeyboardMarkup
)

from config import config


quizes = {}
pm_keyboards = {}
state = {}
user_questions = {}
chat_timeout = {}
user_pm_flags = {}


class CreateQuestionStates(Enum):
    NewQuestion = 1
    AddAnswer = 2
    AddCategory = 3
    EndQuestions = 4
    MarkButton = 5


class DeleteQuestionStates(Enum):
    NextPage = 1
    PrevPage = 2
    DelQuestion = 3


if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(format='%(asctime)s %(name)s [%(levelname)s]: %(message)s', level=logging.INFO)
fh = logging.FileHandler(f'logs/{datetime.now().strftime("%H.%M.%S-%Y.%m.%d")}.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter('%(asctime)s %(name)s [%(levelname)s]: %(message)s'))
logger = logging.getLogger(config.BOT_USERNAME)
logger.addHandler(fh)
bot = telepot.aio.Bot(config.BOT_TOKEN)
aio_loop = asyncio.get_event_loop()

if not os.path.exists('questions.sqlite3'):
    logger.warning('Please ensure that you\'ve run create_db.py file before starting bot')
    raise FileNotFoundError('Please ensure that you\'ve run create_db.py file before starting bot')
db = sqlite3.connect('questions.sqlite3')
cursor = db.cursor()
question_count = len(cursor.execute('SELECT * FROM questions').fetchall())

if not os.path.exists('questions'):
    os.makedirs('questions')

if not os.path.exists('chats'):
    os.makedirs('chats')


def get_questions(num=5) -> list:
    q = cursor.execute('SELECT * FROM questions').fetchall()
    _q = random.sample(q, num)
    random.shuffle(_q)
    an = list()
    for i, db_inst in enumerate(_q):
        id_, categ, quest, answ, answers, has_file, is_button = db_inst
        a_1 = json.loads(answ) + json.loads(answers)
        random.shuffle(a_1)
        an.append({
            'question': quest,
            'has_file': bool(has_file),
            'is_button': bool(is_button),
            'category': categ,
            'answers': [],
            'answ': [],
            'id': id_
        })
        for j, item in enumerate(a_1, 1):
            an[i]['answers'].append({item['text'].lower(): item['answ'], j: item['answ']})
            an[i]['answ'].append(f'{j}. {item["text"]}')
    random.shuffle(an)
    return an


def commit_question(obj, user_id, question_id):
    if 'category' in obj[user_id]:
        category = obj[user_id]['category']
    else:
        category = ''
    if 'question' in obj[user_id]:
        question = obj[user_id]['question']
    else:
        question = ''
    if 'answers' not in obj[user_id]:
        return False
    answ = json.dumps(list(filter(lambda x: True.__eq__(x['answ']), obj[user_id]['answers'])))
    answers = json.dumps(list(filter(lambda x: False.__eq__(x['answ']), obj[user_id]['answers'])))
    has_file = is_button = 0
    if 'has_file' not in user_questions[user_id] or 'is_button' not in obj[user_id]:
        pass
    elif 'has_file' in obj[user_id]:
        has_file = int(obj[user_id]['is_button'])
    elif 'is_button' in obj[user_id]:
        is_button = int(user_questions[user_id]['has_file'])
    else:
        has_file = int(obj[user_id]['has_file'])
        is_button = int(obj[user_id]['is_button'])
    cursor.execute(
        'INSERT INTO questions (id, category, question, answer, answers, has_file, is_button) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (
            question_id,
            category,
            question,
            answ,
            answers,
            has_file,
            is_button
        )
    )
    db.commit()
    return True


async def send_question(chat_id):
    global quizes
    try:
        quizes[chat_id]['question'] = next(quizes[chat_id]['iter'])
    except StopIteration:
        return True
    quizes[chat_id]['i'] += 1
    answ = '\n'.join(quizes[chat_id]['question']['answ'])
    if quizes[chat_id]['question']['has_file']:
        with open(f'questions/{quizes[chat_id]["question"]["id"]}/image.png', 'rb') as img_f:
            if quizes[chat_id]['question']['is_button']:
                quizes[chat_id]['messages'].append(telepot.message_identifier(
                    await bot.sendPhoto(chat_id, img_f)
                ))
                quizes[chat_id]['messages'].append(telepot.message_identifier(
                    await bot.sendMessage(
                        chat_id,
                        f'*Вопрос №{quizes[chat_id]["i"]}*\n'
                        f'{quizes[chat_id]["question"]["question"]}\n'
                        f'{answ}',
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(
                                text=j, callback_data=str(j)
                            ) for j, _ in enumerate(quizes[chat_id]['question']['answers'], 1)]]
                        ),
                        parse_mode='Markdown'
                    )
                ))
            else:
                quizes[chat_id]['messages'].append(telepot.message_identifier(
                    await bot.sendPhoto(chat_id, img_f)
                ))
                quizes[chat_id]['messages'].append(telepot.message_identifier(
                    await bot.sendMessage(
                        chat_id,
                        f'*Вопрос №{quizes[chat_id]["i"]}*\n'
                        f'{quizes[chat_id]["question"]["question"]}\n'
                        f'{answ}',
                        parse_mode='Markdown'
                    )
                ))
    else:
        if quizes[chat_id]['question']['is_button']:
            quizes[chat_id]['messages'].append(telepot.message_identifier(
                await bot.sendMessage(
                    chat_id,
                    f'*Вопрос №{quizes[chat_id]["i"]}*\n'
                    f'{quizes[chat_id]["question"]["question"]}\n'
                    f'{answ}',
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(
                            text=j, callback_data=str(j)
                        ) for j, _ in enumerate(quizes[chat_id]['question']['answers'], 1)]]
                    ),
                    parse_mode='Markdown'
                )
            ))
        else:
            quizes[chat_id]['messages'].append(telepot.message_identifier(
                await bot.sendMessage(
                    chat_id,
                    f'*Вопрос №{quizes[chat_id]["i"]}*\n'
                    f'{quizes[chat_id]["question"]["question"]}\n'
                    f'{answ}',
                    parse_mode='Markdown'
                )
            ))
    return False


async def cleanup(chat_id):
    global quizes
    for message in quizes[chat_id]['messages']:
        await bot.deleteMessage(message)
        await asyncio.sleep(0.1)


async def handle(msg):
    global quizes, pm_keyboards, state, question_count, chat_timeout, user_pm_flags, user_questions
    if 'data' in msg:
        content_type, chat_type, chat_id = telepot.glance(msg['message'])
        message_id = msg['message']['message_id']
        user_id = msg['message']['chat']['id']
        text = None
        if 'text' in msg:
            text = msg['message']['text']
    else:
        content_type, chat_type, chat_id = telepot.glance(msg)
        message_id = msg['message_id']
        user_id = msg['chat']['id']
        text = None
        if 'text' in msg:
            text = msg['text']
    command = None
    cargs = []
    if text:
        command, *cargs = text.split(' ')
    logger.info(f'Got message from {chat_id}-{chat_type} with text: {text}')
    if 'data' in msg:
        if chat_type == 'private':
            if msg['data'] == str(CreateQuestionStates.EndQuestions):
                await bot.deleteMessage(pm_keyboards[chat_id])
                if not commit_question(user_questions, user_id, question_count):
                    await bot.sendMessage(chat_id, 'Не удалось добавить вопрос. Не все данные были заполнены.')
                else:
                    question_count += 1
            elif msg['data'] == str(CreateQuestionStates.NewQuestion):
                user_questions[user_id] = {}
                user_pm_flags[user_id] = {}
                user_pm_flags[user_id]['add_question'] = True
                await bot.sendMessage(chat_id, 'Пожалуйста введите вопрос')
            elif msg['data'] == str(CreateQuestionStates.AddAnswer):
                user_pm_flags[user_id]['add_answer'] = True
                await bot.sendMessage(chat_id, 'Пожалуйста введите ответ')
            elif msg['data'] == str(CreateQuestionStates.AddCategory):
                user_pm_flags[user_id]['add_category'] = True
                await bot.sendMessage(chat_id, 'Пожалуйста введите категорию')
            elif msg['data'] == str(CreateQuestionStates.MarkButton):
                if 'is_button' in user_questions[user_id]:
                    user_questions[user_id]['is_button'] = not user_questions[user_id]['is_button']
                    await bot.sendMessage(
                        chat_id,
                        'Кнопки будут добавленны к вопросу во время викторины' if user_questions[user_id]['is_button']
                        else 'Кнопки не будут добавленны к вопросу во время викторины'
                    )
                else:
                    user_questions[user_id]['is_button'] = True
        elif any(map(chat_type.__eq__, ['supergroup', 'group'])):
            answer = telepot.message_identifier(msg['message'])
            if answer == quizes[chat_id]['messages'][-1]:
                ans = int(msg['data'])
                for d in quizes[chat_id]['question']['answers']:
                    if ans in d:
                        if d[ans]:
                            if msg['from']['first_name'] in quizes[chat_id]['users']:
                                quizes[chat_id]['users'][msg['from']['first_name']] += 1
                            else:
                                quizes[chat_id]['users'][msg['from']['first_name']] = 1
                            quizes[chat_id]['messages'].append(
                                telepot.message_identifier(
                                    await bot.sendMessage(
                                        chat_id,
                                        f'Правильный ответ({msg["data"]}) дал(а): {msg["from"]["first_name"]}'
                                    )
                                )
                            )
                            if await send_question(chat_id):
                                await asyncio.sleep(3)
                                await cleanup(chat_id)
                                res = '\n'.join(f'{item}: {r}' for item, r in
                                                sorted(quizes[chat_id]['users'].items(), key=itemgetter(1), reverse=True))
                                await bot.sendMessage(
                                    chat_id,
                                    f'Викторина окончена\n'
                                    f'Результаты\n'
                                    f'{res}'
                                )
    if text:
        if user_id in user_pm_flags:
            if 'add_question' in user_pm_flags[user_id]:
                if user_pm_flags[user_id]['add_question']:
                    user_questions[user_id]['question'] = text
                    user_pm_flags[user_id] = {}
            elif 'add_answer' in user_pm_flags[user_id]:
                if user_pm_flags[user_id]['add_answer']:
                    if 'answers' in user_questions[user_id]:
                        user_questions[user_id]['answers'].append({'text': text})
                    else:
                        user_questions[user_id]['answers'] = []
                        user_questions[user_id]['answers'].append({'text': text})
                    user_pm_flags[user_id] = {}
                    user_pm_flags[user_id]['mark_answer'] = True
                    await bot.sendMessage(chat_id, 'Является ли этот ответ правильным (да/нет или yes/no)')
            elif 'mark_answer' in user_pm_flags[user_id]:
                if user_pm_flags[user_id]['mark_answer']:
                    if any(map(text.lower().__eq__, ['да', 'y', 'yes', 'д'])):
                        user_questions[user_id]['answers'][-1]['answ'] = True
                    elif any(map(text.lower().__eq__, ['нет', 'н', 'no', 'n'])):
                        user_questions[user_id]['answers'][-1]['answ'] = False
                    user_pm_flags[user_id] = {}
                    await bot.sendMessage(chat_id, 'Можете добавить ещё ответов, или закончить над этим вопросом.')
            elif 'add_category' in user_pm_flags[user_id]:
                if user_pm_flags[user_id]['add_category']:
                    user_questions[user_id]['category'] = text
            elif 'caption' in user_pm_flags[user_id]:
                if any(map(text.lower().__eq__, ['да', 'y', 'yes', 'д'])):
                    await bot.sendMessage(chat_id, 'Введите подпись для фото(не более 160 символов)')
                    user_pm_flags[user_id] = {}
                    user_pm_flags[user_id]['add_caption'] = True
                else:
                    user_pm_flags[user_id] = {}
            elif 'add_caption' in user_pm_flags[user_id]:
                if len(text) <= 160:
                    user_questions[user_id]['question'] = text
                    user_pm_flags[user_id] = {}
                else:
                    await bot.sendMessage(chat_id, ('Введённое сообщение превышает ограничение в 160 символов\n'
                                                    'Пожалуйста введите подпись длинной меньше чем ограничение'))
    if not text:
        if user_id in user_pm_flags:
            if 'add_question' in user_pm_flags[user_id]:
                if content_type == 'photo':
                    if not os.path.exists(f'questions/{question_count}/'):
                        os.makedirs(f'questions/{question_count}/')
                    await bot.download_file(msg['photo'][-1]['file_id'], f'questions/{question_count}/image.png')
                    user_questions[user_id]['has_file'] = True
                    user_pm_flags[user_id] = {}
                    user_pm_flags[user_id]['caption'] = True
                    await bot.sendMessage(chat_id, 'Хотите ли добавить подпись под фото (да/нет)?')
    if command == '/roll':
        if len(cargs) == 0:
            await bot.sendMessage(chat_id, random.randint(1, 6))
        elif len(cargs) == 1:
            await bot.sendMessage(chat_id, random.randint(1, int(cargs[0])))
        elif len(cargs) == 2:
            await bot.sendMessage(chat_id, random.randint(int(cargs[0]), int(cargs[1])))
    if any(map(chat_type.__eq__, ['supergroup', 'group'])):
        if 'reply_to_message' in msg:
            answer = telepot.message_identifier(msg['reply_to_message'])
            if answer in quizes[chat_id]['messages']:
                user_msg = telepot.message_identifier(msg)
                if user_msg not in quizes[chat_id]['messages']:
                    quizes[chat_id]['messages'].insert(0, user_msg)
            if answer == quizes[chat_id]['messages'][-1]:
                ans = int(text)
                for d in quizes[chat_id]['question']['answers']:
                    if ans in d:
                        if d[ans]:
                            if msg['from']['first_name'] in quizes[chat_id]['users']:
                                quizes[chat_id]['users'][msg['from']['first_name']] += 1
                            else:
                                quizes[chat_id]['users'][msg['from']['first_name']] = 1
                            quizes[chat_id]['messages'].append(
                                telepot.message_identifier(
                                    await bot.sendMessage(
                                        chat_id,
                                        f'Правильный ответ({text}) дал(а): {msg["from"]["first_name"]}'
                                    )
                                )
                            )
                            if await send_question(chat_id):
                                await asyncio.sleep(3)
                                await cleanup(chat_id)
                                res = '\n'.join(f'{item}: {r}' for item, r in
                                                sorted(quizes[chat_id]['users'].items(), key=itemgetter(1), reverse=True))
                                await bot.sendMessage(
                                    chat_id,
                                    f'Викторина окончена\n'
                                    f'Результаты\n'
                                    f'{res}'
                                )
        if command == '/quiz':
            if chat_id in chat_timeout:
                if chat_timeout[chat_id] < datetime.now():
                    del chat_timeout[chat_id]
                else:
                    admins = [d['user']['id'] for d in (await bot.getChatAdministrators(chat_id))]
                    if user_id in admins:
                        if len(cargs) == 0:
                            quizes[chat_id] = {'messages': [], 'questions': get_questions(), 'i': 0, 'users': {}}
                            quizes[chat_id]['iter'] = iter(quizes[chat_id]['questions'])
                            await send_question(chat_id)
                        elif len(cargs) == 1:
                            if cargs[0].isnumeric():
                                pass
                            else:
                                await bot.sendMessage(chat_id, "Пожалуйста, введите количество вопросов")
                    else:
                        await bot.sendMessage(chat_id, (f'Команда находится на тайм-ауте\n'
                                                        f'Следующий раз её можно будет запустить через: '
                                                        f'{(datetime.now() - chat_timeout[chat_id]).total_seconds()}'))
            else:
                if len(cargs) == 0:
                    if chat_id in quizes:
                        await bot.sendMessage(chat_id, "Викторина уже идёт")
                    else:
                        quizes[chat_id] = {'messages': [], 'questions': get_questions(), 'i': 0, 'users': {}}
                        quizes[chat_id]['iter'] = iter(quizes[chat_id]['questions'])
                        await send_question(chat_id)
                elif len(cargs) == 1:
                    if cargs[0].isnumeric():
                        pass
                    else:
                        await bot.sendMessage(chat_id, 'Пожалуйста, введите количество вопросов')
    if chat_type == 'private':
        if command == '/new_question':
            pm_keyboards[chat_id] = telepot.message_identifier(
                await bot.sendMessage(
                    chat_id, 'Выберите вариант:',
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=
                        [
                            [
                                InlineKeyboardButton(text='Добавить вопрос',
                                                     callback_data=str(CreateQuestionStates.NewQuestion)),
                                InlineKeyboardButton(text='Добавить ответ',
                                                     callback_data=str(CreateQuestionStates.AddAnswer))
                            ],
                            [
                                InlineKeyboardButton(text='Ответы кнопками?',
                                                     callback_data=str(CreateQuestionStates.MarkButton))
                            ],
                            [
                                InlineKeyboardButton(text='Категория',
                                                     callback_data=str(CreateQuestionStates.AddCategory)),
                                InlineKeyboardButton(text='Закончить добавление вопросов',
                                                     callback_data=str(CreateQuestionStates.EndQuestions))
                            ]
                        ]
                    )
                )
            )


def main():
    aio_loop.create_task(bot.message_loop(handle))

    aio_loop.run_forever()


if __name__ == '__main__':
    main()

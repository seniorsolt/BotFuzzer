import asyncio
import time
from contextlib import asynccontextmanager

import pyrogram
from pyrogram import filters
from pyrogram.errors import MessageIdInvalid, FloodWait
from pyrogram.handlers import MessageHandler, EditedMessageHandler, RawUpdateHandler
from dotenv import load_dotenv
from pydantic import BaseModel
from pyrogram.types import Message

load_dotenv()


class AIResponse(BaseModel):
    """pydantic model to get Structured Outputs from openai"""
    is_expected: bool
    text: str


class ActionFactory:
    @staticmethod
    async def create_action(kind, client, **kwargs):
        if kind == 'send_text_message':
            return SendTextMessageAction(client, **kwargs)
        elif kind == 'send_random_text_message':
            return SendRandomTextMessageAction(client)
        elif kind == 'send_ai_text_message':
            action = await SendAITextMessageAction.create(client,
                                                          kwargs['parent'],
                                                          kwargs['action_in'],
                                                          kwargs['bot_message'],
                                                          kwargs['actions'],
                                                          )
            return action if action.text else None
        elif kind == 'push_inline_button':
            return PushInlineButtonAction(client, **kwargs)
        else:
            raise ValueError(f"Unknown action type: {kind}")


class BaseTelegramAction:
    """base class of action"""
    def __init__(self, client):
        self.client = client
        self.text = None
        self.kind = None
        self.target_chat = self.client.target_bot
        self.response_event = asyncio.Event()
        self.action_result = None

    async def perform(self, detached=False):
        raise NotImplementedError("Subclasses must implement this method")

    async def _finalize_action(self, detached):
        if not self.client.current_action_update_buffer:
            self.action_result = 'Timeout'
            self.client.current_action_update_buffer.append(self.action_result)

        self.client.current_action_update_buffer.sort(key=lambda update: getattr(update, 'id', -1))

        new_states = [self.client.current_state]

        for i, update in enumerate(self.client.current_action_update_buffer):
            from Tester import StateNode
            new_state = await StateNode.create(
                self.client,
                parent=None if detached else new_states[-1],
                action_in=self if i == 0 else None,
                result=update
            )
            new_states.append(new_state)

        self.client.current_action_update_buffer = []
        return new_states[1:]

    def _update_last_minute_requests(self):
        now = time.time()
        self.client.last_minute_requests.append(now)
        while self.client.last_minute_requests and self.client.last_minute_requests[0] < now - 60:
            self.client.last_minute_requests.popleft()

    async def _ensure_minimum_sleep_time(self, start_time):
        elapsed_time = time.monotonic() - start_time
        remaining_sleep_time = self.client.min_time_to_wait - elapsed_time
        if remaining_sleep_time > 0:
            await asyncio.sleep(remaining_sleep_time)

    @asynccontextmanager
    async def manage_handler(self, handler, group=1):
        try:
            self.client.add_handler(handler, group=group)
            self.client.tester_logger.debug(f"Handler was added")
            yield
        finally:
            self.client.remove_handler(handler, group=group)
            self.client.tester_logger.debug(f"Handler was removed")

    async def handle_response(self, client, update, users, chats):
        parser = self.client.dispatcher.update_parsers.get(type(update), None)

        parsed_update, handler_type = (
            await parser(update, users, chats)
            if parser is not None
            else (None, type(None))
        )
        filter = filters.chat(self.target_chat)
        if isinstance(parsed_update, Message):
            message = parsed_update
            if not await filter(client, message=message):
                return
            else:
                if getattr(message, 'text', None):
                    message_text = f'{message.text[:50]}  id: {message.id}'
                    self.client.tester_logger.debug(f"Got message: {message_text}")
                elif getattr(message, 'caption', None):
                    message_text = f'{message.caption[:50]}  id: {message.id}'
                    self.client.tester_logger.debug(f"Got message: {message_text}")
                self.client.tester_logger.debug(f"append {message}")
                self.client.current_action_update_buffer.append(message)
                self.response_event.set()

    async def __call__(self, detached=False):
        return await self.perform(detached)

    def __repr__(self):
        return f'{self.kind}: {getattr(self, "text", None)}'

    def __eq__(self, other):
        if not isinstance(self, type(other)):
            return False
        elif getattr(self, 'text', None) != getattr(other, 'text', None):
            return False
        elif getattr(self, 'kind', None) != getattr(other, 'kind', None):
            return False
        # elif getattr(self, 'callback_data', None) != getattr(other, 'callback_data', None):
        #     return False
        else:
            return True

    def __hash__(self):
        return hash((
            self.text,
            self.kind,
            # getattr(self, 'callback_data', None)
        ))


class SendTextMessageAction(BaseTelegramAction):
    def __init__(self, client, text):
        super().__init__(client)
        self.text = text
        self.kind = 'send_text_message'

    async def perform(self, detached=False):
        self.client.tester_logger.debug(f"Perform action: {self}")
        # handler = MessageHandler(self.handle_response, filters.chat(self.target_chat))
        # handler = RawUpdateHandler(self.handle_response)
        # self.client.add_handler(handler, group=1)

        start_time = time.monotonic()

        self._update_last_minute_requests()

        async with self.manage_handler(RawUpdateHandler(self.handle_response)):
            try:
                self.client.tester_logger.debug(f"Send message with text: {self.text}")
                await self.client.send_message(self.target_chat, self.text)

            except asyncio.TimeoutError:
                self.client.current_action_update_buffer.append('Timeout')
                self.action_result = 'Timeout'

            except FloodWait as fw:
                print(f'{fw}\n\nFloodRate:{len(self.client.last_minute_requests)} api calls per last minute')
                self.client.exporter.export_to_drawio()
                await asyncio.sleep(fw.value)

            await self._ensure_minimum_sleep_time(start_time)

        # self.client.remove_handler(handler, group=1)

        return await self._finalize_action(detached)


class SendRandomTextMessageAction(SendTextMessageAction):
    def __init__(self, client):
        super().__init__(client, text='bla bla bla 111')
        self.kind = 'send_random_text_message'


class SendAITextMessageAction(SendTextMessageAction):
    def __init__(self, client, text):
        super().__init__(client, text=text)
        self.kind = 'send_ai_text_message'

    @classmethod
    async def create(cls, client, parent, action_in, bot_message, actions):
        prompt = await cls._make_prompt(parent, action_in, bot_message, actions)
        is_text_message_expected, text = await cls._check_if_text_message_expected(client, prompt)
        return cls(client, text)

    @classmethod
    async def _check_if_text_message_expected(cls, client, prompt):
        completion = await client.openai_client.beta.chat.completions.parse(
            messages=[
                {
                    "role": "system",
                    "content": """Ты тестируешь телеграм бота от лица юзера. 
                    Тебе приходит сообщение от него. Твоя задача определить, ожидает ли бот от тебя текстовое сообщение.
                    Если ответ да - твоя задача максимально реалистично симитировать реального юзера. 
                    Если бот хочет от тебя имя и фамилию - ты придумываешь имя и фамилию.
                    Если бот хочет от тебя почту и телефон - ты придумываешь почту и телефон, которые похожи на настоящие.
                    Если бот задает тебе свободный вопрос - ты придумываешь сообщение, которое мог бы написать реальный юзер.

Examples:

"Please enter your name": the bot is expecting a name. Output: {"is_expected": true, "text": "Max Ivanov"}

"Click the button below to continue": the bot is not expecting a text response, only a button click. Output: {"is_expected": false, "text": none}

"What's your favourite color?": the bot is expecting a response. Output: {"is_expected": true, "text": "Green"}

"Operation completed successfully. No further action is needed.": the bot is not expecting a response. Output: {"is_expected": false, "text": none}

"What's your phone?": the bot is expecting a phone. Output: {"is_expected": true, "text": "+79607777777"}

Your goal is to determine if the bot is waiting for text input or not, and generate the corresponding JSON response. 
Keep in mind that if there are other available actions that can answer the bot's message, the user might not need to 
type a response. In such cases, consider the user interaction and respond accordingly.""",
                },
                {
                    "role": "user",
                    "content": f"Dialog between user and bot: {prompt}",
                }
            ],
            model="gpt-4o-mini",
            response_format=AIResponse
        )
        response = completion.choices[0].message.parsed.dict()
        is_text_message_expected = response.get('is_expected', '')
        text = response.get('text', '')

        return is_text_message_expected, text

    @classmethod
    async def _make_prompt(cls, parent, action_in, bot_message, actions):
        prompt = ""

        for i, state in enumerate(parent.path[1:], start=1):
            prompt += (f'user: {parent.path[i].action_in}\n'
                       f'bot: {parent.path[i].text}\n'
                       f'available user\'s actions: {parent.path[i].actions_out}\n')

        prompt += (f'user: {action_in}\n'
                   f'bot: {bot_message}\n'
                   f'available user\'s actions: {actions}\n')

        return prompt


class PushInlineButtonAction(BaseTelegramAction):
    def __init__(self, client, mes_id, button):
        super().__init__(client)
        self.kind = 'inline_button'
        self.text = button.text
        self.message_id = mes_id
        self.callback_data = button.callback_data
        self.callback_game = button.callback_game
        self.url = button.url
        self.web_app = button.web_app
        self.switch_inline_query = button.switch_inline_query
        self.switch_inline_query_current_chat = button.switch_inline_query_current_chat
        self.login_url = button.login_url
        self.user_id = button.user_id

    async def perform(self, detached=False):
        self.client.tester_logger.debug(f"Perform action: {self}")
        # handler = MessageHandler(self.handle_response, filters.chat(self.target_chat))
        # handler = RawUpdateHandler(self.handle_response)
        # self.client.add_handler(handler, group=1)

        start_time = time.monotonic()

        self._update_last_minute_requests()

        async with self.manage_handler(RawUpdateHandler(self.handle_response)):
            try:
                if self.callback_data:
                    await self.request_callback_answer()
                else:
                    text = '\n'.join(self._collect_attrs())
                    self.action_result = pyrogram.types.Message(id=0, text=text)

            except asyncio.TimeoutError:
                self.action_result = 'Timeout'

            except FloodWait as fw:
                print(f'{fw}\n\nFloodRate:{len(self.client.last_minute_requests)} api calls per last minute')
                self.client.exporter.export_to_drawio()
                await asyncio.sleep(fw.value)

            await self._ensure_minimum_sleep_time(start_time)

        # self.client.remove_handler(handler, group=1)
        # self.client.tester_logger.debug(f"Handler was deleted")

        return await self._finalize_action(detached)

    def _collect_attrs(self):
        target_attrs = ['url']
        buffer = []
        for attr, value in self.__dict__.items():
            if attr in target_attrs and value is not None:
                buffer.append(f'{attr}: {value}')
        return buffer

    async def request_callback_answer(self):
        try:
            self.client.tester_logger.debug(f"Request_callback_answer from message {self.message_id}")
            await self.client.request_callback_answer(
                self.target_chat,
                message_id=self.message_id,
                callback_data=self.callback_data
            )
        except TimeoutError:
            pass
        except MessageIdInvalid as e:
            self.action_result = pyrogram.types.Message(id=0, text='error ID_Invalid')
            print(e)
        await asyncio.wait_for(self.response_event.wait(), timeout=self.client.max_time_to_wait)

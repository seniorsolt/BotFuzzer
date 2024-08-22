import asyncio
import json
import os
from pyrogram import Client, filters
from dotenv import load_dotenv
from pyrogram.handlers import MessageHandler
from anytree import NodeMixin
from anytree.exporter import JsonExporter, DictExporter
load_dotenv()


class Tester(Client):
    def __init__(self,
                 target_bot,
                 name='TesterBot',
                 initial_actions='/start',
                 reset_action=None,
                 *args,
                 **kwargs
                 ):
        super().__init__(
            name=name,
            api_id=os.getenv('TELEGRAM_API_ID'),
            api_hash=os.getenv('TELEGRAM_API_HASH'),
            *args,
            **kwargs
        )
        self.total = -1
        self.target_bot = target_bot
        self.root = StateNode(client=self)
        self.initial_actions = initial_actions
        self.current_node = self.root
        self.current_state = self.root
        self.visited_states = set()
        self.reset_action = reset_action
        self.depth = 2

    async def test(self, node):
        for action in node.actions_out:
            if self.current_state.state_id != node.state_id:
                await self.restore_state(node)
            new_state = await action()
            self.current_state = new_state
            if new_state.actions_out and new_state.depth < self.depth:
                await self.test(new_state)

    async def restore_state(self, state):
        if self.reset_action:
            await self.reset_action()
        for i, node in enumerate(state.path[:-1]):
            if i == 0:
                await node.actions_out[0](create_new_state=False)
            else:
                await state.path[i+1].action_in(create_new_state=False)
        self.current_state = state


class Action:
    def __init__(self, client: Tester, kind: str, **kwargs):
        self.client = client
        self.kind = kind
        self.target_chat = self.client.target_bot
        if kind == 'send_random_text_message':
            self.text = 'bla bla bla'
        elif kind == 'push_reply_button':
            self.text = kwargs['reply_button']
        elif kind == 'push_inline_button':
            self.inline_button = kwargs['callback_data']
        elif kind == 'send_command':
            self.text = kwargs['text']

        self.response_event = asyncio.Event()
        self.action_result = None

    async def __call__(self, create_new_state=True):
        return await self.perform(create_new_state)

    async def perform(self, create_new_state=True):
        handler = MessageHandler(self.handle_response, filters.chat(self.target_chat))
        self.client.add_handler(handler, group=1)

        if self.kind == 'send_command':
            await self.client.send_message(self.target_chat, self.text)
            await self.response_event.wait()
            self.client.remove_handler(handler, group=1)

        if self.kind == 'push_reply_button':
            await self.client.send_message(self.target_chat, self.text)
            await self.response_event.wait()
            self.client.remove_handler(handler, group=1)

        await asyncio.sleep(2)

        if create_new_state:
            new_state_node = StateNode(self.client,
                                       parent=self.client.current_state,
                                       action_in=self,
                                       text=self.action_result.text or self.action_result.caption,
                                       result=self.action_result)
            return new_state_node
        else:
            return

    async def handle_response(self, client, message):
        self.action_result = message
        self.response_event.set()

    def __repr__(self):
        return f'{self.kind}: {self.text}'


class StateNode(NodeMixin):
    def __init__(self, client, parent=None, action_in=None, children=None, result=None, text=None):
        self.state_id = client.total + 1
        self.parent = parent
        self.action_in = action_in
        if children:
            self.children = children
        self.actions_out = self._explore_and_create_actions(client, result)
        self.text = text
        client.total += 1

    def _explore_and_create_actions(self, client, result):
        actions = []
        if result is None:
            actions.append(Action(client, kind='send_command', text='/start'))
            return actions
        if hasattr(result.reply_markup, 'keyboard'):
            for row in result.reply_markup.keyboard:
                for button in row:
                    actions.append(Action(client, kind='push_reply_button', reply_button=button))
        return actions


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Action):
            return repr(obj)
        return super().default(obj)


def custom_attr_iter(node):
    """custom function to process attrs of nodes for nice view"""
    res = []
    actions_out_item = None

    for k, v in node:
        v = str(v).strip('[]')
        if k == "actions_out":
            actions_out_item = (k, v)
        else:
            res.append((k, v))

    if actions_out_item:
        res.append(actions_out_item)
    return res


async def main():
    tester = Tester(target_bot="photo_aihero_bot")
    async with tester:
        await tester.test(node=tester.root)

    with open('tree.json', 'w', encoding='utf-8') as f:
        exporter = JsonExporter(indent=2,
                                ensure_ascii=False,
                                cls=CustomEncoder,
                                dictexporter=DictExporter(
                                    attriter=custom_attr_iter
                                    )
                                )

        tree = exporter.export(tester.root)
        f.write(tree)

if __name__ == "__main__":
    asyncio.run(main())

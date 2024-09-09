import copy
from functools import reduce
from anytree import NodeMixin
from src.actions import ActionFactory


class StateNode(NodeMixin):
    def __init__(self, state_id, parent=None, action_in=None, children=None,
                 actions_out=None, status='ok', text='', media=None):
        self.state_id = state_id
        self.parent = parent
        self.action_in = action_in
        self.children = children if children else []
        self.text = text
        self.media = media
        self.actions_out = actions_out
        self.status = status

    @classmethod
    async def create(cls, client, parent=None, action_in=None, result=None):
        state_id = client.total + 1
        text = getattr(result, 'text', '') or getattr(result, 'caption', '') if result != 'Timeout' else ''
        media = await cls._extract_and_proccess_media(client, result) if parent else None
        actions_out = await cls._explore_and_create_actions(client, result, text, action_in, parent)
        status = 'ok' if result != 'Timeout' else 'Timeout'
        client.total += 1

        return cls(state_id, parent=parent, action_in=action_in, text=text,
                   actions_out=actions_out, status=status, media=media)

    @classmethod
    async def _explore_and_create_actions(cls, client, result, text, action_in, parent):
        actions = []
        if result is None:
            action = await ActionFactory.create_action(kind='send_text_message',
                                                       client=client,
                                                       text='/start')
            actions.append(action)
            return actions

        if text and parent:
            action = await ActionFactory.create_action(kind='send_ai_text_message',
                                                       client=client,
                                                       parent=parent,
                                                       action_in=action_in,
                                                       bot_message=text,
                                                       actions=actions)
            if action:
                actions.append(action)
        if result == 'Timeout':
            # nothing to add
            return actions
        if hasattr(result.reply_markup, 'keyboard'):
            for row in result.reply_markup.keyboard:
                for button in row:
                    action = await ActionFactory.create_action(kind='send_text_message',
                                                               client=client,
                                                               text=button)
                    actions.append(action)
        elif hasattr(result.reply_markup, 'inline_keyboard'):
            for row in result.reply_markup.inline_keyboard:
                for button in row:
                    action = await ActionFactory.create_action(kind='push_inline_button',
                                                               client=client,
                                                               mes_id=result.id,
                                                               button=button)
                    actions.append(action)


        # if result is not None:
        #     # to check if unexpected text message will break target bot
        #     action = await ActionFactory.create_action(kind='send_random_text_message',
        #                                                client=client)
        #     # usually there is no need to test recursively random text action
        #     if action_in != action:
        #         actions.append(action)

        return actions

    @classmethod
    async def _extract_and_proccess_media(cls, client, result):
        try:
            filepath = await client.download_media(result)
        except ValueError as e:
            client.tester_logger.debug(f"Error while downloading media: {e}")
            filepath = None
        return filepath

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        # elif getattr(self, 'text', None) != getattr(other, 'text', None):
        #     return False
        elif self.action_in != other.action_in:
            return False

        self_actions_out = [action for action in self.actions_out if action.kind != 'send_ai_text_message']
        other_actions_out = [action for action in other.actions_out if action.kind != 'send_ai_text_message']

        if len(self_actions_out) != len(other_actions_out):
            return False
        for self_action, other_action in zip(self_actions_out, other_actions_out):
            if self_action != other_action:
                return False
        return True

    def __hash__(self):
        return hash((
            self.text,
            self.action_in,
            tuple(self.actions_out)
        ))

    def __str__(self):
        def function(res, attr):
            if attr[0] not in ('_NodeMixin__parent', '_NodeMixin__children'):
                res = res + f'{attr[0]}: {attr[1]}\n'
            return res

        return reduce(
            function,
            self.__dict__.items(),
            '\n'
        )

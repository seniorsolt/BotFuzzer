import json
from anytree import NodeMixin
from actions import ActionFactory, BaseTelegramAction


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
    async def create(cls, client, parent=None, action_in=None, result=None, restored=False):
        state_id = client.total + 1
        text = getattr(result, 'text', '') or getattr(result, 'caption', '') if result != 'Timeout' else ''
        media = await cls._extract_and_proccess_media(client, result, restored)
        actions_out = await cls._explore_and_create_actions(client, result, text, action_in, parent, restored)
        status = 'ok' if result != 'Timeout' else 'Timeout'
        client.total += 1

        return cls(state_id, parent=parent, action_in=action_in, text=text,
                   actions_out=actions_out, status=status, media=media)

    @classmethod
    async def _explore_and_create_actions(cls, client, result, text, action_in, parent, restored):
        actions = []
        if result is None:
            action = await ActionFactory.create_action(
                kind='send_text_message',
                client=client,
                text='/start'
            )
            actions.append(action)
            return actions

        if text and not restored and client.openai_client:
            action = await ActionFactory.create_action(
                kind='send_ai_text_message',
                client=client,
                parent=parent,
                action_in=action_in,
                bot_message=text,
                actions=actions
            )
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
    async def _extract_and_proccess_media(cls, client, result, restored):
        if result == 'Timeout' or restored:
            return None
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

        # self_isolated_parent = copy.copy(self.parent)
        # if self_isolated_parent is not None:
        #     self_isolated_parent.parent = None
        #
        # other_isolated_parent = copy.copy(other.parent)
        # if other_isolated_parent is not None:
        #     other_isolated_parent.parent = None
        #
        # if self_isolated_parent != other_isolated_parent:
        #     return False
        # if self.action_in != other.action_in:
        #     return False
        #
        # self_action_in = self.action_in if (self.action_in is not None
        #                                     and self.action_in.kind != 'send_ai_text_message') else None
        # other_action_in = other.action_in if (other.action_in is not None
        #                                       and other.action_in.kind not in ('send_ai_text_message', None)) else None
        #
        # if self_action_in != other_action_in:
        #     return False

        self_actions_out = [action for action in self.actions_out if action.kind != 'send_ai_text_message']
        other_actions_out = [action for action in other.actions_out if action.kind != 'send_ai_text_message']

        if len(self_actions_out) != len(other_actions_out):
            return False
        for self_action, other_action in zip(self_actions_out, other_actions_out):
            if self_action != other_action:
                return False
        return True

    def __hash__(self):
        return hash(self.state_id)

    def __str__(self):
        filtered_dict = {k: v for k, v in self.__dict__.items() if not k.startswith('_NodeMixin__')}

        return json.dumps(filtered_dict, indent=4, default=BaseTelegramAction.default, ensure_ascii=False)

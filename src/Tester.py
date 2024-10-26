import logging
import os
from collections import deque
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pyrogram import Client
from typing import Any, Callable, Optional, List, Union

from StateNode import StateNode

load_dotenv()


class Tester(Client):
    def __init__(
        self,
        target_bot: str,
        min_time_to_wait: float,
        max_time_to_wait: float,
        name: str = 'TesterBot',
        initial_actions: Union[str, List[str]] = '/start',
        reset_action: Optional[Callable] = None,
        max_depth: int = 3,
        max_repeats: int = 1,
        debug: bool = False,
        *args: Any,
        **kwargs: Any
    ):
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        if not api_id or not api_hash:
            raise ValueError("Environment variables TELEGRAM_API_ID and TELEGRAM_API_HASH must be set.")

        super().__init__(
            name=name,
            api_id=api_id,
            api_hash=api_hash,
            *args,
            **kwargs
        )
        self.total = -1
        self.target_bot = target_bot
        self.root = None
        self.initial_actions = initial_actions
        self.current_state = self.root
        self.reset_action = reset_action
        self.max_depth = max_depth
        self.max_repeats = max_repeats
        self.min_time_to_wait = min_time_to_wait
        self.max_time_to_wait = max_time_to_wait

        self.last_minute_requests = deque()
        self.current_action_update_buffer = []

        self.debug = debug
        self.tester_logger = self._setup_logger()

        self._exporter = None
        self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'),
                                         base_url=os.getenv('OPENAI_BASE_URL'))

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('TesterLogger')
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler("yaml_logs.yaml", encoding="utf-8-sig")
        file_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
        file_formatter = YamlLikeFormatter()  # Ensure this formatter is imported and available
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        return logger

    @classmethod
    async def create(cls,
                     target_bot,
                     name='TesterBot',
                     initial_actions='/start',
                     reset_action=None,
                     max_depth=3,
                     min_time_to_wait=10,
                     max_time_to_wait=15,
                     debug=False,
                     *args,
                     **kwargs):

        instance = cls(
            target_bot=target_bot,
            name=name,
            initial_actions=initial_actions,
            reset_action=reset_action,
            max_depth=max_depth,
            min_time_to_wait=min_time_to_wait,
            max_time_to_wait=max_time_to_wait,
            debug=debug,
            *args,
            **kwargs
        )

        instance.root = await StateNode.create(client=instance)
        instance.current_state = instance.root
        return instance

    @property
    def exporter(self):
        # lazy loading and internal import to avoid recursive issues
        # since Exporter uses BaseTelegramAction class from Tester.py
        if self._exporter is None:
            from export import Exporter
            self._exporter = Exporter(self.root)
        return self._exporter

    async def test(self, target_node):
        self.tester_logger.debug(f"Test state: {target_node}")
        for i in range(len(target_node.actions_out)):
            if self.current_state.state_id != target_node.state_id:
                is_success_to_restore_state = await self.restore_state(target_node)
                if not is_success_to_restore_state:
                    return

            result_of_action = await target_node.actions_out[i]()
            self.tester_logger.debug(f"Result of action: {result_of_action}")
            new_state = result_of_action[-1]
            self.tester_logger.debug(f"Current tree: {self.exporter.export_to_json()}")

            # Check for loops by counting occurrences of the new state in the path
            repeat_count = target_node.path.count(new_state)
            if repeat_count >= self.max_repeats:
                new_state.status = 'Loop!'
                self.current_state = new_state
                if self.debug:
                    duplicates = [state.state_id for state in target_node.path if state == new_state]
                    self.tester_logger.debug(
                        f"State {new_state} is repeated more than {self.max_repeats} times "
                        f"in the current branch. Dropping branch. Duplicate states: {duplicates}"
                    )
                continue

            # Update the current state and recursively test if conditions are met
            if new_state.status != 'Timeout' and new_state != target_node:
                self.current_state = new_state
                if new_state.actions_out and new_state.depth < self.max_depth:
                    await self.test(new_state)

    async def restore_state(self, target_state):
        self.tester_logger.debug(f"Restore state: {target_state}")
        self.tester_logger.debug(f"Tree BEFORE restoring: {self.exporter.export_to_json()}")

        if self.reset_action:
            await self.reset_action()

        for i in range(len(target_state.path[:-1])):
            # check if we need to perform action to state to change
            next_state = target_state.path[i + 1]
            next_state_action_in = next_state.action_in

            if next_state_action_in is None:
                self.tester_logger.debug(f"Skipping passive state: {next_state}")
                self.current_state = next_state
                continue

            if i == 0:
                self.current_state = target_state.path[0]
                result_of_action = await target_state.path[i + 1].action_in(restored=True)
                new_state = result_of_action[-1]
            else:
                index_of_action_to_call = self.current_state.actions_out.index(target_state.path[i + 1].action_in)
                result_of_action = await self.current_state.actions_out[index_of_action_to_call](restored=True)
                new_state = result_of_action[-1]

            self.tester_logger.debug(f'New state: {new_state}')
            self.tester_logger.debug(f"Target_state: id {target_state.state_id}")
            if new_state != target_state.path[i + len(result_of_action)]:
                message = f"Fail to restore state: {target_state.path[i + 1]} instead got state: {new_state}"
                self.tester_logger.debug(message)
                new_state.text = message
                new_state.actions_out = []
                return False

            await self._update_actions_out(target_state.path[i + len(result_of_action)], new_state)
            target_state.path[i + len(result_of_action)].action_in = new_state.action_in

            self.total -= len(result_of_action)
            for state in result_of_action:
                state.parent = None
            self.current_state = target_state.path[i + len(result_of_action)]
            self.tester_logger.debug(f"Current state: id {self.current_state.state_id}")

        self.tester_logger.debug(f"Tree AFTER restoring: {self.exporter.export_to_json()}")
        return True

    # def _handle_restore_failure(self, message, new_state=None):
    #     self.tester_logger.debug(message)
    #     if new_state:
    #         new_state.text = message
    #         new_state.actions_out = []

    async def _update_actions_out(self, target_state, new_state):
        # we need to update actions_out because new messages have another ids, it's important for inline buttons,
        # but restored states have no AI actions since AI will always produce different text
        temporary_actions = {}
        for i, action in enumerate(target_state.actions_out[:]):
            if action.kind == 'send_ai_text_message':
                temporary_actions[i] = action

        target_state.actions_out = [action for action in target_state.actions_out if
                                    action.kind != 'send_ai_text_message']

        for j, (target_action, new_action) in enumerate(zip(target_state.actions_out, new_state.actions_out)):
            if target_action == new_action:
                target_state.actions_out[j] = new_action
            else:
                raise TypeError(f'Target action and new_action have different kinds: '
                                f'{target_action.kind} and {new_action.kind}')
        for k, action in temporary_actions.items():
            target_state.actions_out.insert(k, action)


class YamlLikeFormatter(logging.Formatter):
    def format(self, record):
        super().format(record)
        message = f'{self.formatTime(record, "%Y-%m-%d %H:%M:%S")} - {record.levelname}'
        record_message = record.getMessage()

        yaml_like_log = f'{message}: {record_message}'
        return yaml_like_log

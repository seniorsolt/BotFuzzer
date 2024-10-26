# BotFuzzer

BotFuzzer is a tool for automated testing of telegram bots. You don't need to create any cases, mocks or suites, 
just let the BotFuzzer explore your bot.

The BotFuzzer algorithm is based on DFS: starting from the base state, which corresponds to an unregistered user, BotFuzzer explores the Telegram bot, aiming to cover all combinations of possible user states and available actions.

The result of the work is a tree of states and actions. Currently, export is supported in JSON and draw.io XML formats.

![image](https://github.com/user-attachments/assets/f6b1b0dc-a692-4ff2-ba5b-79f591b7b722)



## Installation

BotFuzzer is being developed with Python 3.10. Other versions have not been tested yet.

- Clone the repository `git clone https://github.com/seniorsolt/BotFuzzer.git`
- Navigate into the cloned directory `cd BotFuzzer`
- Set up a virtual environment `python -m venv venv`
- Activate the new venv:
    - Windows: `venv\scripts\activate`
    - Unix based systems: `source venv/bin/activate`
- Install the requirements `pip install -r requirements.txt`

- Create a `.env` file in the `BotFuzzer` folder. Obtain API_ID and API_HASH from https://my.telegram.org and put them into corresponding fields:

  ```
  TELEGRAM_API_ID=<your_api_id>
  TELEGRAM_API_HASH=<your_api_hash>
  ```
  
  BotFuzzer also support AI to perform text based actions: answer open questions, telling email or phone.
  If you want to use this feature, also put OPENAI_API_KEY in `.env`:

  ```
  OPENAI_API_KEY=<your_openai_api_key>
  ```
  
## Usage

The entry point is `main.py`, where you can configure the testing process by setting parameters for the Tester instance. The only required parameter is `target_bot="<bot_username>"`. Target bot is a bot you want to test. All other parameters are optional.

Then simply run main.py as usual.

```
async def main():
    tester = await Tester.create(target_bot="@photo_aihero_bot", max_depth=3)
    async with tester:
        try:
            await tester.test(target_node=tester.root)
        except Exception as e:
            traceback.print_exc()
        finally:
            tester.exporter.export_to_drawio(mode='tree')

if __name__ == "__main__":
    asyncio.run(main())
```

 BotFuzzer is currently under development, and errors are possible. 
 It is recommended to use exception handling and export result in the final section to avoid losing data.

> 💡 **NOTE**: To ensure the tool works correctly, the "/start" command must truly reset the bot's state to the initial state from any bot's state. Example: if there is a moment in the bot where the user is required to enter an email, a mask is set to check the format of the entered text, and other commands starting with a slash "/" have a lower priority, then /start will result in the bot continuing to require the email to be entered.

## Configuration Options

Configuration is set by passing arguments in Tester.create()
```
tester = await Tester.create(
    target_bot="@photo_aihero_bot",
    min_time_to_wait=5,
    max_time_to_wait=10,
    max_depth=3,
    max_repeats=1,
    debug=True
    )
```

All supported args and recommended values:
* target_bot - username of the bot you want to test. Example: "@photo_aihero_bot"
* min_time_to_wait - minimum time (in seconds) to wait for the bot's response. On one hand, we want to speed up testing by setting a low value, but on the other hand, too short a time may result in missing the bot's response or even getting temporarily blocked by Telegram for sending too many requests per minute. A reasonable range is between 4 and 10 seconds.
* max_time_to_wait - maximum time (in seconds) to wait for the bot's response. This sets the upper limit for how long to wait. The reasonable value depends on the bot's speed. Some AI bots may take longer than 15 seconds to respond, but usually 10 seconds is sufficient.
* max_depth - maximum depth of the state tree. For debugging, smaller values like 3, 5, or 7 are recommended. For testing larger bots, this value can be increased as needed.
* max_repeats - maximum number of repeated identical states to detect loops. If the current state has occurred more than max_repeats, it indicates a loop, and going deeper is unnecessary. Default value: 1.
* debug - enable debug mode. Set to True for detailed logging during development and testing, otherwise False.

## Export

There are three options to export result:

```
tester.exporter.export_to_json(save=True)
tester.exporter.export_to_drawio(mode='tree')
tester.exporter.export_to_drawio(mode='matrix')
```

* export_to_json: This exports the results in JSON format.
* export_to_drawio: Exports an XML file that can be opened in the drawio desktop app or online at https://www.drawio.com/.

**Example of mode='tree':**

![image](https://github.com/user-attachments/assets/63386c3f-b260-4efb-aa93-f232fc9b5688)

___

**Example of mode='matrix':**

![image](https://github.com/user-attachments/assets/9cc8b039-71f2-4ac1-921e-c3e07ea76ed4)



## Debug

Pass ```debug = True``` in Tester.create() to write and save logs in yaml format:
```
2024-10-26 20:22:40 - DEBUG: Test state: {
    "state_id": 0,
    "action_in": null,
    "text": "",
    "media": null,
    "actions_out": [
        "send_text_message: /start"
    ],
    "status": "ok"
}
2024-10-26 20:22:40 - DEBUG: Perform action: send_text_message: /start
2024-10-26 20:22:40 - DEBUG: Handler was added
2024-10-26 20:22:40 - DEBUG: Send message with text: /start
2024-10-26 20:22:40 - DEBUG: Got message: Привет! Я бот для генерации фотографий с твоим лиц  id: 189751
2024-10-26 20:22:45 - DEBUG: Handler was removed
2024-10-26 20:22:46 - DEBUG: Result of action: [<StateNode.StateNode object at 0x00000238F9941F60>]
2024-10-26 20:22:46 - DEBUG: Current tree: {
  "state_id": "0",
  "action_in": "None",
  "text": "",
  "media": "None",
  "status": "ok",
  "actions_out": "send_text_message: /start",
  "children": [
    {
      "state_id": "1",
      "action_in": "send_text_message: /start",
      "text": "Привет! Я бот для генерации фотографий с твоим лицом с помощью ИИ.\n\nКак использовать: выбери пол, стиль и пришли свою фотографию.\nЧерез несколько минут ты получишь нейрофото.\n\nТы можешь бесплатно сделать 5 фотографии. \nЗатем можно приобрести еще пакет фотографий.",
      "media": "C:\\Users\\Max\\Desktop\\PycharmProjects\\end2end_testing_tool_for_tg_bots\\BotFuzzer\\downloads\\photo_2024-04-07_18-56-53_7430136075953111048.jpg",
      "status": "ok",
      "actions_out": "send_ai_text_message: Я хочу создать фотографию!, send_text_message: Мужчина, send_text_message: Женщина"
    }
  ]
}
```

You can open the yaml_logs.yaml file in any text editor.
However, I use Sublime Text because it handles large logs efficiently, and you can fold all levels at once using hotkeys (search command: "fold_all").

## AI text-based actions

To use this feature, add `OPENAI_API_KEY` in the `.env` file as mentioned above. 
You can also use a local model if its backend provides an OpenAI-compatible API. Simply set `OPENAI_BASE_URL` in the `.env` file.

## Contributing

Contributions are welcome in any form

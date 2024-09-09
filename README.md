# BotFuzzer

BotFuzzer is a tool for automated testing of telegram bots. You don't need to create any cases, mocks or suites anymore.

The BotFuzzer algorithm is based on DFS: starting from the base state, which corresponds to an unregistered user, BotFuzzer explores the Telegram bot, aiming to cover all combinations of possible user states and their potential actions.

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

- Create a `.env` file in the `src` folder. Obtain API_ID and API_HASH from https://my.telegram.org and put them into corresponding fields:

  ```
  TELEGRAM_API_ID=<your_api_id>
  TELEGRAM_API_HASH=<your_api_hash>
  ```
  
## Usage

The entry point is `main.py`, where you can configure the testing process by setting parameters for the Tester instance. The only required parameter is `target_bot="<bot_username>"`. Target bot is a bot you want to test. All other parameters are optional.

Then simply run main.py as usual.

```
async def main():
    tester = Tester(target_bot="<bot_username>", max_depth=3)
    async with tester:
        await tester.test(node=tester.root)
        tester.exporter.export_to_drawio()

if __name__ == "__main__":
    asyncio.run(main())
```

## Contributing

Contributions are welcome in any form

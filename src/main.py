import asyncio
import pdb

from src.Tester import Tester
import traceback


async def main():
    tester = await Tester.create(target_bot="lanit_picnic_bot",
                                 max_depth=5,
                                 min_time_to_wait=6,
                                 debug=True)
    async with tester:
        try:
            await tester.test(target_node=tester.root)
        except Exception as e:
            traceback.print_exc()
            print(f'ERROR: {e}')
            pdb.post_mortem()
        finally:
            tester.exporter.export_to_drawio()

if __name__ == "__main__":
    asyncio.run(main())

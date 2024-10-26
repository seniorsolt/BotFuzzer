import asyncio
from Tester import Tester
import traceback


async def main():
    tester = await Tester.create(
        target_bot="@photo_aihero_bot",
        max_depth=5,
        min_time_to_wait=5,
        debug=True
    )

    async with tester:
        try:
            await tester.test(target_node=tester.root)
        except Exception as e:
            traceback.print_exc()
            print(f'ERROR: {e}')
        finally:
            tester.exporter.export_to_drawio(mode='tree')
            tester.exporter.export_to_drawio(mode='matrix')
            tester.exporter.export_to_json(save=True)

if __name__ == "__main__":
    asyncio.run(main())

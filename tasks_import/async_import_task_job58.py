import asyncio
import json
import time

import redis
import aredis

redis_pool = aredis.ConnectionPool(
    host='192.168.11.191',
    port=6380,
    db=1
)


def aredis_cli():
    return aredis.StrictRedis(
        connection_pool=redis_pool,
        decode_responses=True,  # 自动解码
    )


class TaskModel():
    def __init__(self, *args, **kwargs):
        self.redis_client = aredis_cli()

    async def push(self, semaphore, site, type, value):
        async with semaphore:
            await self.redis_client.lpush('{}_{}'.format(site, type), value)


if __name__ == '__main__':

    # file = 'hr58.txt'
    site = 'job58'

    # area = [159, 160, 161, 162, 163, 165, 166, 167, 168, 169, 170, 171, 1913, 8000, 15298]
    url = 'https://wh.58.com/yewu/pn{}/'
    # area = [159]

    def gene(to_fill):
        task = {'site': site, 'type': 2, 'url': to_fill}
        return json.dumps(task, ensure_ascii=False)


    loop = asyncio.get_event_loop()
    t = TaskModel().push
    semaphore = asyncio.Semaphore(500)
    task = [asyncio.ensure_future(t(semaphore, site, type=2, value=gene(url.format(i)))) for i in range(70)]
    start = time.time()
    loop.run_until_complete(asyncio.wait(task))
    endtime = time.time() - start
    print(endtime)
    loop.close()

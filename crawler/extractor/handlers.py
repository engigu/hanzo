import json
import os, sys, traceback
from copy import deepcopy

sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import logging

from core.func import load_module
from core.exceptions import *
from core.asredis import AsRedis
from bloom.connection import BFR as bfr
from mongo_operate import mongo_ur
from config import *

EXTRACT_LIST = load_module('lists', __file__, "List_")
EXTRACT_RESUME = load_module("resumes", __file__, "Resume_")

ards = AsRedis(REDIS_HOST, REDIS_PORT, REDIS_DB)


async def handler(msg: dict):
    # rabbitmq  消息格式：Str '{"site": "cccc", "type: 1, "content": "content.....", "curr_task": "yyyyy"}'
    l = logging
    site = msg['site']
    _res = {"site": site, "content": msg['content'], "curr_task": msg['curr_task']}

    if msg['type'] in [1, 3, 4]:
        # list_parser = DISPATCH_KEY_MAP.get(site)['list_parser']
        list_parser = EXTRACT_LIST.get(site, None)
        if not list_parser:
            raise ListParseDoNotExists(f'site: {site} has no corresponding list parser.')
        try:
            detail = list_parser().parser(msg['content'])
            detail_list = detail['resume_list']
            current_page = detail['current_page']
            last_page = detail['last_page']
            for one in detail_list:
                l.info(f"site: {site} parse list one res: {str(one)} ")
                hash_key = one.get("hashed_key", 0)
                if bfr.is_exists(hash_key):  # todo 布隆list过滤
                    l.info(f"site: {site} task has crawled before, skip. task: {str(one)}")
                    continue
                data = json.dumps({
                    'type': 2,
                    'site': site,
                    'url': one['url'],
                    'origin_task': msg['curr_task'],
                }, ensure_ascii=False)
                await ards.push('%s_2' % site, data)
                l.info(f'site: {site} has generated new type2 task: {data}, pushed successfully.')
            if last_page > current_page:
                next_page_task = deepcopy(msg['curr_task'])
                next_page_task['page'] += 1
                next_page_task['origin_task'] = msg['curr_task']
                next_page_task['type'] = 3
                task_data = json.dumps(next_page_task, ensure_ascii=False)
                '''
                    1: 'import task',
                    2: 'parse to type2',
                    3: 'parse to type1',
                    4: 'parse type1 error',
                    5: 'parse type2 error'
                '''
                if msg['type'] != 4:
                    # 这个条件主要是防止之前失败的任务一直重复生成新的翻页type1
                    await ards.push('%s_3' % site, task_data)
                    l.info(f'site: {site} has generated new type1 queue. task: {next_page_task}, pushed successfully.')
        except Exception as e:
            _curr_task = msg['curr_task']
            _curr_task['type'] = 4
            failed_type1_task = json.dumps(_curr_task, ensure_ascii=False)
            await ards.push('%s_4' % site, failed_type1_task)
            l.info(f'site: {site} parse list Error, has pushed to type4 queue. task: {failed_type1_task}, error: '
                   f'{e.__context__}, tb: {traceback.format_exc()}')

    elif msg['type'] in [2, 5]:
        # detail_parser = DISPATCH_KEY_MAP.get(site)['resume_parser']
        detail_parser = EXTRACT_RESUME.get(site, None)
        if not detail_parser:
            raise DetailParseDoNotExists(f'site: {site} has no corresponding detail parser.')
        try:
            detail = detail_parser().auto_html_to_dict(_res)
            l.info(f"site: {site} detail parse res: {str(detail)}")
            if not detail:
                _curr_task = msg['curr_task']
                _curr_task['type'] = 5  # type2 解析失败放回失败队列
                failed_type2_task = json.dumps(_curr_task, ensure_ascii=False)
                await ards.push('%s_5' % site, failed_type2_task)
                l.info(f"site: {site} parse resume None, has pushed to type5 queue, task: {str(_curr_task)}")
                return
            # todo insert mongo
            # resume计算去重
            mongo_ur(detail)  # todo 测试一下

        except Exception as e:
            _curr_task = msg['curr_task']
            _curr_task['type'] = 5  # type2 解析失败放回失败队列
            failed_type2_task = json.dumps(_curr_task, ensure_ascii=False)
            await ards.push('%s_5' % site, failed_type2_task)
            l.error(f"site: {site} parse resume Error, has pushed to type5 queue, task: {str(_curr_task)}, "
                    f"error: {e.__context__}, tb: {traceback.format_exc()}")

    else:
        raise Exception(f'parser type: {msg["type"]} error!')


if __name__ == '__main__':
    print(EXTRACT_LIST)
    print(EXTRACT_RESUME)
    # print(DISPATCH_KEY_MAP)
    pass
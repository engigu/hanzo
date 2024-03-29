import time

import hashlib
import json
from core.mongo_db import MongoDb
from core.func import mongo_time_count
from core.asredis import NoAsRedis
# import logging
from config import *
from copy import deepcopy

MT_cp = MongoDb("aizhaopin", "company_infos")
MT_photo = MongoDb("aizhaopin", "baidu_photos")
cards = NoAsRedis(C_REDIS_HOST, C_REDIS_PORT, C_REDIS_DB)


def resume_develop(resume):
    hashed_key = hashlib.md5(
        json.dumps(resume, sort_keys=True, ensure_ascii=False).encode('utf8')).hexdigest()[8:-10]
    hashed_id = int(hashed_key, 16)
    return hashed_id


def compare_develops(old_develop, new_develop):
    """
    :param old_develop: [{"create_time": 140101111,
                           "invest": "A轮",
                           "invest_money": "千万人民币",
                           "invest_organ": ['aa投资','bb投资'],
                           "scale": "0-50",
                           "state": 1,
                           "update_time": 140101111}]
    :param new_develop: ...
    :return: 保留并集 重复的取最新的update的一项
    """
    res_list = []
    for i, n in enumerate(deepcopy(old_develop)):
        n.pop("update_time")
        match_status = False
        for j, m in enumerate(deepcopy(new_develop)):
            m.pop("update_time")
            if resume_develop(n) == resume_develop(m):
                res_list.append(new_develop[j])
                match_status = True
                break
        if not match_status:
            res_list.append(old_develop[i])
    res_list = res_list + [i for i in new_develop if i not in res_list]
    return res_list


@mongo_time_count('jx_resume_id')
def company_update_func(resume, logger):
    l = logger
    res = MT_cp.search({"jx_resume_id": resume["jx_resume_id"]})
    # st = time.time()
    if not res:
        MT_cp.insert(resume)
        cards.incr(f'{resume["source"]}_{time.strftime("%Y-%m-%d", time.localtime())}')
        cards.incr(f'{resume["source"]}_total')
        l.info(f"inserted jx_resume_id: {resume['jx_resume_id']}")
    else:
        develop_old = res.get("develops", [])
        develop_new = resume.get("develops", [])  # 2019-6-11 修改develop的更新逻辑
        all_develops = compare_develops(develop_old, develop_new)
        resume["develops"] = all_develops
        # deep_old = deepcopy(develop_old)[-1]
        # deep_new = deepcopy(develop_new)[0]
        # deep_old.pop("update_time")
        # deep_new.pop("update_time")
        # if resume_develop(deep_old) != resume_develop(deep_new):
        #     resume["develops"] = develop_old + develop_new
        # else:
        #     develop_old[-1]["update_time"] = develop_new[0]["update_time"]
        #     resume["develops"] = develop_old
        MT_cp.update({"jx_resume_id": resume["jx_resume_id"]}, resume)
        cards.incr(f'{resume["source"]}_{time.strftime("%Y-%m-%d", time.localtime())}')
        l.info(f"updated jx_resume_id: {resume['jx_resume_id']}")
    # l.info(f"jx_resume_id: {resume['jx_resume_id']}, "
    #        f"mongo operate cost {(time.time() - st):.3f} s.")


@mongo_time_count('full_name')
def save_photo(resume, logger):
    l = logger
    full_name = resume.get("full_name")
    res = MT_photo.search({"full_name": full_name})
    # st = time.time()
    if not res:
        MT_photo.insert(resume)
        cards.incr(f'{resume["source"]}_{time.strftime("%Y-%m-%d", time.localtime())}')
        cards.incr(f'{resume["source"]}_total')
        l.info(f"inserted full_name: {full_name}")
    else:
        MT_photo.update({"full_name": full_name}, resume)
        l.info(f"update full_name: {full_name}")
        cards.incr(f'{resume["source"]}_{time.strftime("%Y-%m-%d", time.localtime())}')
    # l.info(f"full_name: {full_name}, "
    #        f"mongo operate cost {(time.time() - st):.3f} s.")


@mongo_time_count('jx_resume_id')
def test_mode_mongo(resume, logger):
    logger.info(f"resume: {str(resume)}")


def mongo_ur(resume: dict, mode: str, logger):
    if mode == 'online':
        source = resume.get("source", None)

        if source in range(200, 300):
            company_update_func(resume, logger)
        elif source == 303:  # company_photo
            save_photo(resume, logger)
        else:
            raise Exception(f"source num: {source} wrong: {resume}")
    else:
        logger.info(f"mongo run mode: {mode}, resume: {str(resume)}")
        test_mode_mongo(resume, logger)


if __name__ == '__main__':
    mongo_ur('xxx')

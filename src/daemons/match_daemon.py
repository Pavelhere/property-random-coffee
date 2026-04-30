# -*- coding: utf-8 -*-

import time

from loguru import logger

from utils import config as cfg_utils
from services.matching import MatchingService


def care(config, user_repo, meet_repo, metadata_repo, email_client):
    matcher = MatchingService(config, user_repo, meet_repo, metadata_repo, email_client)
    pool_period = config["daemons"]["week"]["poolPeriod"]

    while True:
        weekday, _ = cfg_utils.get_week_info(config)

        if weekday == 1:
            result = matcher.generate_matches()
            logger.info("Weekly matcher result: %s", result)

        time.sleep(pool_period)

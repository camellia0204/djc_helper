import json
import os.path
from datetime import timedelta
from typing import List, Optional

from const import downloads_dir
from data_struct import ConfigInterface, to_raw_type
from download import download_github_raw_content
from first_run import is_daily_first_run, is_first_run, is_monthly_first_run, is_weekly_first_run, reset_first_run
from log import logger
from update import version_less
from util import format_now, format_time, get_now, is_windows, message_box, parse_time, try_except
from version import now_version

if is_windows():
    import win32con


class NoticeShowType:
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALWAYS = "always"
    DEPRECATED = "deprecated"


valid_notice_show_type = {val for attr, val in NoticeShowType.__dict__.items() if not attr.startswith("__")}


class Notice(ConfigInterface):
    def __init__(self):
        self.sender = "风之凌殇"
        self.title = "测试消息标题"
        self.message = "测试消息内容"
        self.send_at = "2021-05-11 00:00:00"
        self.show_type = NoticeShowType.ONCE
        self.open_url = ""  # 若填入，在展示对应公告时会弹出该网页
        self.expire_at = "2121-05-11 00:00:00"
        self.show_only_before_version = now_version  # 若填入，则仅在对应版本前才会展示

    def __lt__(self, other):
        return parse_time(self.send_at) < parse_time(other.send_at)

    def need_show(self) -> bool:
        key = self.get_first_run_key()

        # 判断是否过期
        if get_now() > parse_time(self.expire_at):
            return False

        # 判断是否满足版本需求
        if self.show_only_before_version != "" and not version_less(now_version, self.show_only_before_version):
            return False

        # 根据显示类型判断
        if self.show_type == NoticeShowType.ONCE:
            return is_first_run(key)
        elif self.show_type == NoticeShowType.DAILY:
            return is_daily_first_run(key)
        elif self.show_type == NoticeShowType.WEEKLY:
            return is_weekly_first_run(key)
        elif self.show_type == NoticeShowType.MONTHLY:
            return is_monthly_first_run(key)
        elif self.show_type == NoticeShowType.ALWAYS:
            return True
        elif self.show_type == NoticeShowType.DEPRECATED:
            return False
        else:
            return False

    def reset_first_run(self):
        reset_first_run(self.get_first_run_key())

    def get_first_run_key(self) -> str:
        return f"notice_need_show_{self.title}_{self.send_at}"


class NoticeManager:
    def __init__(self, load_from_remote=True):
        self.notices: List[Notice] = []

        self.file_name = "notices.txt"
        self.cache_path = f"{downloads_dir}/{self.file_name}"
        self.save_path = f"utils/{self.file_name}"

        self.load(load_from_remote)

    @try_except()
    def load(self, from_remote=True):
        if from_remote:
            path = self.cache_path
            # 下载最新公告
            self.download_latest_notices()
        else:
            path = self.save_path

        if not os.path.isfile(path):
            return

        # 读取公告
        with open(path, encoding="utf-8") as save_file:
            for raw_notice in json.load(save_file):
                notice = Notice().auto_update_config(raw_notice)
                self.notices.append(notice)

        self.notices = sorted(self.notices)
        logger.info("公告读取完毕")

    def download_latest_notices(self):
        dirpath = os.path.dirname(self.cache_path)
        download_github_raw_content(self.save_path, dirpath)

    @try_except()
    def save(self):
        # 本地存盘
        with open(self.save_path, "w", encoding="utf-8") as save_file:
            json.dump(to_raw_type(self.notices), save_file, ensure_ascii=False, indent=2)
            logger.info("公告存盘完毕")

        logger.warning("稍后请自行提交修改后的公告到github")

    @try_except()
    def show_notices(self):
        valid_notices = list(filter(lambda notice: notice.need_show(), self.notices))

        logger.info(f"发现 {len(valid_notices)} 个新公告")
        for idx, notice in enumerate(valid_notices):
            # 展示公告
            message_box(
                notice.message,
                f"公告({idx + 1}/{len(valid_notices)}) - {notice.title}",
                icon=win32con.MB_ICONINFORMATION,
                open_url=notice.open_url,
                follow_flag_file=False,
            )

        logger.info("所有需要展示的公告均已展示完毕")

    def add_notice(
        self,
        title,
        message,
        sender="风之凌殇",
        send_at: str = "",
        show_type=NoticeShowType.ONCE,
        open_url="",
        valid_duration: Optional[timedelta] = None,
        show_only_before_version="",
    ):
        send_at = send_at or format_now()
        valid_duration = valid_duration or timedelta(days=7)

        if show_type not in valid_notice_show_type:
            logger.error(f"无效的show_type={show_type}，有效值为{valid_notice_show_type}")
            return

        for old_notice in self.notices:
            if old_notice.title == title and old_notice.message == message and old_notice.sender == sender:
                logger.error(f"发现内容完全一致的公告，请确定是否是误操作，若非误操作请去文本直接修改。\n{old_notice}")
                return

        notice = Notice()
        notice.title = title
        notice.message = message
        notice.sender = sender
        notice.send_at = send_at
        notice.show_type = show_type
        notice.open_url = open_url
        notice.expire_at = format_time(get_now() + valid_duration)
        notice.show_only_before_version = show_only_before_version

        self.notices.append(notice)
        logger.info(f"添加公告：{notice}")


def main():
    # 初始化
    nm = NoticeManager(load_from_remote=False)

    # note: 在这里添加公告
    title = "活动周期说明-v3"
    message = """最近不少朋友又再问为啥领不到东西，可能没注意到上次的公告，这里再发一次-。-

也许你会注意到最近蚊子腿领的比较少，这是很正常的=、=下面我介绍下DNF的蚊子腿活动的周期
一般在每年的春节套、五一套、周年庆、国庆套这几个大版本时间点，会出比较多的蚊子腿活动，比如集合站、wegame、qq视频、集卡、心悦等，而在这些时间点之间，有时候会啥活动也不出，连着一两个月都没有啥东西

按照往年经验，基本可以确定，在9.22（国庆套版本）之前是不会有啥活动了

-------------------

前段时间特地还在colg发过一个统计帖，统计了2020.8至今的活动分布，可以发现每年的7月到9月22号之前，都是基本没啥活动的-。-
有兴趣的朋友可以看看那个帖子： https://bbs.colg.cn/thread-8551016-1-1.html

另外说下现在还有的活动:
1. 道聚城（迷你蚊子腿，几乎可以忽略）
2. 心悦特权专区（做任务获取成就点来兑换道具，充钱获取勇士币来兑换道具，以及每周每月的礼包）
3. 心悦app（每日10个雷米，5个复活币，3个霸王契约，需抓包配置心悦app请求包）
4. 黑钻礼包（每月的迷你蚊子腿）
5. 腾讯游戏信用礼包（每月的迷你蚊子腿）
6. 小酱油（周礼包的变大药水和每年一次的生日礼包）
7. DNF助手编年史（目前常驻的助手活动，每达到新的等级可以领取新的东西，需要配置助手token等参数，目前只能抓包获取）
8. DNF马杰洛的规划（不手动参与拉回流几乎领不到啥）
9. 超级会员（一次性见面奖励，此外买会员可以兑换东西）
10. qq视频-爱玩（一次性见面奖励，此外买会员可以兑换东西）

其中上面的又可以细分为

每日可以领到的：
1. 心悦app

隔几日就能领到的：
1. DNF助手编年史（升级时）
2. 心悦特权专区

每周可以领到的
1. 道聚城
2. 小酱油
3. 心悦特权专区

每月可以领到的
1. 心悦特权专区
2. 黑钻礼包
3. 腾讯游戏信用礼包

一次性活动
1. 超级会员
2. qq视频-爱玩
"""
    open_url = ""
    show_only_before_version = ""

    if title != "":
        nm.add_notice(
            title,
            message,
            send_at=format_now(),
            show_type=NoticeShowType.ONCE,
            open_url=open_url,
            valid_duration=timedelta(days=7),
            show_only_before_version=show_only_before_version,
        )

    nm.save()


def test():
    nm = NoticeManager(load_from_remote=True)

    for notice in nm.notices:
        notice.reset_first_run()
        notice.show_only_before_version = ""

    logger.info("测试环境已重置完毕，所有公告都已改为未展示状态，且关闭版本限制")

    nm.show_notices()

    os.system("PAUSE")


if __name__ == "__main__":
    TEST = False
    from util import bypass_proxy

    bypass_proxy()

    if not TEST:
        main()
    else:
        test()

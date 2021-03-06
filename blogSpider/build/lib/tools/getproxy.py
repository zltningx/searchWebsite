import sqlite3
import requests
import sys

from scrapy.selector import Selector
from concurrent.futures import ThreadPoolExecutor

# speed of proxy server
MAX_LOAD = 3.0  # sec


def crawl_page_xici(i, sql_manager):
    """
    :param i:  page number 1, 2, 3 .etc
    :return:
    """
    ip_lists = list()
    headers = {
        "User-Agent": "User-Agent:Mozilla/5.0(Macintosh;U;IntelMacOSX10_6_8;en\
        -us)AppleWebKit/534.50(KHTML,likeGecko)Version/5.1Safari/534.50"
    }
    res = requests.get("http://www.xicidaili.com/wt/{}".format(i), headers=headers)
    selector = Selector(text=res.text)
    page_ips = selector.css("#ip_list tr")
    for ip_detail in page_ips[1:]:
        td_list = ip_detail.css("td::text").extract()
        location = ip_detail.css("a::text").extract_first()
        if not location:
            location = ''
        speed = float(ip_detail.css(".bar::attr(title)").extract_first().strip('秒'))
        if speed < MAX_LOAD:
            # td_list[0] == host, td_list[1] == port, td_list[4] == proxy_type,
            # td_list[5] == protocol
            if not location:
                # when location is empty.
                td_list[5] = td_list[4]
                td_list[4] = td_list[3]
            if td_list[0] and td_list[1]:
                ip_lists.append((td_list[0], int(td_list[1]),
                                 td_list[4], td_list[5], location, speed))
    return ip_lists


def crawl_page_kuaidaili(i, sql_manager):
    """
    :param i:  page number 1, 2, 3 .etc
    :return:
    """
    ip_lists = list()
    headers = {
        "User-Agent": "User-Agent:Mozilla/5.0(Macintosh;U;IntelMacOSX10_6_8;en\
        -us)AppleWebKit/534.50(KHTML,likeGecko)Version/5.1Safari/534.50"
    }
    res = requests.get("https://www.kuaidaili.com/free/inha/{}".format(i), headers=headers)
    selector = Selector(text=res.text)
    page_ips = selector.css("tbody")
    for ip_detail in page_ips:
        td_list = ip_detail.css("td::text").extract()
        speed = float(td_list[5].strip('秒'))
        if speed <= MAX_LOAD:
            ip_lists.append((td_list[0], int(td_list[1]),
                            td_list[2], td_list[3], td_list[4], speed))

    return ip_lists


class SqlManager(object):
    def __init__(self):
        self.conn = sqlite3.connect("proxy.db")
        self.c = self.conn.cursor()

    def _create_table(self):
        # create only one
        self.c.execute("""CREATE TABLE ip (
                              host TEXT NOT NULL PRIMARY KEY,
                              port INTEGER NOT NULL,
                              proxy_type TEXT,
                              protocol TEXT,
                              location TEXT,
                              speed REAL
                              )""")
        self.conn.commit()

    def insert_one(self, value):
        if not isinstance(value, tuple):
            raise ValueError("value must be a tuple")
        try:
            self.c.execute("INSERT INTO ip VALUES (?,?,?,?,?,?)", value)
            self.conn.commit()
        except Exception as e:
            print(e, "when insert one")

    def insert_many(self, value_list):
        try:
            if not isinstance(value_list[0], tuple):
                raise ValueError("value must be a tuple")
        except Exception as e:
            print(e, "when insert many")
        # self.c.executemany("INSERT INTO ip VALUES (?,?,?,?,?,?)", value_list)
        for value in value_list:
            try:
                self.c.execute("INSERT INTO ip VALUES (?,?,?,?,?,?)", value)
            except Exception as e:
                pass
        self.conn.commit()

    def random_fetcher(self, num):
        self.c.execute("SELECT * FROM ip ORDER BY RANDOM() limit {}".format(num))
        return self.c.fetchall()

    def do_clean(self):
        self.c.execute("DELETE FROM ip")
        self.conn.commit()

    def do_delete(self, host):
        self.c.execute("DELETE FROM ip WHERE host='{}'".format(host))

    def do_exit(self):
        self.conn.close()


def get_proxy_ips(sql_manager):
    with ThreadPoolExecutor(30) as Executor:
        for i in range(1, 1000):
            future = Executor.submit(crawl_page_kuaidaili, i, sql_manager)
            sql_manager.insert_many(future.result())


class IpManager(SqlManager):
    def __init__(self):
        super().__init__()

    def create(self):
        self._create_table()

    def clean(self):
        self.do_clean()

    def crawl(self):
        get_proxy_ips(self)

    def judge(self, host, port):
        http_url = "www.freebuf.com"
        proxy_url = "https://{}:{}".format(host, port)
        try:
            proxy_dict = {
                "http": proxy_url
            }
            res = requests.get(http_url, proxies=proxy_dict)
        except Exception as e:
            print("invalid ip")
            self.do_delete(host)
            return False
        else:
            code = res.status_code
            if (code >= 200) and (code < 300):
                print("effective ip")
                return True
            else:
                print("invalid ip")
                self.do_delete(host)
                return False

    def random(self):
        raw_ip = self.random_fetcher(1)
        if raw_ip:
            return raw_ip[0][0] + ":" + str(raw_ip[0][1])

    def exit(self):
        self.do_exit()

if __name__ == "__main__":
    ip = IpManager()
    if len(sys.argv) == 2:
        command = sys.argv[1]
        if command == 'init':
            ip.create()
    ip.crawl()
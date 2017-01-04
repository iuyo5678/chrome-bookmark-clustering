#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Time-stamp: <2017-01-04 17:20:21 Wednesday by wls81>

# @version 1.0
# @author zhangguhua

from Queue import Queue
import threading
import time
import requests

headers = {'user-agent': 'Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
timeout = 10
max_retry = 3


class ParallelDownload(threading.Thread):
    def __init__(self, thread_id, in_queue, out_queue):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.in_queue = in_queue
        self.out_queue = out_queue

    def run(self):
        while self.in_queue.qsize() > 0:
            item = self.in_queue.get()
            serial_num = item[0]
            item_url = item[1][0]
            print "Thread: {0} start_crawl：{1}".format(self.thread_id, item_url.encode("utf-8"))
            result = download_page_content(item_url)
            print "Thread: {0} end_crawl：{1}".format(self.thread_id, item_url.encode("utf-8"))

            self.out_queue.put((serial_num, result))
    

def download_page_content(url, proxies=None):
    """
    """
    try_numner = 1
    status_code = 404
    while try_numner <= max_retry:
        try:
            if not proxies:
                response = requests.get(url, timeout=timeout, headers=headers)
            else:
                response = requests.get(url, proxies=proxies, timeout=timeout, headers=headers)
            status_code = response.status_code
        except:
            print "The {0} fetch {1} failed.".format(try_numner, url.encode("utf-8"))
        if status_code != 200:
            try_numner += 1
        else:
            break
    if status_code == 200:
        # 判断页面的的编码，有些不标准的页面，request解码bug
        if response.encoding == "ISO-8859-1":
            response.encoding = response.apparent_encoding
        return response.text
    else:
        return None



if __name__ == "__main__":
    in_queue = Queue()

    out_queue = Queue()

    in_queue.put((1, ["http://www.baidu.com", "baidu"]))
    in_queue.put((1, ["http://www.sina.com", "sina"]))
    in_queue.put((1, ["http://www.163.com", "163"]))
    for i in range(2):
        downloader = ParallelDownload("test" + str(i), in_queue, out_queue)
        downloader.daemon = True
        downloader.start()

    while threading.activeCount() > 1:
        print threading.activeCount()
        time.sleep(1)

    
    while out_queue.qsize() > 0:
        item = out_queue.get()
        print out_queue.qsize()
    

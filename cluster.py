
# coding: utf-8

# In[1]:

#!/usr/bin/env python


# Time-stamp: <2016-12-21 12:03:37 Wednesday by wls81>

import sys
import re
import pickle
import os 
import hashlib
import argparse
from collections import defaultdict

import requests
import jieba
import jieba.analyse

from bs4 import BeautifulSoup as bf

headers = {'user-agent': 'Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
cluster_result = {}
timeout = 40
max_retry = 3

def get_bookmarks(bookmark_content):
    """
    """
    relink = '<A HREF="(\S*)"\s.*>(.*)</A>'
    bookmarks = re.findall(relink, bookmark_content)
    print "共计获得书签：%d 条" % len(bookmarks)
    raw_result = []
    for item in bookmarks:
        bm_info = list(item)
        bm_info.append(0)
        raw_result.append(bm_info)
    return raw_result

def download_page_content(url, proxies=None):
    """
    """
    try_numner = 1
    status_code = 404
    print "开始爬取网页：%s" %url
    while try_numner <= max_retry:
        try:
            if not proxies:
                response = requests.get(url, timeout=timeout, headers=headers)
            else:
                response = requests.get(url, proxies=proxies, timeout=timeout, headers=headers)
            status_code = response.status_code
        except:
            print "第 %d 次抓取失败" % try_numner
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

def collect_page_content(bookmarks, data_path):
    """
    """
    for i , bookmark in enumerate(bookmarks):
        # 如果已经下载了页面，就直接加载结果
        if os.path.isfile(data_path +'/' + str(i)):
            temp_file = open(data_path +'/' + str(i))
            bookmarks[i] = pickle.load(temp_file)
            continue
        # chrome 内部url和本地文件直接聚一类，不参与计算了
        if bookmark[0].startswith("chrome:") or bookmark[0].startswith("file:"):
            bookmarks[i][2] = -1
            temp_file = open(data_path +'/' + str(i), 'wb')
            ss = pickle.dump(bookmarks[i], temp_file)
            continue
        # 没有下载的，http的下载页面，并且保存结果
        page_content = download_page_content(bookmark[0])
        if page_content:
            bookmarks[i][2] = 0
            bookmarks[i].append(page_content)
        else:
            bookmarks[i][2] = -2
            # 结果保存到文件夹中
        temp_file = open(data_path +'/' + str(i), 'wb')
        ss = pickle.dump(bookmarks[i], temp_file)
        
    return bookmarks

def add_tags(bookmarks, topK=20):
    """
    """
    for i , bookmark in enumerate(bookmarks):
        if bookmark[2] == 0:
            content = bookmark[4]
            
            bookmark_tag_word = jieba.analyse.textrank(content, topK, withWeight=False, allowPOS=('ns', 'n', 'vn', 'v'))
            if len(bookmark_tag_word) == 0:
                bookmark_tag_word = jieba.analyse.extract_tags(content, topK)
            
            bookmarks[i].append(bookmark_tag_word)

    return bookmarks

def extract_text(bookmarks):
    """
    """
    for i , bookmark in enumerate(bookmarks):
        if bookmark[2] == 0:
            bsoup = bf(bookmark[3], "html5lib")
            # 过滤掉页面中的js和css
            for script in bsoup(["script", "style"]):
                script.extract()
                
            bookmark_text = " ".join(bsoup.stripped_strings)
            bookmarks[i].append(bookmark_text)
    return bookmarks

def unvlaid_data(x):
    """
    切词前过滤掉无效字段,这里仅过滤了纯数字
    """
    return not x.isdigit()

def cut_word(bookmarks_result):
    """
    对文章进行切词
    """
    bookmark_corpus = list()
    map_dict = dict()
    index = 0
    for i, bookmark in enumerate(bookmarks_result):
        if bookmark[2] >= 0:
            map_dict[index] = i
            seg_list = jieba.cut(bookmark[4], cut_all=True) 
            bookmark_corpus.append("  ".join(filter(unvlaid_data, seg_list)))
            index += 1
    print "抽取到有效文章%d" % len(bookmark_corpus)
    return map_dict, bookmark_corpus

def extract_features(bookmark_corpus, debug_mode=False):
    """
    抽取特征
    """
    from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
    transformer = TfidfTransformer(smooth_idf=False)
    # 最大选10000个词作为特征词
    vectorizer = CountVectorizer(min_df=1, max_features=10000)
    
    # 不限制特征词数量
    #vectorizer = CountVectorizer(min_df=1)
    
    # word bag 特征向量
    #feature_matrix = vectorizer.fit_transform(bookmark_corpus)
    
    # tf-idf 特征向量
    feature_matrix = transformer.fit_transform(vectorizer.fit_transform(bookmark_corpus))

    print "计算完成文章的特征向量"
    return feature_matrix

def hierarchical_clustering(feature_matrix, kvalue, debug_mode=False):
    """
    层次聚类
    """
    from sklearn.cluster import AgglomerativeClustering
    clustering = AgglomerativeClustering(linkage='ward', n_clusters=kvalue).fit(feature_matrix.toarray())
    clustering_result = clustering.labels_
    if debug_mode:
        print "hierarchical_clustering result:"
        print "------------------------------------------------------------------------------------"
        print clustering_result
    return clustering_result

def kmeans_clustering(feature_matrix, kvalue, debug_mode=False):
    """
    """
    # kmeans-聚类
    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=kvalue, random_state=0).fit(feature_matrix)
    clustering_result = kmeans.labels_
    if debug_mode:
        print "kmeans_clustering result:"
        print "------------------------------------------------------------------------------------"
        print clustering_result
    return clustering_result


def calu_cluster_name(cluster_content, key, topK=3):
    # 计算簇的特征词
    if key == "-1":
        return u"local file"
    if key == "-2":
        return u"cann't open page"
    content = cluster_content.get(key, "")
    full_content = " ".join(content)
    tag_words = jieba.analyse.extract_tags(full_content, topK, allowPOS=('ns', 'n', 'vn', 'v'))
    if len(tag_words) == 0:
        tag_words = jieba.analyse.extract_tags(full_content, topK)

    return "-".join(tag_words)

# 将聚簇结果标记写入数据
def write_mark(bookmarks_result,clustering_result, map_dict):
    for index, label in enumerate(clustering_result):
        bookmark_index = map_dict[index]
        bookmarks_result[bookmark_index][2] = label
        result = defaultdict(list)
        cluster_content = defaultdict(list)
        for item in bookmarks_result:
            key = str(item[2])
            result[key].append(item[1])
            if int(item[2]) >= 0:
                cluster_content[key].append(item[4].lower())
    return result, cluster_content

# 输出结果
def print_result(result, cluster_content):
    for k,v in result.iteritems(): 
        print k, calu_cluster_name(cluster_content, k)
        print "/*************************************************************************************/"
        for value in v:
            print value
        print "/*************************************************************************************/"
        print ""
    

def main(args):
    # 打开导出的书签文件
    bookmark_file = open(args.file)
    bookmark_content = bookmark_file.read()
    m = hashlib.new('ripemd160')
    m.update(bookmark_content)
    bookmark_md5 = m.hexdigest()
    data_path = os.path.dirname(os.path.abspath(__file__)) + '/data/' + str(bookmark_md5)
    if not os.path.exists(data_path):
        os.mkdir(data_path) 
    bookmarks = get_bookmarks(bookmark_content)
    # 下载或是从保存记录中加载所有的页面数据
    bookmarks_result = collect_page_content(bookmarks, data_path)
    print  "抽取页面的内容"
    bookmarks_result = extract_text(bookmarks_result)
    # 提取文章的关键词，这一步可以省略
    bookmarks_result = add_tags(bookmarks_result)
    if not args.kvalue:
        args.kvalue = int(len(bookmarks_result)/20 + 1)

    ks_result = extract_text(bookmarks_result)
    # 提取文章的关键词，这一步可以省略,其实没有任何用
    #bookmarks_result = add_tags(bookmarks_result)

    print "数据准备结束"

    map_dict, bookmark_corpus = cut_word(bookmarks_result)
    feature_matrix = extract_features(bookmark_corpus, args.debug)
    if args.method == "kmeans":
        clustering_result = kmeans_clustering(feature_matrix, args.kvalue, args.debug)
    else:
        clustering_result = hierarchical_clustering(feature_matrix, args.kvalue, args.debug)
    result, cluster_content = write_mark(bookmarks_result,clustering_result, map_dict)
    print_result(result, cluster_content)


parser = argparse.ArgumentParser(description='chrome 书签自动分类工具')
parser.add_argument("-k", "--kvalue", type=int, help="聚簇的个数，将书签分为多少个簇")
parser.add_argument('-m', "--method", choices=['hierarchical', 'kmeans'], required=True,  
                    help='选择聚类方法只有两种可选，kmeans和hierarchical')
parser.add_argument("-f", "--file", required=True,
                    help="书签文件的路径")
parser.add_argument("-d", "--debug",action='store_false', default=False, help="开启调试模式")
parser.add_argument("-p", "--proxy",help="页面抓取时使用代理")

args = parser.parse_args()
main(args)

#!/usr/bin/env python

# Scrape.py
# Scrape mobygames.com for team sizes to compare over time and by game engine
# Once mobygames releases their API, this will all be deprecated

import codecs, json, sys
import sqlite3

def game_row_generator(httpCache):
    for url in httpCache:
        if '/game/' in url:
            yield (url,httpCache[url])

def developer_row_generator(httpCache):
    baseUrl = 'http://www.mobygames.com/developer/sheet/view/developerId,'
    for url in httpCache:
        if  baseUrl in url:
            yield (url[len(baseUrl):-1], httpCache[url])

def main():
    with open('http_cache.json') as data_file:
        httpCache = json.load(data_file)

    with sqlite3.connect('http_cache.db') as conn:
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS games")
        c.execute("DROP TABLE IF EXISTS developers")
        c.execute("CREATE TABLE games (url text, contents text)")
        c.execute("CREATE TABLE developers (id text, contents text)")
        c.execute("CREATE UNIQUE INDEX game_index ON games (url)")
        c.execute("CREATE UNIQUE INDEX developer_index ON developers (id)")

        c.executemany("insert into games(url,contents) values (?,?)", game_row_generator(httpCache))
        c.executemany("insert into developers(id,contents) values (?,?)", developer_row_generator(httpCache))
        conn.commit()                


if __name__=="__main__":
    main()



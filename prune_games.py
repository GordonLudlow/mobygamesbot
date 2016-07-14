#!/usr/bin/env python

# prune_games.py
# Add an ignore field to games that are for old systems, handheld or mobile

import codecs, HTMLParser, json, robotparser, sys, time, urllib2
import string
import sqlite3
from scrape import RobotsTxtParser, CacheUrl, GetContent

userAgent = 'Moby Games Bot (https://github.com/GordonLudlow/mobygamesbot)'
lastPageRequestTime = time.time()

class GamePageParser(HTMLParser.HTMLParser):
    def __init__(self):
        self.platformBlock = False
        self.platform = []
        self.platformCount = 0
        self.genreBlock = False
        self.foundFirstGenre = True        
        self.inATag = False
        self.uninterestingCharacters = set(string.punctuation+string.whitespace)
        
        HTMLParser.HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.inATag = True
            if self.platformBlock:
                self.platform.append('')
                #print 'appending empty string'
                
    def handle_endtag(self, tag):
        if tag == 'a':
            self.inATag = False
            if self.platformBlock:
                self.platformCount = self.platformCount + 1
                #print 'incrementing plaform count'
            if self.genreBlock:
                self.foundFirstGenre = True                
        if tag == 'div':
            if self.platform:
                self.platformBlock = False
            if self.foundFirstGenre:
                self.genreBlock = False
                self.foundFirstGenre = False   

    def handle_data(self, data):
        if not self.platform and not self.inATag and (data == 'Platform' or data == 'Platforms'):
            self.platformBlock = True
        elif self.platformBlock and not all(c in self.uninterestingCharacters for c in data):
            #print 'processing platform data, self.platformCount=%d' % self.platformCount
            #print 'self.platform = ', self.platform
            #print 'data="%s"' % data
            if self.platform[self.platformCount]:
                self.platform[self.platformCount] = self.platform[self.platformCount] + ' '
            self.platform[self.platformCount] = self.platform[self.platformCount] + data
        elif data == "Genre":
            self.genreBlock = True
            self.genre = ''
        elif self.genreBlock:
            if self.genre:
                self.genre = self.genre + ' '
            self.genre = self.genre + data         

def main(inFile, outFile):
    robot = RobotsTxtParser('http://www.mobygames.com/robots.txt')
    robot.read()

    with open(inFile) as data_file:
        input = json.load(data_file)

    with open('platform.json') as platform_file:
        platform = json.load(platform_file)

    with codecs.open(outFile, encoding='utf-8-sig', mode='w+') as output, sqlite3.connect('http_cache.db') as conn:

        httpCache = conn.cursor()

        for game in input:
            if 'ignore' in game:
                continue
            print game['game']
            gameContent = GetContent(game['credits'], httpCache, robot)
            gameParser = GamePageParser()
            gameParser.feed(gameContent)
            print gameParser.platform
            gamePlatforms = set([platform[x] for x in gameParser.platform])
            print gamePlatforms
            if len(gamePlatforms) == 0:
                print 'No platform????'
                exit(1)
            elif len(gamePlatforms) == 1:
                p = gamePlatforms.pop()
                if p != 'console' and p != 'desktop':
                    game['ignore'] = p
                    game.pop('metacritic', None)
                    if game['engine'] == 'engine':
                        game.pop('engine')
            else:
                if not 'console' in gamePlatforms:
                    game['ignore'] = ', '.join(gamePlatforms)
                    game.pop("metacritic", None)
                    if game['engine'] == 'engine':
                        game.pop('engine')
            if not 'ignore' in game:
                try:
                    if 'DLC / Add-on' in gameParser.genre:
                        game['ignore'] = 'DLC / Add-on'
                        game.pop("metacritic", None)
                        if game['engine'] == 'engine':
                            game.pop('engine')
                except AttributeError:
                    pass             

            conn.commit()
       
        json.dump(sorted(input, key=lambda k: "ignore" in k), output, indent=4, separators=(',', ': '))


if __name__=="__main__":
    if len(sys.argv) != 3:
        print 'Usage: prune_games in_file out_file'
        exit(1)
    main(sys.argv[1], sys.argv[2])



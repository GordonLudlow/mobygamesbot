#!/usr/bin/env python

# Scrape.py
# Scrape mobygames.com for team sizes to compare over time and by game engine
# Once mobygames releases their API, this will all be deprecated

import json, time, urllib2, HTMLParser

class GamePageParser(HTMLParser.HTMLParser):
    def __init__(self):
        self.teamMembers = set()
        HTMLParser.HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                    if '/developer/sheet/view/developerId,' in attr[1]:
                        self.teamMembers.add(attr[1])

class DeveloperPageParser(HTMLParser.HTMLParser):
    def __init__(self, gameLink):
        self.gameLink = gameLink
        self.roles = set()
        self.parsingHeader = False
        self.header = None
        HTMLParser.HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'h3':
            self.parsingHeader = True
            #print "found header tag"
        elif tag == 'a':
            #print "found anchor tag"
            if self.header:
                for attr in attrs:
                    if attr[0] == 'href':
                        if self.gameLink == attr[1]:
                            #print "found game back link"
                            self.roles.add(self.header)
                        #else:
                            #print "found some other a href %s (!= %s)" % (attr[1], self.gameLink)

    def handle_endtag(self, tag):
        if tag == 'table':
            self.header = None

    def handle_data(self, data):
        if self.parsingHeader:
            self.header = data
            self.parsingHeader = False



def GetMobyGamePage(creditsUrl):
    # A credits URL has this format: http://www.mobygames.com/game/<plaform>/<game>/credits
    # The corresponding game page is: http://www.mobygames.com/game/<game>
    # As it appears in links from a developer's page: /game/<game>
    # Example: <a href="/game/diablo-iii">
    # http://www.mobygames.com/game/windows/diablo-iii/credits
    # http: //www.mobygames.com/game/diablo-iii
    # 
    start = creditsUrl[:-8].rfind('/')+1
    return '/game/%s' % creditsUrl[start:-8]

def GetContent(url, httpCache):
    if url in httpCache:
        #print "cached"
        return httpCache[url]
    contents = ''
    try:
        # Using "Custom User-Agent" because MobyGames uses CloudFlare which blocks the default, "Python-urllib/2.6"
        # Their robots.txt allows access to the parts of the site we're accessing.
        # Comments on their forums indicate that scraping is allowed until the API is released, 
        # http://www.mobygames.com/forums/dga,2/dgb,3/dgm,223636/
        # "Talking of which, we've run into a couple of people recently who are scraping MobyGames for projects like this. Well, your scraping will soon be unnecessary! Work is officially underway on a MobyGames API - for anyone wanting to use our data for non-commercial purposes. We really want to become _the_ easily usable data source for game info, & will be talking about how you can test the system & get an API key soon."

        req = urllib2.Request(url, headers={'User-Agent' : 'Moby Games Bot (https://github.com/GordonLudlow/mobygamesbot)'})
        time.sleep(1) # TODO: read it from robots.txt (1 is the value there now)
        response = urllib2.urlopen(req)
        contents = response.read()
        httpCache[url] = contents
        httpCache['dirty'] = True
    except urllib2.HTTPError, e:
        print 'Http error code - %s. %s' % (e.code, e.fp.read())
    except IOError as e:
        print 'I/O error({0}): {1} when downloading {2}'.format(e.errno, e.strerror, url)
    except:
        print 'Error opening url: %s' % url
        print sys.exc_info()[0]
    return contents

with open('http_cache.json') as data_file:
    httpCache = json.load(data_file)
httpCache['dirty'] = False
with open('games.json') as data_file:    
    games = json.load(data_file)
for game in games:
    gameContent = GetContent(game['credits'], httpCache)
    gameParser = GamePageParser()
    gameParser.feed(gameContent)

    print "%s credits %d people" % (game["game"], len(gameParser.teamMembers))

    # What did these people do?
    roles = {}
    backlink = GetMobyGamePage(game['credits'])
    for teamMember in gameParser.teamMembers:
        teamMemberContent = GetContent("http://www.mobygames.com%s" % teamMember, httpCache)
        teamMemberParser = DeveloperPageParser(backlink)
        teamMemberParser.feed(teamMemberContent)
        for role in teamMemberParser.roles:
            if role in roles:
                roles[role] = roles[role]+1
            else:
                roles[role] = 1
    for role in roles:
        print "%s: %d" % (role, roles[role])

# Write out any newly crawled pages to the cache
if httpCache['dirty']:
    with open('http_cache.json', 'w') as data_file:
        json.dump(httpCache, data_file)
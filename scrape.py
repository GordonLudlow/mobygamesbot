#!/usr/bin/env python

# Scrape.py
# Scrape mobygames.com for team sizes to compare over time and by game engine
# Once mobygames releases their API, this will all be deprecated

import HTMLParser, json, robotparser, time, urllib2

userAgent = 'Moby Games Bot (https://github.com/GordonLudlow/mobygamesbot)'

# The robotparser in python 2.7 doesn't support crawl-delay, this does
class RobotsTxtParser(robotparser.RobotFileParser):
    def read(self):
        """Reads the robots.txt URL and feeds it to the parser."""
        try:
            req = urllib2.Request(self.url, headers={'User-Agent' : userAgent})
        except urllib2.HTTPError as err:
            if err.code in (401, 403):
                self.disallow_all = True
            elif err.code >= 400:
                self.allow_all = True
        else:
            response = urllib2.urlopen(req)
            raw = response.read()
            lines = raw.decode('utf-8').splitlines()
            self.parse(lines)
            for line in lines:
                if line.startswith("Crawl-delay:"):
                    self.crawl_delay = float(line[12:])


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
            #print 'found header tag'
        elif tag == 'a':
            #print 'found anchor tag'
            if self.header:
                for attr in attrs:
                    if attr[0] == 'href':
                        if self.gameLink == attr[1]:
                            #print 'found game back link'
                            self.roles.add(self.header)
                        #else:
                            #print 'found some other a href %s (!= %s)' % (attr[1], self.gameLink)

    def handle_endtag(self, tag):
        if tag == 'table':
            self.header = None

    def handle_data(self, data):
        if self.parsingHeader:
            self.header = data
            self.parsingHeader = False
# A cached game page shouldn't get stale because MobyGames doesn't really track live teams
# But a developer page can definitely get stale.  If the game link doesn't appear on the develop page,
# we may have cached it before the game was added.  If that happens, we catch it below.


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

def GetContent(url, httpCache, robot):
    if url in httpCache:
        #print 'cached'
        return httpCache[url]

    if not robot.can_fetch(userAgent, url):
        print 'This bot has been blocked from scraping mobygames.com by their robots.txt file'
        print '%s is disallowed' % url
        exit(1)
    print 'Downloading %s' % url
    contents = ''
    try:
        # Using "Custom User-Agent" because MobyGames uses CloudFlare which blocks the default, "Python-urllib/2.6"
        # Their robots.txt allows access to the parts of the site we're accessing.
        # Comments on their forums indicate that scraping is allowed until the API is released, 
        # http://www.mobygames.com/forums/dga,2/dgb,3/dgm,223636/
        # "Talking of which, we've run into a couple of people recently who are scraping MobyGames for projects like this. Well, your scraping will soon be unnecessary! Work is officially underway on a MobyGames API - for anyone wanting to use our data for non-commercial purposes. We really want to become _the_ easily usable data source for game info, & will be talking about how you can test the system & get an API key soon."

        time.sleep(robot.crawl_delay)
        req = urllib2.Request(url, headers={'User-Agent' : userAgent})
        response = urllib2.urlopen(req)
        encoding = response.headers.getparam('charset')
        contents = response.read().decode(encoding)
        httpCache[url] = contents
        with open('http_cache.json', 'w') as data_file:
            json.dump(httpCache, data_file)
    except urllib2.HTTPError, e:
        print 'Http error code - %s. %s' % (e.code, e.fp.read())
    except IOError as e:
        print 'I/O error({0}): {1} when downloading {2}'.format(e.errno, e.strerror, url)
    except:
        print 'Error opening url: %s' % url
        print sys.exc_info()[0]
    return contents

def main():
    robot = RobotsTxtParser('http://www.mobygames.com/robots.txt')
    robot.read()

    with open('http_cache.json') as data_file:
        httpCache = json.load(data_file)

    with open('dev_titles.json') as data_file:
        dev_title = json.load(data_file)

    with open('games.json') as data_file:    
        games = json.load(data_file)

    for game in games:
        gameContent = GetContent(game['credits'], httpCache, robot)
        gameParser = GamePageParser()
        gameParser.feed(gameContent)

        print '%s credits %d people' % (game['game'], len(gameParser.teamMembers))

        # What did these people do?
        roles = {}
        backlink = GetMobyGamePage(game['credits'])
        for teamMember in gameParser.teamMembers:
            teamMemberContent = GetContent('http://www.mobygames.com%s' % teamMember, httpCache, robot)
            teamMemberParser = DeveloperPageParser(backlink)
            teamMemberParser.feed(teamMemberContent)
            if not teamMemberParser.roles:
                print "Didn't find link back to %s from %s" % (backlink, teamMember)
                print "Cache is stale?  Need to be able to re-cache a developer page if they work on a new game"
                exit(1)
            for role in teamMemberParser.roles:
                if role in roles:
                    roles[role].append(teamMember)
                else:
                    roles[role] = [teamMember]
        devteam = set()
        for role in roles:
            if role not in dev_title:
                print 'Add %s to dev_titles.json' % role
                exit(1)
            if dev_title[role]:
                for person in roles[role]:
                    devteam.add(person)
        print '%d of these are on the dev team' % len(devteam)
        print '%d programmers' % len(roles['Programming/Engineering'])


if __name__=="__main__":
    main()



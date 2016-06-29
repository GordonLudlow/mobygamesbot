#!/usr/bin/env python

# Scrape.py
# Scrape mobygames.com for team sizes to compare over time and by game engine
# Once mobygames releases their API, this will all be deprecated

import codecs, HTMLParser, json, robotparser, sys, time, urllib2

userAgent = 'Moby Games Bot (https://github.com/GordonLudlow/mobygamesbot)'
lastPageRequestTime = time.time()

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
        self.teamMembers = {}
        self.newTitle = False
        self.developedByBlock = False
        HTMLParser.HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                    page = attr[1]
                    if '/developer/sheet/view/developerId,' in page:
                        if not page in self.teamMembers:
                            self.teamMembers[page] = {}
                        if not 'titles' in self.teamMembers[page]:
                            self.teamMembers[page]['titles'] = set()
                        self.teamMembers[page]['titles'].add(self.title)
        elif tag == 'tr':
            for attr in attrs:
                if attr[0] == 'class' and attr[1] == 'crln':
                    self.newTitle = True
                    self.title = ''

    def handle_endtag(self, tag):
        if tag == 'td':
            self.newTitle = False
        if tag == 'a':
            self.developedByBlock = False

    def handle_data(self, data):
        if self.newTitle:
            if self.title:
                self.title = self.title + ' '
            self.title = self.title + data
        if data == 'Developed by':
            self.developedByBlock = True
            self.developer = ''
        elif self.developedByBlock:
            if self.developer:
                self.developer = self.developer + ' '
            self.developer = self.developer + data

class DeveloperPageParser(HTMLParser.HTMLParser):
    def __init__(self, gameLink):
        self.gameLink = gameLink
        self.roles = set()
        self.rolesOnAllGames = {}
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
                        if '/game/' in attr[1]:
                            if self.header in self.rolesOnAllGames:
                                self.rolesOnAllGames[self.header] = self.rolesOnAllGames[self.header]+1
                            else:
                                self.rolesOnAllGames[self.header] = 1
                            if self.gameLink == attr[1]:
                                self.roles.add(self.header)

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

        delay = robot.crawl_delay
        global lastPageRequestTime
        elapsedTime = time.time() - lastPageRequestTime
        if elapsedTime < delay:
            print "waiting %f seconds" % (delay - elapsedTime)
            time.sleep(delay - elapsedTime)
        lastPageRequestTime = time.time()

        req = urllib2.Request(url, headers={'User-Agent' : userAgent})
        response = urllib2.urlopen(req)
        encoding = response.headers.getparam('charset')
        contents = response.read().decode(encoding)
        httpCache[url] = contents
        with open('http_cache.json', 'w') as data_file:
            json.dump(httpCache, data_file)
    except urllib2.HTTPError, e:
        # If someone has a private profile and we try to read it, we get a 404. 
        # The error text tells us it's private.
        # We want to cache the error so we don't keep requesting the 'private profile' error page.
        contents = e.fp.read()
        httpCache[url] = contents
        with open('http_cache.json', 'w') as data_file:
            json.dump(httpCache, data_file)
        print 'Http error code - %s. %s' % (e.code, contents)
    except IOError as e:
        print 'I/O error({0}): {1} when downloading {2}'.format(e.errno, e.strerror, url)
    except:
        print 'Error opening url: %s' % url
        print sys.exc_info()[0]
    return contents

def keywithmaxval(d): # See http://stackoverflow.com/questions/268272/getting-key-with-maximum-value-in-dictionary
     """ a) create a list of the dict's keys and values; 
         b) return the key with the max value"""  
     v=list(d.values())
     k=list(d.keys())
     return k[v.index(max(v))]

def main():
    robot = RobotsTxtParser('http://www.mobygames.com/robots.txt')
    robot.read()

    with open('http_cache.json') as data_file:
        httpCache = json.load(data_file)

    with open('dev_titles.json') as data_file:
        dev_title = json.load(data_file)

    with open('games.json') as data_file:    
        games = json.load(data_file)

    platforms = set()
    for game in games:
        for platform in game['metacritic']:
            platforms.add(platform)
    with codecs.open('output.txt', encoding='utf-8-sig', mode='w+') as output_file:
        output_file.write('\t\t\t\t\t\t\tMetacritic scores\n')
        output_file.write('%s\t%s\t%s\t%s\t%s\t%s\t%s' % ('Game', 'Developer', 'Engine', 'Year released', 'Credited people', 'Dev team size', 'Programmers'))
        for platform in platforms:
            output_file.write('\t%s' % platform)
        output_file.write('\n');
        for game in games:
            gameContent = GetContent(game['credits'], httpCache, robot)
            gameParser = GamePageParser()
            gameParser.feed(gameContent)

            print '%s (from %s) credits %d people' % (game['game'], gameParser.developer, len(gameParser.teamMembers))
            output_file.write('%s\t%s\t%s\t%d\t%d' % (game['game'], gameParser.developer,game['engine'],game['year'],len(gameParser.teamMembers)))

            # What did these people do?
            roles = {}
            backlink = GetMobyGamePage(game['credits'])
            for teamMember in gameParser.teamMembers:
                teamMemberContent = GetContent('http://www.mobygames.com%s' % teamMember, httpCache, robot)
                teamMemberParser = DeveloperPageParser(backlink)
                teamMemberParser.feed(teamMemberContent)
                if teamMemberParser.roles:
                    gameParser.teamMembers[teamMember]['roles'] = teamMemberParser.roles
                else:
                    if 'private profile' in teamMemberContent:
                        # private profile
                        print '%s on %s has a private profile' % (teamMember, backlink)

                        # Does someone with a non-private profile have the same title in this game's credits
                        for title in gameParser.teamMembers[teamMember]['titles']:
                            if teamMemberParser.roles:
                                break
                            for someoneElse in gameParser.teamMembers:
                                if someoneElse != teamMember and title in gameParser.teamMembers[someoneElse]['titles']:
                                    teamMemberParser.roles = gameParser.teamMembers[someoneElse]['roles']
                                    print 'Someone else was also credited with %s, so assuming:' % title
                                    for role in teamMemberParser.roles:
                                        print '\t%s' % role
                                    break
                        if not teamMemberParser.roles:
                            print "Couldn't find someone else with the same title.  Need to assign based on title on the game page."
                            exit(1) 
                    else:
                        print "Didn't find link back to %s from %s" % (backlink, teamMember)
                        print "Cache is stale?  Need to be able to re-cache a developer page if they work on a new game"
                        exit(1)
                for role in teamMemberParser.roles:
                    if role in roles:
                        roles[role].append(teamMember)
                    else:
                        roles[role] = [teamMember]
                # if the only credit they have for this game is "Other", deduce what they do by their credits on other games
                if (len(teamMemberParser.roles) == 1) and ('Other' in teamMemberParser.roles) and (len(teamMemberParser.rolesOnAllGames)>1):
                    del teamMemberParser.rolesOnAllGames['Other']
                    #print 'Person credited only as "Other".  Roles on all games:'
                    #for role in teamMemberParser.rolesOnAllGames:
                    #    print '\t%s: %d' % (role, teamMemberParser.rolesOnAllGames[role])
                    role = keywithmaxval(teamMemberParser.rolesOnAllGames)
                    #print '\tPredominant role: %s' % role 
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
            if 'Programming/Engineering' in roles:
                print '%d programmers' % len(roles['Programming/Engineering'])
                output_file.write('\t%d\t%d' % (len(devteam), len(roles['Programming/Engineering'])))
            else:
                print 'No programmers?'
                print 'Roles are:'
                for role in roles:
                    print '\t%s' % role
                exit(1)
            for platform in platforms:
                output_file.write('\t')
                if platform in game['metacritic']:
                    output_file.write('%d' % game['metacritic'][platform])
            output_file.write('\n');


if __name__=="__main__":
    main()



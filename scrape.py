#!/usr/bin/env python

# Scrape.py
# Scrape mobygames.com for team sizes to compare over time and by game engine
# Once mobygames releases their API, this will all be deprecated

import codecs, HTMLParser, json, robotparser, sys, time, urllib2
import sqlite3
import string

userAgent = 'Moby Games Bot (https://github.com/GordonLudlow/mobygamesbot)'
baseDeveloperUrl = 'http://www.mobygames.com/developer/sheet/view/developerId,'
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
        self.genreBlock = False
        self.foundFirstGenre = True
        self.platformBlock = False
        self.platform = []
        self.platformCount = 0
        self.platformUrls = []
        self.inATag = False
        self.inPTag = False
        self.paragraphText = ''
        self.listingPlatformUrls = False
        self.uninterestingCharacters = set(string.punctuation+string.whitespace)        
        HTMLParser.HTMLParser.__init__(self)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.inATag = True
            if self.platformBlock:
                self.platform.append('')        
            for attr in attrs:
                if attr[0] == 'href':
                    page = attr[1]
                    if self.listingPlatformUrls:
                        #print 'Link to platform: %s' % page
                        self.platformUrls.append(page)
                    elif '/developer/sheet/view/developerId,' in page:
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
        elif tag == 'p':
            self.inPTag = True
            self.paragraphText = ''

    def handle_endtag(self, tag):
        if tag == 'td':
            self.newTitle = False
        elif tag == 'a':
            self.inATag = False
            self.developedByBlock = False
            if self.genreBlock:
                self.foundFirstGenre = True
            if self.platformBlock:
                self.platformCount = self.platformCount + 1                
        elif tag == 'div':
            if self.platform:
                self.platformBlock = False        
            if self.foundFirstGenre:
                self.genreBlock = False
                self.foundFirstGenre = False
                try:
                    if 'DLC / Add-on' in self.genre:
                        print self.genre
                        exit(1)
                except AttributeError:
                    pass
        elif tag == 'p':
            self.inPTag = False
            #print '<p>%s</p>' % self.paragraphText
            if self.paragraphText == 'The following releases of this game have credits associated with them:':
                self.listingPlatformUrls = True
        elif tag == 'ul':
            self.listingPlatformUrls = False
                 
    def handle_data(self, data):
        if self.inPTag:
            if self.paragraphText:
                self.paragraphText = self.paragraphText + ' '
            self.paragraphText = self.paragraphText + data
        elif self.newTitle:
            if self.title:
                self.title = self.title + ' '
            self.title = self.title + data
            
        elif not self.platform and not self.inATag and (data == 'Platform' or data == 'Platforms'):
            self.platformBlock = True
        elif self.platformBlock and not all(c in self.uninterestingCharacters for c in data):
            if self.platform[self.platformCount]:
                self.platform[self.platformCount] = self.platform[self.platformCount] + ' '
            self.platform[self.platformCount] = self.platform[self.platformCount] + data
            
        elif data == 'Developed by':
            self.developedByBlock = True
            self.developer = ''
        elif self.developedByBlock:
            if self.developer:
                self.developer = self.developer + ' '
            self.developer = self.developer + data
        elif data == "Genre":
            self.genreBlock = True
            self.genre = ''
        elif self.genreBlock:
            if self.genre:
                self.genre = self.genre + ' '
            self.genre = self.genre + data

            
           
            
class DeveloperPageParser(HTMLParser.HTMLParser):
    def __init__(self, gameLink):
        self.gameLink = gameLink
        self.roles = set()
        self.rolesOnAllGames = {}
        self.titlesPerRole = {}
        self.parsingHeader = False
        self.header = None
        self.inDevCreditsTitleSpan = False
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
                            #else:
                            #    print "%s isn't %s" % (self.gameLink, attr[1])
                        #else:
                        #    print "non game link ", attr[1]
                    #else:
                    #    print "non-href attr"
                    #    for a in attr:
                    #        print a
            #else:
            #    print 'No header, ignoring link: '
            #    for attr in attrs:
            #        for a in attr:
            #            print a
        elif tag=='span':
            if self.header:
                for attr in attrs:
                    if attr[0] == 'class' and attr[1] == 'devCreditsTitle':
                        self.inDevCreditsTitleSpan = True
                        self.devCreditsTitle = ''

    def handle_endtag(self, tag):
        if tag == 'table':
            self.header = None
        if tag == 'span':
            if self.inDevCreditsTitleSpan:
                self.inDevCreditsTitleSpan = False
                if not self.header in self.titlesPerRole:
                    self.titlesPerRole[self.header] = set()
                self.titlesPerRole[self.header].add(self.devCreditsTitle)

    def handle_data(self, data):
        if self.parsingHeader:
            #print "header is %s" % data
            self.header = data
            self.parsingHeader = False
        elif self.inDevCreditsTitleSpan:
            if self.devCreditsTitle:
                self.devCreditsTitle = self.devCreditsTitle + ' '
            self.devCreditsTitle = self.devCreditsTitle + data
# A cached game page shouldn't get stale because MobyGames doesn't really track live teams
# But a developer page can definitely get stale.  If the game link doesn't appear on the develop page,
# we may have cached it before the game was added.  If that happens, we catch it below.


def GetMobyGamePage(creditsUrl):
    # A credits URL has this format: http://www.mobygames.com/game/<plaform>/<game>/credits
    # or, for a game released on one platform:  http://www.mobygames.com/game/<game>/credits
    # The corresponding game page is: http://www.mobygames.com/game/<game>
    # As it appears in links from a developer's page: /game/<game>
    # Example: <a href="/game/diablo-iii">
    # http://www.mobygames.com/game/windows/diablo-iii/credits
    # http://www.mobygames.com/game/diablo-iii
    # /game/diablo-iii
    start = creditsUrl[:-8].rfind('/')+1
    return '/game/%s' % creditsUrl[start:-8]

def CacheUrl(url, contents, httpCache):
    if '/game/' in url:
        httpCache.execute("INSERT OR REPLACE INTO games VALUES (?, ?)", (url, contents))
    elif baseDeveloperUrl in url:
        httpCache.execute("INSERT OR REPLACE INTO developers VALUES (?,?)", (url[len(baseDeveloperUrl):-1], contents))
    else:
        print "Can't cache this url: %s" % url
        exit(1)
    
def GetContent(url, httpCache, robot, forceDownload=False):
    if not forceDownload:
        # Look it up in the db
        if '/game/' in url:
            httpCache.execute('SELECT contents FROM games where url=?', (url,))
            row = httpCache.fetchone()
            if row:        
                return row[0]
        elif baseDeveloperUrl in url:
            httpCache.execute('SELECT contents FROM developers where id=?', (url[len(baseDeveloperUrl):-1],))
            row = httpCache.fetchone()
            if row:        
                return row[0]
        else:
            print 'url is neither a game credits page nor a developer page'
            print url
            exit(1)

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
        CacheUrl(url, contents, httpCache)
    except urllib2.HTTPError, e:
        # If someone has a private profile and we try to read it, we get a 404. 
        # The error text tells us it's private.
        # We want to cache the error so we don't keep requesting the 'private profile' error page.
        contents = e.fp.read()
        CacheUrl(url, contents, httpCache)
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

    with open('dev_titles.json') as data_file:
        dev_title = json.load(data_file)

    with open('games.json') as data_file:    
        games = json.load(data_file)

    platforms = set()
    for game in games:
        try:
            for platform in game['metacritic']:
                platforms.add(platform)
        except KeyError:
            print "%s doesn't have metacritic scores." % game['game']
            exit(1)
            
    mgPlatforms = []
    with open('platform.json') as data_file:
        dict = json.load(data_file)
        for p in dict:
            if dict[p] == 'console' or dict[p] == 'desktop':
                mgPlatforms.append(p)

    with codecs.open('output.txt', encoding='utf-8-sig', mode='w+') as output_file, sqlite3.connect('http_cache.db') as conn:
        output_file.write('\t\t\t\t\t\t\tPlatforms%sMetacritic scores\n' % ('\t' * len(mgPlatforms)))
        output_file.write('%s\t%s\t%s\t%s\t%s\t%s\t%s' % ('Game', 'Developer', 'Engine', 'Year released', 'Credited people', 'Dev team size', 'Programmers'))
        for platform in mgPlatforms:
            output_file.write('\t%s' % platform)        
        for platform in platforms:
            output_file.write('\t%s' % platform)
        output_file.write('\n')

        httpCache = conn.cursor()

        for game in games:
            if 'ignore' in game:
                continue
            print game['game']
            baseCreditsUrl = 'http://www.mobygames.com' + GetMobyGamePage(game['credits']) + '/credits'
            gameContent = GetContent(baseCreditsUrl, httpCache, robot)
            gameParser = GamePageParser()
            if 'developer' in game:
                gameParser.developer = game['developer']
            gameParser.feed(gameContent)
            
            # At this point, either gameParser has all of the team member data
            # from the single-platform game -or- it has no team memeber data but
            # has a list of urls to parse to get the data for all the platform(s).
            # Feed it the other platform(s), if any.
            for platformUrl in gameParser.platformUrls:
                gameContent = GetContent('http://www.mobygames.com%s' % platformUrl, httpCache, robot)
                gameParser.feed(gameContent)

            print '%s (from %s) credits %d people across %d platforms (%d documented)' % (game['game'], gameParser.developer, len(gameParser.teamMembers), gameParser.platformCount, len(gameParser.platformUrls))
            output_file.write('%s\t%s\t%s\t%d\t%d' % (game['game'], gameParser.developer,game['engine'],game['year'],len(gameParser.teamMembers)))

            # What did these people do?
            roles = {}
            backlink = GetMobyGamePage(game['credits'])
            for teamMember in gameParser.teamMembers:
                for retry in (False, True):
                    teamMemberContent = GetContent('http://www.mobygames.com%s' % teamMember, httpCache, robot, retry)
                    teamMemberParser = DeveloperPageParser(backlink)
                    teamMemberParser.feed(teamMemberContent)
                    if teamMemberParser.roles:
                        gameParser.teamMembers[teamMember]['roles'] = teamMemberParser.roles
                        break # don't need to retry
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
                            break # don't need to retry 
                        else:
                            if retry:
                                print "Didn't find link back to %s from %s" % (backlink, teamMember)
                                print "Cache is not stale!"
                                print

                                for title in gameParser.teamMembers[teamMember]['titles']:
                                    print title
                                    for role in teamMemberParser.titlesPerRole:
                                        print role
                                        for credit in teamMemberParser.titlesPerRole[role]:
                                            print '\t%s' % credit
                                            if credit == title:
                                                teamMemberParser.roles.add(role)
                                                print '%s so assume %s' % (title, role)
                                if not teamMemberParser.roles:
                                    print "Couldn't find that credit on another game"
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
            elif 'programmers' in game:
                print '%d programmers (who also had other roles)' % game['programmers']
                output_file.write('\t%d\t%d' % (len(devteam), game['programmers']))            
            elif not 'no programmers' in game:
                print 'No programmers?'
                print 'Roles are:'
                for role in roles:
                    print '\t%s' % role
                exit(1)
            for platform in mgPlatforms:
                output_file.write('\t')
                if platform in gameParser.platform:
                    output_file.write('1')
            for platform in platforms:
                output_file.write('\t')
                if platform in game['metacritic']:
                    output_file.write('%d' % game['metacritic'][platform])
            output_file.write('\n');
            conn.commit()


if __name__=="__main__":
    main()



#!/usr/bin/env python

# Scrape.py
# Scrape mobygames.com for team sizes to compare over time and by game engine
# Once mobygames releases their API, this will all be deprecated

import json, time, urllib2

def GetContent(url, httpCache):
    if url in httpCache:
        print "cached"
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
with open('games.json') as data_file:    
    games = json.load(data_file)
for game in games:
    content = GetContent(game['credits'], httpCache)

# Write out any newly crawled pages
with open('http_cache.json', 'w') as data_file:
    json.dump(httpCache, data_file)
# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import json
import sys
#import threading
#import time
#from Queue import Queue, Empty

from default import autoplayRandomize

def getDbPath():
    import os

    path = xbmc.translatePath("special://userdata/Database")
    files = os.listdir(path)
    latest = ""
    for file in files:
        if file[:8] == 'MyVideos' and file[-3:] == '.db':
            if file > latest:
                latest = file
    if latest:
        return os.path.join(path, latest)
    else:
        return ""

def getPlayCount(url):
    import sqlite3
    
    dbPath = getDbPath()
    if dbPath:
        conn = sqlite3.connect(dbPath)
        c = conn.cursor()

        #log(url[:120])
        #c.execute('SELECT playCount FROM files WHERE strFilename LIKE ?', [url[:100]])

        str_sql='SELECT playCount FROM files WHERE strFilename LIKE ?'
        args=[url[:120]+'%']

        #str_sql='SELECT playCount FROM files WHERE strFilename = ?'
        #args=[url]

        c.execute(str_sql,args)


        result = c.fetchone()
        #log('*****************'+repr(result) )
        if result:
            result = result[0]
            if result:
                return int(result)
            return 0
    return -1

#def getPlayCount(url):
#
#    #query   = '{"jsonrpc": "2.0","method": "VideoLibrary.GetTVShows","params": {"filter": {"field": "playcount", "operator": "is", "value": "0" },"properties": ["lastplayed"], "sort": {"order": "descending", "method": "lastplayed"} },"id": "1" }'
#    #request = '{"jsonrpc": "2.0","method": "VideoLibrary.GetMovies", "params": {"filter": {"field": "playcount", "operator": "greaterthan", "value": "0"},  "limits": { "start" : 0 }, "properties": ["playcount"], "sort": { "order": "ascending", "method": "label" } }, "id": "libMovies"}'
#    #request='{"jsonrpc": "2.0", "method": "Player.GetItem", "params": { "properties": ["title", "album", "artist", "season", "episode", "duration", "showtitle", "tvshowid", "thumbnail", "file", "fanart", "streamdetails"], "playerid": 1}, "id": "VideoGetItem"}'
#
#    #results = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
#
##    get_movies       = {"jsonrpc": "2.0",'id': 1, "method": "VideoLibrary.GetMovies",     "params": { "filter": {"field": "playcount", "operator": "is", "value": "0"}, "properties" : ["playcount", "title"] }}
##
##    mov = json_query(get_movies, True)
##    log(repr(mov))
#
#    request = {"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"field": "playcount", "operator": "greaterthan", "value": "0"}, "limits": { "start" : 0 }, "properties": ["playcount"], "sort": { "order": "ascending", "method": "label" } }, "id": url}
#    results = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
#    log(repr(results))


def autoPlay(url, name, autoPlay_type):
    import random
    from domains import sitesBase, parse_reddit_link, build_DirectoryItem_url_based_on_media_type
    from utils import unescape, post_is_filtered_out, log, clean_str
    from actions import setting_gif_repeat_count
    from reddit import reddit_request, determine_if_video_media_from_reddit_json
    #collect a list of title and urls as entries[] from the j_entries obtained from reddit
    #then create a playlist from those entries
    #then play the playlist

    gif_repeat_count=setting_gif_repeat_count()

    entries = []
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    playlist.clear()
    log("**********autoPlay %s*************" %autoPlay_type)
    content = reddit_request(url)
    if not content: return

    content = json.loads(content.replace('\\"', '\''))

    log("Autoplay %s - Parsing %d items" %( autoPlay_type, len(content['data']['children']) )    )

    for j_entry in content['data']['children']:
        try:
            if post_is_filtered_out( j_entry ):
                continue

            title = clean_str(j_entry, ['data','title'])

            try:
                media_url = j_entry['data']['url']
            except:
                media_url = j_entry['data']['media']['oembed']['url']

            is_a_video = determine_if_video_media_from_reddit_json(j_entry)

            #log("  Title:%s -%c %s"  %( title, ("v" if is_a_video else " "), media_url ) )
            #hoster, DirectoryItem_url, videoID, mode_type, thumb_url,poster_url, isFolder,setInfo_type, IsPlayable=make_addon_url_from(media_url,is_a_video)
            ld=parse_reddit_link(link_url=media_url, assume_is_video=is_a_video, needs_preview=False, get_playable_url=True )

            DirectoryItem_url, setProperty_IsPlayable, isFolder, title_prefix = build_DirectoryItem_url_based_on_media_type(ld, media_url, title, on_autoplay=True)

            if ld:
                if ld.media_type not in [sitesBase.TYPE_VIDEO, sitesBase.TYPE_GIF, sitesBase.TYPE_VIDS, sitesBase.TYPE_MIXED]:
                    continue

            autoPlay_type_entries_append( entries, autoPlay_type, title, DirectoryItem_url)
            if ld.media_type == sitesBase.TYPE_GIF:
                for _ in range( 0, gif_repeat_count ):
                    autoPlay_type_entries_append( entries, autoPlay_type, title, DirectoryItem_url)

        except Exception as e:
            log("  EXCEPTION Autoplay "+ str( sys.exc_info()[0]) + "  " + str(e) )

    #def k2(x): return x[1]
    #entries=remove_duplicates(entries, k2)

    if autoplayRandomize:
        random.shuffle(entries)

    #for title, url in entries:
    #    log("  added to playlist:"+ title + "  " + urllib.unquote_plus(url) )
    for title, url in entries:
        listitem = xbmcgui.ListItem(title)
        playlist.add(url, listitem)
        log('add to playlist: %s %s' %(title.ljust(25)[:25],url ))
    xbmc.Player().play(playlist)

def autoPlay_type_entries_append( entries, autoPlay_type, title, playable_url):
    #log(' ****playcount %d:[%s] %s' %( getPlayCount(playable_url), playable_url, title) )
    if autoPlay_type=="ALL":
        entries.append([title,playable_url])
    elif autoPlay_type=="UNWATCHED" and getPlayCount(playable_url) <= 0:
        #log('added to UNWATCHED %s' %( title) )
        entries.append([title,playable_url])
    #elif autoPlay_type.startswith("UNFINISHED_") and getPlayCount(url) == 0:
    #    entries.append([title,playable_url])

if __name__ == '__main__':
    pass
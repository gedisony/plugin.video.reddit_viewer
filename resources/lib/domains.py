#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import sys
import re
import requests
import json
from urllib.parse import urlparse
#sys.setdefaultencoding("utf-8")

from default import addon, streamable_quality,hide_nsfw
from default import addon_path, pluginhandle, reddit_userAgent, REQUEST_TIMEOUT
from .utils import log, parse_filename_and_ext_from_url, image_exts, link_url_is_playable, ret_url_ext, remove_duplicates, safe_cast, clean_str,pretty_datediff_wrap, nested_lookup

#use_ytdl_for_yt      = addon.getSetting("use_ytdl_for_yt") == "true"    #let youtube_dl addon handle youtube videos. this bypasses the age restriction prompt
use_addon_for_youtube     = addon.getSetting("use_addon_for_youtube") == "true"
use_addon_for_Liveleak    = addon.getSetting("use_addon_for_Liveleak") == "true"
#resolve_undetermined = addon.getSetting("resolve_undetermined") == "true" #let youtube_dl addon get playable links if unknown url(slow)

from . CommonFunctions import parseDOM

keys=[ 'li_label'           #  the text that will show for the list
      ,'li_label2'          #
      ,'li_iconImage'       #
      ,'li_thumbnailImage'  #
      ,'DirectoryItem_url'  #
      ,'is_folder'          #
      ,'type'               # video pictures  liz.setInfo(type='pictures',
      ,'isPlayable'         # key:value       liz.setProperty('IsPlayable', 'true')  #there are other properties but we only use this
      ,'infoLabels'         # {"title": post_title, "plot": description, "plotoutline": description, "Aired": credate, "mpaa": mpaa, "Genre": "r/"+subreddit, "studio": hoster, "director": posted_by }   #, "duration": 1271}   (duration uses seconds for titan skin
      ,'width'
      ,'height'
      ,'description'
      ,'link_action'
      ,'channel_id'         #used in youtube videos
      ,'channel_name'
      ,'video_id'           #used in youtube videos
      ]
ytdl_sites=[]
#deviantart mixtape.moe sli.mg

class sitesBase(object):
    regex=''
    thumb_url=''
    poster_url=''
    media_type=''
    link_action=''   #'playable' for direct video links or one of the "modes" used by this script
    dictList = []   #used by assemble_images_dict ret_album_list and
    media_url=''
    original_url=''
    media_w=0
    media_h=0
    description=None  #additional description gathered from link
    video_id=''

    include_gif_in_get_playable=False   #it is best to parse the link and get the mp4/webm version of a gif media. we can't do this with some sites so we just return the gif media instead of looking for mp4/webm

    TYPE_IMAGE='image'
    TYPE_ALBUM='album'
    TYPE_VIDEO='video'
    TYPE_GIF='gifvideo'   #this indicates that the video needs to be repeated
    TYPE_VIDS ='vids'
    TYPE_MIXED='mixed'
    TYPE_REDDIT='reddit'
    TYPE_UNKNOWN='unknown'
    DI_ACTION_PLAYABLE='playable'
    DI_ACTION_YTDL='playYTDLVideo'
    DI_ACTION_URLR='playURLRVideo'
    DI_ACTION_ERROR='error_message'

    def __init__(self, link_url):
        self.media_url=link_url
        self.original_url=link_url

    def get_html(self,link_url=''):
        if not link_url:
            link_url=self.original_url

        content = self.requests_get(link_url)

        return content.text

    @classmethod
    def requests_get(self, link_url, headers=None, timeout=REQUEST_TIMEOUT, allow_redirects=True):
        content = requests.get( link_url, headers=headers, timeout=timeout, allow_redirects=allow_redirects )
        #there is an error here: get_thumb_url error:No module named 'requests.packages.urllib3.packages.ordered_dict'
        #don't know what to do with this error. just leaving it alone if it just comes up when getting thumbnail for subreddits



        #if hasattr(content, "from_cache"): log( '  #cached:{0} {1}'.format( repr(content.from_cache),link_url) )
        #else:log( '  #cache disabled: {0}'.format( link_url) )  #if requests_cache is not installed, page will not have from_cache attribute
        if content.status_code==requests.codes.ok:
            return content
        else:
            log('    error: %s requests_get: %s %s' %(self.__class__.__name__, repr( content.status_code ), link_url ) )
            content.raise_for_status()
            #raise Exception()
            #xbmc.executebuiltin('XBMC.Notification("%s", "%s" )' %( content.status_code, link_url  ) )
            return None

    def get_playable(self, media_url='', is_probably_a_video=False ):
        media_type=''
        if not media_url:
            media_url=self.media_url

        _,ext=parse_filename_and_ext_from_url(media_url)
        if self.include_gif_in_get_playable:
            if ext in ["mp4","webm","gif"]:
                media_type=self.TYPE_VIDEO
                if ext=='gif':
                    media_type=self.TYPE_GIF
                    self.link_action=sitesBase.DI_ACTION_PLAYABLE
                    self.thumb_url=media_url
                    self.poster_url=self.thumb_url
                return media_url,media_type
        else:
            if ext in ["mp4","webm"]:
                self.link_action=self.DI_ACTION_PLAYABLE
                return self.media_url,self.TYPE_VIDEO

        if ext in image_exts:  #excludes .gif
            self.thumb_url=media_url
            self.poster_url=self.thumb_url
            return self.media_url,self.TYPE_IMAGE

        return self.get_playable_url(self.media_url, is_probably_a_video=False )

    def get_playable_url(self, media_url, is_probably_a_video ):
        raise NotImplementedError

    def get_thumb_url(self):
        raise NotImplementedError

    def request_meta_ogimage_content(self,link_url=''):
        if not link_url: link_url=self.media_url

        m_type=link_url_is_playable(link_url)
        if m_type:
            #if m_type=='image': return link_url
            return link_url #will a video link resolve to a preview image?
        else:
            try:
                #headers = {"Range": "bytes=0-1000"} content = self.requests_get(link_url, headers)
                #timeout not working right if redirect.

                #first, do a head request. sometimes the link is an mp3 and we don't want to download the entire file just to check the 'content-type'
                head=requests.head(link_url, timeout=(4,4),allow_redirects=True)
                #log('head request returned:'+repr(head.status_code)+' '+repr(head.headers))
                if head.status_code==requests.codes.ok:
                    if 'html' in head.headers.get('content-type') :
                        r = self.requests_get(link_url,headers=None, timeout=(4,4), allow_redirects=True)
                        #log( "getting OG:image:" + repr(r.headers))
                        if r:
                            a=parseDOM(r.text, "meta", attrs = { "property": "og:image" }, ret="content" )   #most sites use <meta property="
                            b=parseDOM(r.text, "meta", attrs = {     "name": "og:image" }, ret="content" )   #boardgamegeek uses <meta name="
                            i=next((item for item in [a,b] if item ), '')
                            #log( "if parseDOM:" + link_url)
                            if i:
                                try:
                                    return urllib.parse.urljoin(link_url, i[0]) #handle relative or absolute
                                except IndexError: pass
                                else:
                                    log('      %s: cant find <meta property="og:image" '  %(self.__class__.__name__ ) )
            except Exception as e:
                log('request_meta_ogimage_content:'+str(e))

    #def combine_title_and_description(self, title, description):
    #    return ( '[B]'+title+'[/B]\n' if title else '' ) + ( description if description else '' )

    def clog(self, error_code, request_url):
        log("    %s error:%s %s" %( self.__class__.__name__, error_code ,request_url) )
    @classmethod
    def get_first_url_from(self,string_with_url,return_all_as_list=False):
        #first, search for [link description](https:www.yhotuve.com/...) pattern
        #  NOTE that the [...](...) pattern has a space inserted between the [] and () in format_description() and we account for this in the regex
        match = re.compile('\[.*?\][ ]??\((https?:\/\/.*?)\)').findall(string_with_url)
        if not match:
            match = re.compile("(https?://[^\s/$.?#].[^\s]*)['\\\"]?(?:$)?").findall(string_with_url)

        #log('   get_first_url_from:matches' + repr(match) )
        if match:
            if return_all_as_list:
                return match
            else:
                return match[0]

    @classmethod
    def split_text_into_links(self,string_with_url):
        if string_with_url:
            string_with_url=string_with_url+" \nhttp://blank.padding\n" #imperfect regex: need a padding to make regex work
            #match = re.compile("([\s\S]+?(?:(https?://\S*?\.\S*?)(?:[\s)\[\]{},;\"\':<]|\.\s|$)))").findall(string_with_url)
            match = re.compile("([\s\S]*?(?:(https?://\S*?\.\S*?)(?:[\s)\[\]{},;\"\':<]|$)))").findall(string_with_url) #imperfect regex: this regex needs more work so that we don't need to add the padding above and modify the match to remove the http... later in code.
            if match:
                #import pprint; log(pprint.pformat(match))
                return match

    def set_media_type_thumb_and_action(self,media_url,default_type=TYPE_VIDEO, default_action=DI_ACTION_YTDL):
        _,ext=parse_filename_and_ext_from_url(media_url)
        self.media_url=media_url
        if ext=='gif':
            self.media_type=self.TYPE_GIF #sitesBase.TYPE_VIDEO
            self.link_action=self.DI_ACTION_PLAYABLE  #playable uses pluginUrl directly
        elif ext in image_exts:    #image_exts = ['jpg','png', 'RAW', 'jpeg', 'tiff', 'tga', 'pcx', 'bmp']
            self.media_type=self.TYPE_IMAGE
        elif ext in ["mp4","webm"]:
            self.media_type=self.TYPE_VIDEO
            self.link_action=self.DI_ACTION_PLAYABLE
        else:
            self.media_type=default_type
            self.link_action=default_action

        if self.media_type in [self.TYPE_GIF, self.TYPE_IMAGE]:
            #assign thumb and poster image if there is none yet.
            self.thumb_url=media_url if self.thumb_url else self.thumb_url
            self.poster_url=media_url if self.poster_url else self.poster_url

    def assemble_images_dictList(self,images_list):
        title=label2=thumbnail=image_url=desc=None
        width=height=0
        isPlayable=infoLabels=link_action=channel_id=channel_name=video_id=None
        item_type=self.TYPE_IMAGE     #all default to type image

        for item in images_list:
            #log('      type: %s' %( type(item)  ) )
            if isinstance(item, str ):   #for python3 isinstance(item, (basestring,unicode) ):   #type(item) in [str,unicode]:  #if isinstance(item, basestring):                #log( 'assemble_images_dictList STRING')
                image_url=item
                thumbnail=image_url
            elif  isinstance(item, list):    #type(item) is list:
                if len(item)==1:
                    #log( 'assemble_images_dictList LEN1')
                    image_url=item[0]
                elif len(item)==2:
                    #log( 'assemble_images_dictList LEN2')
                    title=item[0]
                    image_url=item[1]
                    thumbnail=image_url
                elif len(item)==3:
                    #log( 'assemble_images_dictList LEN3')
                    title=item[0]
                    image_url=item[1]
                    thumbnail=item[2]
            elif isinstance(item, dict):  #type(item) is dict:
                title    =item.get('title') if item.get('title') else ''
                label2   =item.get('label2','')
                desc     =item.get('description') if item.get('description') else ''
                image_url=item.get('url')
                thumbnail=item.get('thumb')
                width    =item.get('width') if item.get('width') else 0
                height   =item.get('height') if item.get('height') else 0
                item_type=item.get('type')   #media_type
                isPlayable=item.get('isPlayable')
                link_action=item.get('link_action','')
                channel_id=item.get('channel_id','')
                channel_name=item.get('channel_name','')
                video_id=item.get('video_id','')
                duration=item.get('duration','') #kodi prefers infolabels.duration in seconds
                set_=item.get('set','')           #infolabels.set, name of the collection, i'm using this to show "14 videos" if item is a playlist

            infoLabels={ "Title": title, "plot": desc, "duration":duration, "set":set_,}
            #order is important here.
            e=[ title                   #'li_label'           #  the text that will show for the list (we use description because most albumd does not have entry['type']
               ,label2                  #'li_label2'          #
               ,""                      #'li_iconImage'       #
               ,thumbnail               #'li_thumbnailImage'  #
               ,image_url               #'DirectoryItem_url'  #
               ,False                   #'is_folder'          #
               ,item_type               #'type'               # video pictures  liz.setInfo(type='pictures',
               ,isPlayable              #'isPlayable'         # key:value       liz.setProperty('IsPlayable', 'true')  #there are other properties but we only use this
               ,infoLabels              #'infoLabels'         # {"title": post_title, "plot": description, "plotoutline": description, "Aired": credate, "mpaa": mpaa, "Genre": "r/"+subreddit, "studio": hoster, "director": posted_by }   #, "duration": 1271}   (duration uses seconds for titan skin
               ,width
               ,height
               ,desc                    #'description'
               ,link_action             #'link_action'
               ,channel_id              #'channel_id'
               ,channel_name            #'channel_name'
               ,video_id                #'video_id'
                ]
            self.dictList.append(dict(zip(keys, e)))

#    keys = ['FirstName', 'LastName', 'SSID']
#
#    name1 = ['Michael', 'Kirk', '224567']
#    name2 = ['Linda', 'Matthew', '123456']
#
#    dictList = []
#    dictList.append(dict(zip(keys, name1)))
#    dictList.append(dict(zip(keys, name2)))
#
#    print dictList
#    for item in dictList:
#        print ' '.join([item[key] for key in keys])
def all_same(items):
    #returns True if all items the same
    return all(x == items[0] for x in items)

def url_resolver_support(link_url):
    return False

class ClassYoutube(sitesBase):
    regex='(youtube.com/)|(youtu.be/)|(youtube-nocookie.com/)|(plugin.video.youtube/play)'
    video_id=''
    url_type=''

    api_key='AIzaSyBilnA0h2drOvpnqno24xeVqGy00fp07so'

    @classmethod
    def remove_attribution_link_from_url_if_present(self, youtube_url):
        o = urlparse(youtube_url)
        query = urllib.parse.parse_qs(o.query)

        if 'a' in query and 'u' in query:  #if 'attribution_link' in query:
            u=query['u'][0]
            #log('   u  '+ repr(u))
            #replace the attribution link
            return '{scheme}://{netloc}{path}'.format(scheme=o.scheme, netloc=o.netloc,path=u)
        return youtube_url

    def get_playable_url(self, media_url='', is_probably_a_video=False ):
        if not media_url:
            media_url=self.media_url

        o = urlparse(media_url)
        query = urllib.parse.parse_qs(o.query)

        self.media_url=self.remove_attribution_link_from_url_if_present(media_url)

        self.url_type, id_from_url=self.get_video_channel_user_or_playlist_id_from_url( self.media_url )

        if self.url_type=='video':
            self.video_id=id_from_url
            self.get_thumb_url() #there is no request penalty for getting yt thumb url so we do it here
            self.link_action, playable_url=self.return_action_and_link_tuple_accdg_to_setting_wether_to_use_addon_for_youtube(self.video_id)

            #some youtube links take a VERY long time for youtube_dl to parse. we simplify it by getting the video id and using a simpler url
            #BUT if there is a time skip code in the url, we just pass it right through. youtube-dl can handle this part.
            #   time skip code comes in the form of ?t=122  OR #t=1m45s OR ?t=2:43
            if 't' in query or '#t=' in media_url:
                return media_url, self.TYPE_VIDEO
            else:
                return playable_url, self.TYPE_VIDEO
        elif self.url_type in ['channel','playlist','user']:
            log("    %s_ID=%s <--%s" %( self.url_type, repr(id_from_url), self.media_url) )
            self.link_action='listRelatedVideo'
            return media_url, self.TYPE_VIDS
        else:
            self.link_action='playYTDLVideo'
            return media_url, self.TYPE_VIDEO

    @classmethod
    def get_video_channel_user_or_playlist_id_from_url(self, youtube_url):
        youtube_url=self.remove_attribution_link_from_url_if_present(youtube_url)

        video_id=self.get_video_id( youtube_url )
        if video_id:
            return 'video', video_id
        else:
            channel_id=self.get_channel_id_from_url( youtube_url )
            user_id=self.get_user_id_from_url( youtube_url )
            playlist_id=self.get_playlist_id_from_url( youtube_url )
            #log( '  1:'+repr(channel_id) +'  2:'+ repr(user_id)+'  3:'+repr(playlist_id))
            if channel_id:
                return 'channel', channel_id
            elif playlist_id:
                return 'playlist', playlist_id
            elif user_id:
                return 'user', user_id
        return '',''
    @classmethod
    def return_action_and_link_tuple_accdg_to_setting_wether_to_use_addon_for_youtube(self, video_id):
        link_actn=''
        link_=''

        if video_id:
            if use_addon_for_youtube:
                link_actn=self.DI_ACTION_PLAYABLE
                link_="plugin://plugin.video.youtube/play/?video_id=" + video_id
            else:
                link_actn=self.DI_ACTION_YTDL
                #some youtube links take a VERY long time for youtube_dl to parse. we simplify it by getting the video id and using a simpler url
                #BUT if there is a time skip code in the url, we just pass it right through. youtube-dl can handle this part.
                #   time skip code comes in the form of ?t=122  OR #t=1m45s OR ?t=2:43
                link_=self.build_youtube_url_with_video_id(video_id)
            #log('    returning:{0} {1}'.format(link_actn, link_))
            return link_actn, link_
    @classmethod
    def build_youtube_url_with_video_id(self,video_id):
        return "http://youtube.com/v/{0}".format(video_id)
    @classmethod
    def get_video_id(self, yt_url):
        #video_id_regex=re.compile('(?:youtube(?:-nocookie)?\.com/(?:\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&;]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})', re.DOTALL)
        #added parsing for video_id in kodi_youtube_plugin url
        video_id_regex=re.compile('(?:youtube(?:-nocookie)?\.com/(?:\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&;]v=)|youtu\.be\/|plugin:\/\/plugin\.video\.youtube\/play\/\?video_id=)([a-zA-Z0-9_-]{11})', re.DOTALL)
        video_id=''
        match = video_id_regex.findall(yt_url)
        if match:
            video_id=match[0]
        else:
            #log('    second parsing for video id:'+yt_url)
            #for parsing this: https://www.youtube.com/attribution_link?a=y08k0cdNBKw&u=%2Fwatch%3Fv%3DQOVrrL5KtsM%26feature%3Dshare%26list%3DPLVonsjaXkSpfuIv02l6IM1pN1Z3IfXWUW%26index%3D4
            o = urlparse(yt_url)
            query = urllib.parse.parse_qs(o.query)
            if 'a' in query and 'u' in query:   #if all (k in query for k in ("a","u")):
                u=query['u'][0]
                #log('   u  '+ repr(u)) #  <--  /watch?v=QOVrrL5KtsM&feature=share&list=PLVonsjaXkSpfuIv02l6IM1pN1Z3IfXWUW&index=4
                match = video_id_regex.findall('youtube.com'+u)
                if match:
                    video_id=match[0]
                else:
                    log("    Can't get youtube video id:"+yt_url)
        return video_id

    @classmethod
    def get_channel_id_from_url(self, yt_url):
        channel_id=''
        channel_id_regex=re.compile('(?:https?:\/\/)?(?:www\.)?youtube\.com\/(?:channel\/)([a-zA-Z0-9\-_]{1,})', re.DOTALL)
        match = channel_id_regex.findall(yt_url)
        if match:
            channel_id=match[0]
        #log('yt channelID='+repr(channel_id))
        return channel_id
    @classmethod
    def get_user_id_from_url(self, yt_url):
        channel_id=''
        channel_id_regex=re.compile('(?:https?:\/\/)?(?:www\.)?youtube\.com\/(?:user\/)([a-zA-Z0-9\-_]{1,})', re.DOTALL)
        match = channel_id_regex.findall(yt_url)
        if match:
            channel_id=match[0]
        #log('yt channelID='+repr(channel_id))
        return channel_id
    @classmethod
    def get_playlist_id_from_url(self, youtube_url):
        o = urlparse(youtube_url)
        query = urllib.parse.parse_qs(o.query)

        playlist_id=query.get('list',None)
        if playlist_id:
            return playlist_id[0]


    def get_thumb_url(self):
        """
            Each YouTube video has 4 generated images. They are predictably formatted as follows:

            http://img.youtube.com/vi/<insert-youtube-video-id-here>/0.jpg
            http://img.youtube.com/vi/<insert-youtube-video-id-here>/1.jpg
            http://img.youtube.com/vi/<insert-youtube-video-id-here>/2.jpg
            http://img.youtube.com/vi/<insert-youtube-video-id-here>/3.jpg

            The first one in the list is a full size image and others are thumbnail images. The default thumbnail image (ie. one of 1.jpg, 2.jpg, 3.jpg) is:
            http://img.youtube.com/vi/<insert-youtube-video-id-here>/default.jpg

            For the high quality version of the thumbnail use a url similar to this:    http://img.youtube.com/vi/<insert-youtube-video-id-here>/hqdefault.jpg
            There is also a medium quality version of the thumbnail, similar to the HQ: http://img.youtube.com/vi/<insert-youtube-video-id-here>/mqdefault.jpg
            For the standard definition version of the thumbnail, use similar to this:  http://img.youtube.com/vi/<insert-youtube-video-id-here>/sddefault.jpg
            For the maximum resolution version of the thumbnail use similar to this:    http://img.youtube.com/vi/<insert-youtube-video-id-here>/maxresdefault.jpg
            All of the above urls are available over https too. Just change http to https in any of the above urls. Additionally, the slightly shorter hostname i3.ytimg.com works in place of img.youtube.com in the example urls above.

            #http://stackoverflow.com/questions/2068344/how-do-i-get-a-youtube-video-thumbnail-from-the-youtube-api
        """
        quality0123=1
        if not self.video_id:
            self.video_id=self.get_video_id(self.media_url)

        if self.video_id:
            self.thumb_url='http://img.youtube.com/vi/%s/%d.jpg' %(self.video_id,quality0123)
            self.poster_url='http://img.youtube.com/vi/%s/%d.jpg' %(self.video_id,0)

        return self.thumb_url

    def get_links_in_description(self, return_channelID_only=False):
        links=[]
        self.video_id=self.get_video_id( self.media_url )
        youtube_api_key=self.ret_api_key()
        if self.video_id:
            # Get info for this YouTube video, need the channel id for later
            query_params = {
                'key': youtube_api_key,
                'id': self.video_id,
                'fields':'items(snippet(channelId,title,description))',  #use '*' to get all fields
                'part': 'id,snippet',
            }

            api_url='https://www.googleapis.com/youtube/v3/videos?'+urllib.parse.urlencode(query_params)
            r = self.requests_get(api_url)
            #log(r.text)
            j=r.json()   #.loads(r.text)  #j=json.loads(r.text.replace('\\"', '\''))
            description=clean_str(j, ['items',0,'snippet','description'])
            channel_id=clean_str(j, ['items',0,'snippet','channelId'])
            if return_channelID_only:
                return channel_id
            #log(description)
            #log('***channel_id:'+channel_id)
            #links_from_description=self.get_first_url_from(description, return_all_as_list=True)

            text_and_links_tuple_list=self.split_text_into_links(description)

            if text_and_links_tuple_list:
                for text, link in text_and_links_tuple_list:
                    ld=parse_reddit_link(link, assume_is_video=False, needs_preview=False )  #setting needs_preview=True slows things down
                    if ld:
                        links.append( {'title': text,
                                        'type': ld.media_type,
                                        'description': text,
                                        'url': ld.playable_url if ld.playable_url else link,
                                        'thumb':ld.thumb,
        #                                'isPlayable':'true',
                                        'link_action':ld.link_action,
                                        'video_id':ld.video_id,
                                        }  )
                    else:
                        links.append( {'title': text,
                                        'type': self.TYPE_UNKNOWN,
                                        'description': text,
                                        'url': link,
                                        }  )
                self.assemble_images_dictList(links)
                return self.dictList
        else:
            log("  can't get video id")
            if return_channelID_only:
                channel_id=self.get_channel_id_from_url( self.media_url )
                log("    got channel id:"+channel_id)
                return channel_id

    def ret_api_key(self):
        youtube_api_key = addon.getSetting("youtube_api_key")
        if not youtube_api_key:
            youtube_api_key=self.api_key
        return youtube_api_key

    def ret_album_list(self, type_='related', search_string=None):
        youtube_api_key=self.ret_api_key()
        links=[]
        query_params={}

        self.url_type, id_from_url=self.get_video_channel_user_or_playlist_id_from_url( self.media_url )

        if type_=='channel':  #here, user specifically asked to show videos in channel via context menu
            channel_id=self.get_links_in_description(return_channelID_only=True)
            if not channel_id:
                raise ValueError('Could not get channel_id')
            request_action, query_params = self.build_query_params_for_channel_videos(youtube_api_key,channel_id)
        elif type_=='playlist':  #here, user specifically asked to show videos in playlist via context menu
            playlist_id=self.get_playlist_id_from_url( self.media_url )
            request_action, query_params = self.build_query_params_for_playlist_videos(youtube_api_key,playlist_id)
        elif type_=='playlists':  #here, user specifically asked to show playlists in the channel. the url is required to be a channel (channel_url built in ContextMenus.py)
            channel_id=self.get_channel_id_from_url( self.media_url )
            request_action, query_params = self.build_query_params_for_playlists_in_channel(youtube_api_key,channel_id)
        elif type_=='search':  #here, user specifically asked to search
            request_action, query_params = self.build_query_params_for_search(youtube_api_key,search_string)

        else:  #in this portion, we determine if we will determine what kind of related videos to list by the url provided. usually it is related by videoid, but we can also handle channel, user or playlist url's
            if self.url_type=='video':
                request_action, query_params = self.build_query_params_for_related_to_videoId(youtube_api_key,id_from_url)
            elif self.url_type=='channel':
                #this requests videos in channel
                request_action, query_params = self.build_query_params_for_channel_videos(youtube_api_key,id_from_url)
                #this requests playlists in channel
                #request_action, query_params = self.build_query_params_for_playlists_in_channel(youtube_api_key,id_from_url)
                #self.get_channel_info(id_from_url)
            elif  self.url_type=='playlist':
                request_action, query_params = self.build_query_params_for_playlist_videos(youtube_api_key,id_from_url)
            elif  self.url_type=='user':
                #https://stackoverflow.com/questions/22613903/youtube-api-v3-get-list-of-users-videos
                channel_id,uploads=self.get_id_from_user(id_from_url)
                #request_action, query_params = self.build_query_params_for_channel_videos(youtube_api_key,channel_id) #100 quota cost
                request_action, query_params = self.build_query_params_for_playlist_videos(youtube_api_key,uploads)    #  2 quota cost

        if query_params:
            links.extend( self.get_video_list(request_action, query_params) )

            #log(repr(links))
            self.assemble_images_dictList(links)
            return self.dictList
    @classmethod
    def build_query_params_for_channel_videos(self,youtube_api_key, channel_id):
        return  'search', {
                'key': youtube_api_key,
                'fields':'items(kind,id(videoId),snippet(publishedAt,channelTitle,channelId,title,description,thumbnails(medium)))',
                'type': 'video',         #video,channel,playlist.
    #            'kind': 'youtube#video',
                'maxResults': '50',      # Acceptable values are 0 to 50
                'part': 'snippet',
                'order': 'date',
                'channelId': channel_id,
            }
    @classmethod
    def build_query_params_for_related_to_videoId(self,youtube_api_key,video_id):
        return  'search', {
                'key': youtube_api_key,
                'fields':'items(kind,id(videoId),snippet(publishedAt,channelTitle,channelId,title,description,thumbnails(medium)))',
                'type': 'video',         #video,channel,playlist.
                'maxResults': '50',      # Acceptable values are 0 to 50
                'part': 'snippet',
                'relatedToVideoId': video_id,  #if the relatedToVideoId parameter is set, the only other supported parameters are part, maxResults, pageToken, regionCode, relevanceLanguage, safeSearch, type (which must be set to video), and fields.
                'safeSearch':'moderate' if hide_nsfw else 'none',
            }
    @classmethod
    def build_query_params_for_search(self,youtube_api_key,search_string,type_='video'):
        from .utils import ret_bracketed_option
        #specify different results by adding order_option in square brackets in the search string.
        stripped_string, order_option=ret_bracketed_option(search_string)  #developer feature: specify the order in search parameter "[date]" etc.
        if order_option:
            if order_option.lower() in['date','rating','relevance','title','videocount','viewcount']:
                log('  youtube search:using special order option [{0}]'.format(order_option))
            else:
                log('  youtube search:unsupported order option [{0}]'.format(order_option))
                order_option='relevance'
                stripped_string=search_string
        else:
            order_option='relevance'

        return  'search', {
                'key': youtube_api_key,
                'fields':'items(kind,id(videoId),snippet(publishedAt,channelTitle,channelId,title,description,thumbnails(medium)))',
                'type': type_,         #video,channel,playlist.
                'maxResults': '50',      # Acceptable values are 0 to 50
                'part': 'snippet',
                'order': order_option, #date,rating,relevance,title,videoCount,viewCount
                'q': stripped_string,
                'safeSearch':'moderate' if hide_nsfw else 'none',
            }
    @classmethod
    def build_query_params_for_playlist_videos(self,youtube_api_key, playlist_id):
        return  'playlistItems', {
                'key': youtube_api_key,
                #'fields':'items(id(videoId),snippet(publishedAt,channelId,title,description,thumbnails(medium)))', can't specify fields for playlistItems
                'type': 'video',         #video,channel,playlist.
                'maxResults': '50',      # Acceptable values are 0 to 50
                'part': 'snippet',
                'playlistId': playlist_id,
            }
    @classmethod
    def build_query_params_for_user_videos(self,youtube_api_key, user_id):
        return  'channels', {
                'key': youtube_api_key,
                'maxResults': '50',      # Acceptable values are 0 to 50
                'part': 'snippet,contentDetails',
                'forUsername': user_id,
            }
    @classmethod
    def build_query_params_for_playlists_in_channel(self,youtube_api_key, channel_id):
        return  'playlists', {
                'key': youtube_api_key,
                'maxResults': '50',      # Acceptable values are 0 to 50
                'part': 'snippet,contentDetails',
                'channelId': channel_id,
            }
    @classmethod
    def build_query_params_for_get_channel_info(self,youtube_api_key, channel_id):
        return  'channels', {
                'key': youtube_api_key,
                'part': 'snippet,brandingSettings',  #https://developers.google.com/youtube/v3/docs/channels#resource
                'id': channel_id,
            }
    @classmethod
    def get_id_from_user(self,user_id):
        query_params = {
            'key': self.ret_api_key(),
            'part': 'snippet,contentDetails',
            'forUsername': user_id,
        }
        api_url='https://www.googleapis.com/youtube/v3/channels?'+urllib.parse.urlencode(query_params)
        r = self.requests_get(api_url)
        #log(r.text)
        j=r.json()   #.loads(r.text)  #j=json.loads(r.text.replace('\\"', '\''))
        channel_id=clean_str(j, ['items',0,'id'])
        uploads=clean_str(j, ['items',0,'contentDetails','relatedPlaylists','uploads'])
        #log('channel_id:'+repr(channel_id) +' uploads:'+ repr(uploads))
        return channel_id,uploads

    def get_channel_info(self,channel_id, entry_name=None):
        #return format similar to get_subreddit_info() in reddit.py
        #this is used to get the channel info/banner for the index page
        link_action, query_params=self.build_query_params_for_get_channel_info(self.ret_api_key(),channel_id)

        api_url='https://www.googleapis.com/youtube/v3/{0}?{1}'.format(link_action,urllib.parse.urlencode(query_params))
        #log(api_url)
        r = self.requests_get(api_url)
        j=r.json()
        #log(repr(j))

        j=j.get('items')[0]

        #videoId=clean_str(j, ['snippet','resourceId','videoId'])
        channel_info={}
        if 'brandingSettings' in j:
            title=clean_str(j, ['brandingSettings','channel','title'])
            channel_info.update( {'entry_name':entry_name,               #used as key when searching
                               'display_name':title,
                               'banner_img': clean_str(j, ['brandingSettings','image','bannerImageUrl']),   #this one is rectangular
                               'icon_img': clean_str(j, ['snippet','thumbnails','default','url']),
                               'header_img': clean_str(j, ['brandingSettings','image','bannerTvImageUrl']), #bannertv is square
                               'title':title,
                               'header_title':title,
                               'public_description':clean_str(j, ['brandingSettings','channel','description']),
                               #'subreddit_type':j.get('subreddit_type'),
                               #'subscribers':j.get('subscribers'),
                               'created':clean_str(j, ['snippet','publishedAt']),        #public, private
                               'over18':None,
                               } )
            import pprint
            log( pprint.pformat(channel_info, indent=1) )
            return channel_info

    def ret_videoId_list_from(self,items_from_api_response):
        video_ids=[]
        for i in items_from_api_response:
            kind=clean_str(i, ['kind'])
            if kind in ['youtube#searchResult','youtube#playlistItem']: #if request_action in ['search','playlistItems']:
                if kind=='youtube#searchResult':
                    videoId=clean_str(i, ['id','videoId'])
                elif kind=='youtube#playlistItem':    #videoId is located somewhere else in the json if using playlistItems
                    videoId=clean_str(i, ['snippet','resourceId','videoId'])
                video_ids.append(videoId)
        return video_ids
    def get_video_durations(self,youtube_api_key,videoIds):
        from .utils import ytDurationToSeconds
        durations=[]
        query_params={'key': youtube_api_key,
                'part': 'contentDetails',
                'id': ",".join(videoIds),            #','.join(map(str, myList))#if the list contains numbers
            }
        api_url='https://www.googleapis.com/youtube/v3/{0}?{1}'.format("videos",urllib.parse.urlencode(query_params))
        r = self.requests_get(api_url)
        j=r.json()
        #log(repr(j))
        for i in j.get('items'):
            d=clean_str(i, ['contentDetails','duration'],'')
            durations.append(ytDurationToSeconds(d))
            #import iso8601
            #iso8601.parse_duration(d)
        return durations
    def get_video_durations_dict(self,youtube_api_key,items_from_api_response):
        video_ids=self.ret_videoId_list_from(items_from_api_response)
        #log('aaaaaaaaaa'+repr(video_ids))
        durations=self.get_video_durations(youtube_api_key, video_ids)
        #log('aaaaaaaaaa'+repr(durations))
        vnd=dict(zip(video_ids,durations))
        del video_ids[:]
        del durations[:]
        return vnd

    def get_video_list(self, request_action, query_params, direct_api_request_url=None, prev_page=1 ):
        from .utils import set_query_field, seconds_to_hms
        links=[]
        if direct_api_request_url:
            log('direct api request url provided:'+repr(direct_api_request_url))
            api_url=direct_api_request_url
        else:
            api_url='https://www.googleapis.com/youtube/v3/{0}?{1}'.format(request_action,urllib.parse.urlencode(query_params))
        r = self.requests_get(api_url)
        j=r.json()
        #log(repr(j))

        nextPageToken=clean_str(j, ['nextPageToken'])
        totalResults=clean_str(j, ['pageInfo','totalResults'])
        #log('nextPageToken={0}   totalResults={1}'.format(nextPageToken,totalResults))
        items=j.get('items')
        all_same_channel=all_same([clean_str(i, ['snippet','channelTitle']) for i in items])
        #log(repr(channels))
        videoId_and_durations=self.get_video_durations_dict(self.api_key,items)
        #log('videoId_and_durations:'+repr(videoId_and_durations))

        for i in items:
            #snippet has: publishedAt channelId title description thumbnails{}
            kind=clean_str(i, ['kind'])
            #log(repr(kind))
            if kind in ['youtube#searchResult','youtube#playlistItem']: #if request_action in ['search','playlistItems']:
                if kind=='youtube#searchResult':
                    videoId=clean_str(i, ['id','videoId'])
                elif kind=='youtube#playlistItem':    #videoId is located somewhere else in the json if using playlistItems
                    videoId=clean_str(i, ['snippet','resourceId','videoId'])
                link_action, playable_url=self.return_action_and_link_tuple_accdg_to_setting_wether_to_use_addon_for_youtube(videoId)

            elif kind=='youtube#playlist': # if request_action=='playlists':     #these are playlists. we construct playlist url's
                videoId=''
                playlist_id=clean_str(i, ['id'])
                link_action='listRelatedVideo'
                playable_url="https://www.youtube.com/playlist?list={0}".format(playlist_id)

            #log('video id:'+repr(videoId))
            publishedAt=clean_str(i, ['snippet','publishedAt'])
            pretty_date=pretty_datediff_wrap(publishedAt, format_string="%Y-%m-%dT%H:%M:%S.000Z")
            #log('publishedAt:'+repr(publishedAt) + ' which is ' + pretty_date)
            set_='' #infolabels set(name of the collection)  i'll use this to store "14 videos" for playlist
            channel_id=clean_str(i, ['snippet','channelId'])
            title=clean_str(i, ['snippet','title'])
            description=clean_str(i, ['snippet','description'])
            #thumb1280=clean_str(i, ['snippet','thumbnails','maxres']) #1280x720
            thumb640=clean_str(i, ['snippet','thumbnails','standard','url']) #640x480
            thumb480=clean_str(i, ['snippet','thumbnails','high','url'])   #480x360
            thumb320=clean_str(i, ['snippet','thumbnails','medium','url']) #320x180
            channelTitle=clean_str(i, ['snippet','channelTitle'])
            items_in_playlist=clean_str(i, ['contentDetails','itemCount'],default=0) #exists only for playlist. does not exist in searchResult or playlistItem
            duration=videoId_and_durations.get(videoId)
            duration_hms=seconds_to_hms(duration)
            if items_in_playlist==0: #we're supposed to use listitem.duration for this field. but kodi <18 only formats this field in mmm. kodi 18 formats this to hh:mm:ss
                set_=duration_hms    # we resort to formatting it ourselves and putting it in a different field(set) that is also displayed in the gui on the same location 
            if items_in_playlist==1:
                set_="{0} video".format(items_in_playlist)
            elif items_in_playlist>1:
                set_="{0} videos".format(items_in_playlist)
            if not all_same_channel: #if all videos in the list is not from the same channel, add channel name beside date
                pretty_date="{0} [I]@{1}[/I]".format(pretty_date,channelTitle)

            #log('  link_action:'+link_action +' -->'+ playable_url)
            links.append( {'title': title,
                            'type': self.TYPE_VIDEO,
                            'label2': pretty_date,
                            'description': description,
                            'url': playable_url,
                            'thumb': next((i for i in [thumb320,thumb480,thumb640] if i ), ''), #there are instances where a playlist will have a thumbnail that has three dots. (default no image thumbnail)
                            'isPlayable': 'true' if link_action==self.DI_ACTION_PLAYABLE else 'false',
                            'link_action':link_action,
                            'channel_id':channel_id,
                            'channel_name':channelTitle,
                            'video_id':videoId,
                            #'duration':duration,
                            'set':set_,
                            }  )
        if nextPageToken:
            new_url_with_next_page=set_query_field(api_url,'pageToken',nextPageToken,True)
            links.append( {'title': "Page {0}".format(prev_page + 1), #'Show more',
                            'type': self.TYPE_ALBUM,
                            'label2': None,
                            'description': "More items from total:{0}".format(totalResults),
                            'url': new_url_with_next_page,
                            'thumb': 'DefaultFolderNextSquare.png',
                            'isPlayable': 'false',
                            'link_action':'listMoreVideo',
                            'channel_id':None,
                            'channel_name':None,
                            'video_id':None,
                            }  )
        return links

class ClassImgur(sitesBase):
    regex='(imgur.com)'

    #use this header for interacting with the imgur api
    #get client id by registering at https://api.imgur.com/oauth2/addclient
    #request_header={ "Authorization": "Client-Id a594f39e5d61396" }
    request_header={ "Authorization": "Client-Id 7b82c479230b85f" }

    #when is_an_album() is called to check a /gallery/ link, we ask imgur; it returns more info than needed, we store some of it here
    is_an_album_type=""
    is_an_album_link=""
    images_count=0
    image_url_of_a_single_image_album=''

    def get_album_thumb(self, media_url):

        album_id=self.get_album_or_gallery_id(media_url)

        request_url="https://api.imgur.com/3/album/"+album_id
        #log("    get_album_thumb---"+request_url )
        r = self.requests_get(request_url, headers=ClassImgur.request_header)
        #log(r.text)
        j = r.json()    #j = json.loads(r.text)

        thumb_image_id=j['data'].get('cover')
        #images_count=j['data'].get('images_count')

        if thumb_image_id:
            #we're not guaranteed that it is jpg but it seems to work with png files as well...
            return 'http://i.imgur.com/'+thumb_image_id+'m.jpg', 'http://i.imgur.com/'+thumb_image_id+'l.jpg'

            #for i in j['data']['images']:
            #    if thumb_image_id == i.get('id'):
            #        thumb_image=i.get('link')
            #        thumb_w=i.get('width')
            #        thumb_h=i.get('height')
        return "",""

    def is_an_album(self, media_url):
        #determins if an imgur url is an album
        r=None
        request_url=''
        media_url=media_url.split('?')[0] #get rid of the query string

        #links with an /a/ is an album e.g: http://imgur.com/a/3SaoS
        if "/a/" in media_url:
            album_id=media_url.split("/a/",1)[1]
            #sometimes album contain only one image. we check if this is true and results in many requests to imgur and SLOWs down directory listing for album-heavy subreddits like r/DIY
            request_url="https://api.imgur.com/3/album/"+album_id
            r=self.requests_get(request_url, headers=ClassImgur.request_header)
        else:
            #links with /gallery/ is trickier. sometimes it is an album sometimes it is just one image
            if '/gallery/' in media_url:
                r=self.get_gallery_info(media_url)

        if r:
            #if 'Ji0I' in media_url: log(r.text)
            j = r.json()
            #log(" is_album=" + str(j['data']['is_album'])    )
            #log(" in_gallery=" + str(j['data']['in_gallery'])    )
            #we already incurred the bandwidth asking imgur about album info. might as well use the data provided
            jdata=j.get('data')
            if jdata:
                self.is_an_album_type= jdata.get('type')   #"image/png" , "image\/gif"
                self.is_an_album_link= jdata.get('link')

            #this link (https://imgur.com/gallery/VNPcuYP) returned an extra 'h' on j['data']['link']  ("http:\/\/i.imgur.com\/VNPcuYPh.gif")
            #causing the video not to play. so, we grab mp4 link if present
                if jdata.get('mp4'):
                    self.is_an_album_link= jdata.get('mp4')

            self.images_count=jdata.get('images_count')
            if self.images_count:
                #log('    imgur album images count ' + repr(self.images_count))
                if self.images_count == 1:
                    #if there is an mp4 tag in the json, use that value.
                    #     there have been instances where the 'link' tag leads to a gif. that does not have the same name as the .mp4 equivalent (it has an extra 'h' at the end)
                    #     so renaming by changing the .gif to .mp4 wouldn't work.
                    #        credit to mac1202 2/26/2017 for finding this bug.
                    if jdata.get('images')[0].get('mp4'):
                        self.image_url_of_a_single_image_album=jdata.get('images')[0].get('mp4')
                    else:
                        self.image_url_of_a_single_image_album=jdata.get('images')[0].get('link')
                    #log( '  *** album with 1 image ' + self.image_url_of_a_single_image_album)
                    return False
                else:
                    #data is already there, just parse it
                    images=self.ret_images_dict_from_album_json(j)
                    self.assemble_images_dictList(images)
                    return True
            else:
                #sometimes we receive a single image data (no images_count)  is_album=false
                self.image_url_of_a_single_image_album=self.is_an_album_link
                return False
            #sometimes 'is_album' key is not returned, so we also check for 'in_gallery'
    #            if 'is_album' in j['data']:
    #                is_album_key=jdata.get('is_album')
    #                return is_album_key
    #            else:
    #                try:in_gallery_key=jdata.get('in_gallery')
    #                except: in_gallery_key=False
    #                return in_gallery_key
    #        #else: #status code not 200... what to do...
    #        #    return True  #i got a 404 on one item that turns out to be an album when checked in browser. i'll just return true
        else:
            return False

    def get_gallery_info(self, media_url):
        gallery_name = media_url.split("/gallery/",1)[1]
        if gallery_name=="":
            return False

        request_url="https://api.imgur.com/3/gallery/"+gallery_name

        #log("    imgur:check if album- request_url---"+request_url )
        try:
            r = self.requests_get(request_url, headers=ClassImgur.request_header)
        except requests.exceptions.HTTPError:
            #http://imgur.com/gallery/Ji0IWhG this link has /gallery/ but returns 404 if asked as gallery
            request_url="https://api.imgur.com/3/image/"+gallery_name
            #log('      Trying a different query:'+request_url)
            try:
                r = self.requests_get(request_url, headers=ClassImgur.request_header)
            except requests.exceptions.HTTPError:
                #https://imgur.com/gallery/knbXW   this link has is not "image" nor "gallery" but is "album"
                request_url="https://api.imgur.com/3/album/"+gallery_name
                #log('      Trying a different query:'+request_url)
                r = self.requests_get(request_url, headers=ClassImgur.request_header)
                #there has to be a better way to do this...
        return r

    def ask_imgur_for_link(self, media_url):
        #sometimes, imgur links are posted without the extension(gif,jpg etc.). we ask imgur for it.
        #log("  ask_imgur_for_link: "+media_url )

        media_url=media_url.split('?')[0] #get rid of the query string
        img_id=media_url.split("com/",1)[1]  #.... just get whatever is after "imgur.com/"   hope nothing is beyond the id
        #log("    ask_imgur_for_link: "+img_id )

        #6/30/2016: noticed a link like this: http://imgur.com/topic/Aww/FErKmLG
        if '/' in img_id:
            #log("  split_ask_imgur_for_link: "+ str( img_id.split('/')) )
            img_id = img_id.split('/')[-1]     #the -1 gets the last item on the list returned by split

        if img_id:
            request_url="https://api.imgur.com/3/image/"+img_id
            r = self.requests_get(request_url, headers=ClassImgur.request_header)
            j=r.json()

            if j['data'].get('mp4'):
                return j['data'].get('mp4')
            else:
                return j['data'].get('link')

    def get_thumb_url(self):
        return self.get_thumb_from_url()

    def get_thumb_from_url(self,link_url=''):
        #return the thumbnail url given the image url
        #accomplished by appending a 'b' at the end of the filename
        #this won't work if there is a '/gallery/' in the url

        thumbnail_type='b'
        #possible thumbnail_types
        #    s = Small Square (90�90)
        #    b = Big Square (160�160)
        #    t = Small Thumbnail (160�160)
        #    m = Medium Thumbnail (320�320)
        #    l = Large Thumbnail (640�640)
        #    h = Huge Thumbnail (1024�1024)
        if not link_url:
            link_url=self.original_url

        if self.thumb_url:
            return self.thumb_url

        is_album=self.is_an_album(link_url)
        #log('  imgur says is_an_album:%s %s' %( str(is_album), link_url) )
        if is_album:
            #log('      getting album thumb for ' + link_url)
            self.thumb_url, self.poster_url= self.get_album_thumb(link_url)
            return self.thumb_url

        o=urlparse(link_url)
        filename,ext=parse_filename_and_ext_from_url(link_url)
        #log("file&ext------"+filename+"--"+ext+"--"+o.netloc )

        #imgur url's sometimes do not have an extension and we don't know if it is an image or video
        if ext=="":
            #log("ret_thumb_url["+ o.path[1:] ) #starts with / use [1:] to skip 1st character
            filename = o.path[1:]
            ext = 'jpg'
        elif ext in ['gif', 'gifv', 'webm', 'mp4']:
            ext = 'jpg'

        #return o.scheme+"://"+o.netloc+"/"+filename+ thumbnail_type +"."+ext
        thumb= ("%s://%s/%s%c.%s" % ( o.scheme, o.netloc, filename, thumbnail_type, ext ) )
        #log('      imgur thumb:' + thumb)

        return thumb

    def get_album_or_gallery_id(self,album_url):
        #you need to have determined that the url is album
        match = re.compile(r'imgur\.com/(?:a|gallery)/(.*)/?', re.DOTALL).findall(album_url)
        if match:
            album_name = match[0]  #album_url.split("/a/",1)[1]
        else:
            log(r"ret_album_list: Can't determine album name from["+album_url+"]" )
            album_name=""
        return album_name

    def ret_album_list(self, album_url):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem
        # see ret_thumb_url for thumbnail_size_code values

        #album_url="http://imgur.com/a/fsjam"
        #sometimes album name has "/new" at the end

        album_name = self.get_album_or_gallery_id(album_url)

        if album_name=="":
            log(r"ret_album_list: Can't determine album name from["+album_url+"]" )
            return self.dictList

        #log('album name:'+album_name+' from ['+album_url+']')
        request_url="https://api.imgur.com/3/album/"+album_name+"/images"
        #log("listImgurAlbum-request_url---"+request_url )
        r = self.requests_get(request_url, headers=ClassImgur.request_header)

        images=[]

        if r.status_code==200:  #http status code 200 = success
            #log(r.text)
            j = r.json()   #json.loads(r.text)

            images=self.ret_images_dict_from_album_json(j)
            #for i in images: log( '##' + repr(i))
            self.assemble_images_dictList(images)
        else:
            self.clog(r.status_code ,request_url)

        return self.dictList

    def ret_images_dict_from_album_json(self, j):
        images=[]
        #2 types of json received:
        #first, data is an array of objects
        #second, data has 'images' which is the array of objects
        if 'images' in j['data']:
            imgs=j.get('data').get('images')
        else:
            imgs=j.get('data')

        for _, entry in enumerate(imgs):
            link_type=entry.get('type')         #image/jpeg
            if link_type=='image/gif':
                media_url=entry.get('mp4')
                media_type=self.TYPE_VIDEO
                isPlayable='true'
            else:
                media_url=entry.get('link')
                media_type=self.TYPE_IMAGE
                isPlayable='false'
            width    =entry.get('width')
            height   =entry.get('height')
            title    =entry.get('title')
            descrip  =entry.get('description')
            media_thumb_url=self.get_thumb_from_url(media_url)

            images.append( {'title': title,
                            'type': media_type,
                            'description': descrip,
                            'url': media_url,
                            'thumb': media_thumb_url,
                            'width': width,
                            'height': height,
                            'isPlayable':isPlayable,
                            }  )
        return images

    def media_id(self, media_url):
        #return the media id from an imbur link
        pass

    def get_playable_url(self, media_url, is_probably_a_video): #is_probably_a_video means put video extension on it if media_url has no ext
        webm_or_mp4='.mp4'  #6/18/2016  using ".webm" has stopped working
        media_url=media_url.split('?')[0] #get rid of the query string?
        is_album=self.is_an_album(media_url)
        if is_album:
            return media_url, sitesBase.TYPE_ALBUM
        else:
            if '/gallery/' in media_url:
                #media_url=media_url.replace("/gallery/","/")
                #is_an_album will ask imgur if a link has '/gallery/' in it and stores it in is_an_album_link
                media_url=self.is_an_album_link
                #log('      media_link from /gallery/: '+  media_url )

        #use the image link if there is only one image in an album/gallery
        if self.image_url_of_a_single_image_album:
            media_url=self.image_url_of_a_single_image_album

        _,ext=parse_filename_and_ext_from_url(media_url)

        if ext == "":
            media_url=self.ask_imgur_for_link(media_url)
            _,ext=parse_filename_and_ext_from_url(media_url)
            #below is a faster alternative but not as accurate.
            #if is_probably_a_video:  #reddit thinks this is a video
            #    media_url=media_url+ webm_or_mp4
            #    is_video=True
            #else:
            #    media_url=media_url+".jpg"
            #    is_video=False

        if ext in ['gif', 'gifv', 'mp4'] :   #NOTE: we're treating all mp4 links as gif and set them to loop playback
            media_url=media_url.replace(".gifv",webm_or_mp4) #can also use .mp4.  crass but this method uses no additional bandwidth.  see playImgurVideo
            media_url=media_url.replace(".gif",webm_or_mp4)  #xbmc won't play gif but replacing .webm works!
            #self.media_type=sitesBase.TYPE_VIDEO
            self.media_type=sitesBase.TYPE_GIF
            self.link_action=self.DI_ACTION_PLAYABLE

            self.thumb_url=media_url.replace(webm_or_mp4,'.jpg')
            self.poster_url=self.thumb_url
        elif ext in image_exts:    #image_exts = ['jpg','png', 'RAW', 'jpeg', 'tiff', 'tga', 'pcx', 'bmp']
            self.thumb_url=media_url
            self.poster_url=self.thumb_url

            self.media_type=sitesBase.TYPE_IMAGE
        else:
            self.media_type=sitesBase.TYPE_VIDEO
            self.link_action=self.DI_ACTION_PLAYABLE

        #log("    media url return=["+media_url+'] vid:' + str(is_video ))
        self.media_url=media_url
        return self.media_url, self.media_type

class ClassVidme(sitesBase):
    regex='(vid.me)'
    #request_header={ "Authorization": "Basic " + base64_encode($key . ':') }
    request_header={ "Authorization": "Basic aneKgeMUCpXv6FdJt8YGRznHk4VeY6Ps:" }

    def get_playable_url(self,media_url, is_probably_a_video=True):
        #https://docs.vid.me/#api-Video-DetailByURL
        #request_url="https://api.vid.me/videoByUrl/"+videoID
        request_url="https://api.vid.me/videoByUrl?url="+ urllib.parse.quote_plus( media_url )
        #log("vidme request_url---"+request_url )
        r = requests.get(request_url, headers=ClassVidme.request_header, timeout=REQUEST_TIMEOUT)
        #log(r.text)

        if r.status_code != 200:   #http status code 200 is success
            log("    vidme request failed, trying alternate method: "+ str(r.status_code))

            #try to get media id from link.
            #media_url='https://vid.me/Wo3S/skeletrump-greatest-insults'
            #media_url='https://vid.me/Wo3S'
            id_=re.findall( 'vid\.me/(.+?)(?:/|$)', media_url )   #***** regex capture to end-of-string or delimiter. didn't work while testing on https://regex101.com/#python but will capture fine

            request_url="https://api.vid.me/videoByUrl/" + id_[0]
            r = requests.get(request_url, headers=ClassVidme.request_header, timeout=REQUEST_TIMEOUT)
            #log(r.text)
            if r.status_code != 200:
                log("    vidme request still failed:"+ str(r.text) )
                t= r.json()
                raise Exception( str(r.status_code) + ' ' + t.get('error'))

        j = r.json()    #j = json.loads(r.text)
        vid_info=j.get('video')

        #for attribute, value in j.iteritems():
        #    log(  str(attribute) + '==' + str(value))
        status = vid_info.get( 'state' )
        #log( "    vidme video state: " + status ) #success / suspended / deleted
        if status != 'success':
            raise Exception( "vidme video: " +vid_info.get('state'))

        self.thumb_url=vid_info.get("thumbnail_url")

        #if 'ta6C' in media_url: log(r.text)
        self.link_action=self.DI_ACTION_PLAYABLE
        return ( vid_info.get('complete_url') ), sitesBase.TYPE_VIDEO

    def get_thumb_url(self):
        return self.thumb_url

#vine parsing broken
#class ClassVine(sitesBase):
#    regex='(vine\.co)'
#
#    def get_playable_url(self, media_url, is_probably_a_video=True):
#        contentUrl=''
#        #media_url='"image": "https://v.cdn.vine.co/r/videos/38B4A9174D1177703702723739648_37968e655a0.1.5.1461921223578533188.mp4.jpg?versionId=hv6zBo4kGHPH8NdQeJVo_JRGSVXV73Cc"'
#        #msp=re.compile('videos\/(.*?\.mp4)')
#        msp=re.compile('(https?://.*/videos/.*?\.mp4)')
#        match=msp.findall(media_url)
#        if match:
#            #the media_url from reddit already leads to the actual stream, no need to ask vine
#            log('    the media_url from reddit already leads to the actual stream [%s]' %match[0])
#            return media_url, sitesBase.TYPE_VIDEO   #return 'https://v.cdn.vine.co/r/videos/'+match[0]
#
#        #request_url="https://vine.co/oembed.json?url="+media_url   won't work. some streams can't be easily "got" by removing the .jpg at the end
#        request_url=media_url
#        #log("    %s get_playable_url request_url--%s" %( self.__class__.__name__, request_url) )
#        r = self.requests_get(request_url)
#        log( r.text)
#        """
#        #there are parsed characters(\u2122 etc.) in r.text that causes errors somewhere else in the code.
#        #matches the json script from the reply
#        json_match=re.compile('<script type=\"application\/ld\+json\">\s*([\s\S]*?)<\/script>' , re.DOTALL).findall(r.text)
#        if json_match:
#            #log(json_match[0])
#            #the text returned causes a json parsing error, we fix them below before decoding
#            #use this site to find out where the decoding failed https://jsonformatter.curiousconcept.com/
#            jt = json_match[0].replace('"name" : ,','"name" : "",').encode('ascii', errors='ignore')   #('utf-8')
#            j=json.loads(jt)
#            contentUrl=j['sharedContent']['contentUrl']
#            thumbnailUrl=j['sharedContent']['thumbnailUrl']
#
#        """
#        m_strm=re.compile('"contentUrl"\s:\s"(https?://.*?\.mp4.*?)"').findall(r.text)
#        if m_strm:
#            contentUrl=m_strm[0]
#            #log('matched:'+ contentUrl )
#        #m_thumb=re.compile('"thumbnailUrl"\s:\s"(https?://.*?\.jpg)\?').findall(r.text)
#        #if m_thumb:
#        #    thumbnailUrl=m_thumb[0]
#
#        self.link_action=self.DI_ACTION_PLAYABLE
#        return contentUrl, sitesBase.TYPE_VIDEO
#
#        #log('vine type %s thumbnail_url[%s]' %(type, thumbnail_url) )
#        return '',''
#
#    def get_thumb_url(self):
#        pass

class ClassVimeo(sitesBase):
    regex='(vimeo\.com/)'
    video_id=''

    def get_playable_url(self, media_url='', is_probably_a_video=False ):
        if not media_url:
            media_url=self.media_url

        self.get_video_id()

        if self.video_id:
            #if use_ytdl_for_yt:  #ytdl can also handle vimeo
            # (10/2/2016) --- please only use script.module.youtube.dl if possible and remove these dependencies.
            self.link_action=sitesBase.DI_ACTION_YTDL
            return media_url, self.TYPE_VIDEO
            #else:
            #self.link_action=self.DI_ACTION_PLAYABLE
            #return "plugin://plugin.video.vimeo/play/?video_id=" + self.video_id, self.TYPE_VIDEO
        else:
            log("    %s cannot get videoID %s" %( self.__class__.__name__, media_url) )
            #feed it to ytdl. sometimes link points to multiple streams: https://vimeo.com/mrmichaelrobinson/videos/
            self.link_action=sitesBase.DI_ACTION_YTDL
            return media_url, self.TYPE_VIDEO

    def get_video_id(self):
#         match = re.compile('vimeo.com/(.*)', re.DOTALL).findall(self.media_url)
#         if match:
#             log('      simple regex got:' + repr(match) )
#             self.video_id=match[0]
        match = re.compile('vimeo.com\/(?:channels\/(?:\w+\/)?|groups\/(?:[^\/]*)\/videos\/|album\/(?:\d+)\/video\/|)(\d+)(?:$|\/|\?)', re.DOTALL).findall(self.media_url)
        if match:
            #log('      long regex got:' + repr(match) )
            self.video_id=match[0]

    def get_thumb_url(self):
        #http://stackoverflow.com/questions/1361149/get-img-thumbnails-from-vimeo
        if not self.video_id:
            self.get_video_id()

        request_url='http://vimeo.com/api/v2/video/%s.json' % self.video_id
        #log(request_url)
        r = self.requests_get(request_url)
        #log(r.text)
        j=r.json()
        self.poster_url=j[0].get('thumbnail_large')
        self.thumb_url=self.poster_url
        #log( "   ***** thumbnail " + self.poster_url)

        return self.thumb_url

class ClassGiphy(sitesBase):
    regex='(giphy\.com)|(gph\.is)'
    #If your app is a form of a bot (ie. hubot), for internal purposes, open source, or for a class project,
    #  we highly recommend you institute the beta key for your app.
    #  Unless you're making thousands of requests per IP, you shouldn't have any issues.
    #The public beta key is "dc6zaTOxFJmzC”
    key='dc6zaTOxFJmzC'
    video_url=''
    video_id=''

    def get_playable_url(self, media_url, is_probably_a_video=True ):

        if 'gph.is' in media_url:
            log('    giphy short url detected:' + media_url)
            media_url=self.request_meta_ogimage_content(media_url)

        if 'media' in media_url:
            if 'giphy.gif' in media_url:
                self.media_url=media_url.replace('giphy.gif','giphy-loop.mp4')

                self.link_action=sitesBase.DI_ACTION_PLAYABLE
                log('    simple replace ' + self.media_url )
                return self.media_url, sitesBase.TYPE_VIDEO    #giphy auto loops x times

        if self.get_media_info():
            self.link_action=sitesBase.DI_ACTION_PLAYABLE
            return self.video_url, sitesBase.TYPE_VIDEO

        return '',''

    def get_media_info(self):
        if not self.video_id:
            self.get_video_id()
            log("      giphy id:" + self.video_id)

        if self.video_id:
            request_url="http://api.giphy.com/v1/gifs/%s?api_key=%s" %( self.video_id, self.key )
            #log('    Giphy request:'+ request_url)
            content = self.requests_get(request_url)
            j = content.json()
            #d=j.get('data')
            images=j.get('data').get('images')
            #log( pprint.pformat(images, indent=1) )

            #log('      vid=%s' %  images.get('original').get('mp4')  )
            #log('     loop=%s' %  images.get('looping').get('mp4')  )

            original=images.get('original')
            self.media_w=original.get('width')
            self.media_h=original.get('height')
            original_video=original.get('mp4')
            looping_video=images.get('looping').get('mp4')

            self.thumb_url=images.get('fixed_height_still').get('url')
            self.poster_url=images.get('original_still').get('url')

            if looping_video:
                self.video_url=looping_video
            else:
                self.video_url=original_video

            return True
        else:
            log("cannot get giphy id")

        return False

    def get_video_id(self):
        self.video_id=''
        match = re.compile('giphy\.com/media/([^ /]+)/|i\.giphy\.com/([^ /]+)\.gif|giphy\.com/gifs/(?:.*-)?([^ /?]+)').findall(self.media_url)
        #log('    matches' + repr(match) )
        for m in match[0]:
            if m:
                self.video_id=m
                return

    def get_thumb_url(self):
        #calling get_playable_url sometimes results in querying giphy.com. if we do, we also save the thumbnail info.
        if self.thumb_url:
            return self.thumb_url
        else:
            self.get_media_info()

        return self.thumb_url

class ClassDailymotion(sitesBase):
    regex='(dailymotion\.com)'

    def get_playable_url(self, media_url='', is_probably_a_video=False ):
        if not media_url:
            media_url=self.media_url

        # *** needs access token to get playable url. we'll just have ytdl handle dailymotion
        self.link_action=sitesBase.DI_ACTION_YTDL
        return media_url, self.TYPE_VIDEO

#         self.get_video_id()
#         #log('    videoID:' + self.video_id)
#         if self.video_id:
#             request_url= 'https://api.dailymotion.com/video/' + self.video_id
#
#             #https://api.dailymotion.com/video/x4qviso?fields=aspect_ratio,stream_h264_hd_url,poster_url,thumbnail_url,sprite_320x_url
#
#             content = requests.get(request_url )
#             log('    ' + str(content.text))
#             if content.status_code==200:
#                 j = content.json()
#                 log( pprint.pformat(j, indent=1) )
#             else:
#                 log("  dailymotion query failed:" + str(content.status_code) )
#         else:
#             log("    %s cannot get videoID %s" %( self.__class__.__name__, media_url) )

    def get_video_id(self):
        match = re.compile('.+dailymotion.com\/(?:video\/([^_]+))?[^#]*(?:#video=([^_&]+))?', re.DOTALL).findall(self.media_url)
        #log('    match:'+ repr(match) )
        for m in match[0]:
            if m:
                self.video_id=m
                return

    def get_thumb_url(self):
        #http://stackoverflow.com/questions/13173641/how-to-get-the-video-thumbnail-from-dailymotion-video-from-the-video-id-of-that
        #Video URL: http://www.dailymotion.com/video/`video_id`
        #Thumb URL: http://www.dailymotion.com/thumbnail/video/video_id
        #
        #OR
        #https://api.dailymotion.com/video/VIDEO_ID?fields=field1,field2,...
        #Replace field1,field2 with
        #thumbnail_large_url (320px by 240px)
        #thumbnail_medium_url (160px by 120px)
        #thumbnail_small_url (80px by 60px)
        return self.media_url.replace('/video/','/thumbnail/video/')

class ClassLiveleak(sitesBase):
    regex='(liveleak.com)'
    # *** liveleak handled by ytdl

    def get_playable_url(self, media_url='', is_probably_a_video=False ):
        if use_addon_for_Liveleak:
            self.link_action=self.DI_ACTION_PLAYABLE
            return "plugin://plugin.video.liveleak/?mode=view&url={0}".format(urllib.parse.quote_plus( media_url )), self.TYPE_VIDEO
        else:
            self.link_action=sitesBase.DI_ACTION_YTDL
            return self.media_url, self.TYPE_VIDEO

    def get_thumb_url(self):
        #log('    getting liveleak thumbnail ')
        if not self.thumb_url:
            img=self.request_meta_ogimage_content()
            if img:
                self.thumb_url=img
                self.poster_url=self.thumb_url
                #log('      ll thumb:' + self.thumb_url )
                return self.thumb_url

class ClassStreamable(sitesBase):
    regex='(streamable.com)'
    video_id=''

    def get_playable_url(self, media_url, is_probably_a_video=True):
        #check if provided url links directly to the stream
        #https://streamable.com/dw9f
        #   becomes --> https://streamable.com/video/mp4/dw9f.mp4  or  https://streamable.com/video/webm/dw9f.webm
        #   thumbnail -->     //cdn.streamable.com/image/dw9f.jpg
        #this is the streamable api https://api.streamable.com/videos/dw9f

        self.get_video_id()
        #log('    ' + self.video_id)
        url_mp4=""
        url_mp4m=""
        url_webm=""
        url_webmm=""

        if self.video_id:
            api_url='https://api.streamable.com/videos/%s' %self.video_id
            r = self.requests_get(api_url)
            #log(r.text)
            j=json.loads(r.text.replace('\\"', '\''))

            if j.get('files'):  #we are not guaranteed that 'mp4-mobile' etc. exists.
                if j['files'].get('mp4'):
                    url_mp4=j['files']['mp4']['url']
                if j['files'].get('mp4-mobile'):
                    url_mp4m=j['files']['mp4-mobile']['url']
                if j['files'].get('webm'):
                    url_webm=j['files']['mp4']['url']
                if j['files'].get('webm-mobile'):
                    url_webmm=j['files']['mp4-mobile']['url']

                #use mp4 if mp4 is present else use mp4mobile then if it is still empty, use webm versions
                url_hq=url_mp4 if url_mp4 else url_mp4m
                if url_hq=="":
                    url_hq=url_webm if url_webm else url_webmm

                url_mq=url_mp4m if url_mp4m else url_mp4
                if url_mq=="":
                    url_mq=url_webmm if url_webmm else url_webm

                #finally if no hq available use mq
                if url_hq=="": url_hq=url_mq
                if url_mq=="": url_mq=url_hq

                self.link_action=sitesBase.DI_ACTION_PLAYABLE
                if streamable_quality=='full' :
                    return "https:" + url_hq, sitesBase.TYPE_VIDEO
                else:
                    return "https:" + url_mq, sitesBase.TYPE_VIDEO
        else:
            log('      %s: cant get video id '  %(self.__class__.__name__ ) )

    def get_video_id(self):
        self.video_id=''
        match = re.compile('streamable\.com\/video/(?:.+)/([^_]+)\.(?:mp4|webm)|streamable\.com\/(.*)(?:\?|$)').findall(self.media_url)
        #log('    matches' + repr(match) )
        for m in match[0]:
            if m:
                self.video_id=m
                return
        #if match: self.video_id=match[0]

    def get_thumb_url(self):
        log('    getting thumbnail [%s] %s' %(self.video_id, self.media_url ) )
        if not self.video_id:
            self.get_video_id()

        self.thumb_url="https://cdn.streamable.com/image/%s.jpg" %self.video_id
        self.poster_url=self.thumb_url

        return self.thumb_url

class ClassTumblr(sitesBase):
    regex='(tumblr\.com)'

    api_key='no0FySaKYuQHKl0EBQnAiHxX7W0HY4gKvlmUroLS2pCVSevIVy'
    include_gif_in_get_playable=True

    def get_thumb_url(self):
        #call this after calling get_playable_url
        return self.thumb_url

    def get_playable_url(self, media_url, is_probably_a_video=True ):
        #log('class tumblr prep media url')

        # don't check for media.tumblr.com because
        #there are instances where media_url is "https://vt.tumblr.com/tumblr_o1jl6p5V5N1qjuffn_480.mp4#_=_"
#         filename,ext=parse_filename_and_ext_from_url(media_url)
#
#         if 'media.tumblr.com' in media_url:
#             if ext in image_exts:
#                 return media_url, sitesBase.TYPE_IMAGE
#             elif ext in ["mp4","gif"]:
#                 return media_url,sitesBase.TYPE_VIDEO

        if "www.tumblr.com" in media_url:   #warning:nsfw!!  https://www.tumblr.com/video/johncena2014/144096330849/500/
            match = re.findall('https?://www.tumblr.com/(?:post|image|video)/(.+?)/(.+?)(?:/|$)',media_url)
        else:
            match = re.findall('https?://(.*)\.tumblr.com/(?:post|image|video)/(.+?)(?:/|$)',media_url)

        blog_identifier = match[0][0]
        post_id         = match[0][1]

        api_url='http://api.tumblr.com/v2/blog/%s/posts?api_key=%s&id=%s' %(blog_identifier,self.api_key,post_id )
        #needs to look like this:   #see documentation  https://www.tumblr.com/docs/en/api/v2
        #url='http://api.tumblr.com/v2/blog/boo-rad13y/posts?api_key=no0FySaKYuQHKl0EBQnAiHxX7W0HY4gKvlmUroLS2pCVSevIVy&id=146015264096'
        #log('apiurl:'+api_url)
        #log(api_url)
        r = self.requests_get(api_url)
        #log(r.text)
        j=json.loads(r.text.replace('\\"', '\''))

        #log("aaaaa "+ str( j['response']['blog']['url'])   )

        #this is only one post so no need to iterate through posts
        #for post in j['response']['posts']:
        post=j['response']['posts'][0]

        media_type=post['type']  #  text, photo, quote, link, chat, audio, video, answer
        #log('  Tumblr media type: ' + post['type'])

        if media_type == 'photo':
            #log('len of photos ' + str(  len(post['photos']) )  )
            self.thumb_url=post['photos'][0]['alt_sizes'][1]['url']    #alt_sizes 0-5

            if len(post['photos'])==1:
                image=post['photos'][0]['original_size']['url']
                #log('media url: ' + post['photos'][0]['original_size']['url']  )

                self.poster_url=image
                return image, sitesBase.TYPE_IMAGE

            else:
#                     dictList=[]
#                     for i, photo in enumerate( post['photos'] ):
#                         #log("%d %s" %(i, photo['original_size']['url'] ))
#                         #p.append(photo['original_size']['url'])
#
#                         infoLabels={ "Title": photo['caption'], "plot": photo['caption'], "PictureDesc": '', "exif:exifcomment": '' }
#                         e=[ photo['caption'] if photo['caption'] else str(i+1) #'li_label'           #  the text that will show for the list  (list label will be the caption or number if caption is blank)
#                            ,''                                                 #'li_label2'          #
#                            ,""                                                 #'li_iconImage'       #
#                            ,photo['alt_sizes'][3]['url']                       #'li_thumbnailImage'  #
#                            ,photo['original_size']['url']                      #'DirectoryItem_url'  #
#                            ,False                                              #'is_folder'          #
#                            ,'pictures'                                         #'type'               # video pictures  liz.setInfo(type='pictures',
#                            ,True                                               #'isPlayable'         # key:value       liz.setProperty('IsPlayable', 'true')  #there are other properties but we only use this
#                            ,infoLabels                                         #'infoLabels'         # {"title": post_title, "plot": description, "plotoutline": description, "Aired": credate, "mpaa": mpaa, "Genre": "r/"+subreddit, "studio": hoster, "director": posted_by }   #, "duration": 1271}   (duration uses seconds for titan skin
#                            ,'none'                                             #'context_menu'       # ...
#                               ]
#
#                         dictList.append(dict(zip(keys, e)))
                return self.media_url, sitesBase.TYPE_ALBUM

        elif media_type == 'video':
            self.thumb_url=post['thumbnail_url']
            return post['video_url'], sitesBase.TYPE_VIDEO
        elif media_type == 'audio':
            return post['audio_url'], media_type

        return "", media_type

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem

        if "www.tumblr.com" in album_url:   #warning:nsfw!!  https://www.tumblr.com/video/johncena2014/144096330849/500/
            match = re.findall('https?://www.tumblr.com/(?:post|image|video)/(.+?)/(.+?)(?:/|$)',album_url)
        else:
            match = re.findall('https?://(.*)\.tumblr.com/(?:post|image|video)/(.+?)(?:/|$)',album_url)

        blog_identifier = match[0][0]
        post_id         = match[0][1]

        api_url='http://api.tumblr.com/v2/blog/%s/posts?api_key=%s&id=%s' %(blog_identifier,self.api_key,post_id )
        #needs to look like this:   #see documentation  https://www.tumblr.com/docs/en/api/v2
        #url='http://api.tumblr.com/v2/blog/boo-rad13y/posts?api_key=no0FySaKYuQHKl0EBQnAiHxX7W0HY4gKvlmUroLS2pCVSevIVy&id=146015264096'
        #log('apiurl:'+api_url)
        #log(api_url)
        r = self.requests_get(api_url)
        #log(r.text)
        j=json.loads(r.text.replace('\\"', '\''))

        #log("aaaaa "+ str( j['response']['blog']['url'])   )

        #this is only one post so no need to iterate through posts
        #for post in j['response']['posts']:
        post=j['response']['posts'][0]

        media_type=post['type']  #  text, photo, quote, link, chat, audio, video, answer
        #log('  Tumblr media type: ' + post['type'])

        if media_type == 'photo':
            #log('len of photos ' + str(  len(post['photos']) )  )
            self.thumb_url=post['photos'][0]['alt_sizes'][1]['url']    #alt_sizes 0-5

            list_=(        [ photo.get('caption'), photo.get('original_size').get('url'), photo['alt_sizes'][3]['url'] ]  for photo in post['photos']   )

            self.assemble_images_dictList( list_ )

        else:
            log('      %s wrong media type: %s '  %(self.__class__.__name__ ), media_type )

        #log( pprint.pformat(self.dictList, indent=1) )
        return self.dictList

class ClassBlogspot(sitesBase):
    regex='(blogspot\.com)'
    include_gif_in_get_playable=True

    #go here:  https://console.developers.google.com/apis/credentials?project=_
    #  Create Credentials -> API Key -> Browser Key
    #  test: https://www.googleapis.com/blogger/v3/blogs/2399953?key=YOUR-API-KEY
    #     FAIL. go to. https://console.developers.google.com/apis/api/blogger/overview?project=script-reddit-reader
    #       click on "Enable" on top center area
    #  test: https://www.googleapis.com/blogger/v2/blogs/2399953&key=AIzaSyCcKuHRAYT1qreLx_Z3zwks9ODuEauJmUU
    #     will work

    key_string='key=AIzaSyCcKuHRAYT1qreLx_Z3zwks9ODuEauJmUU'

    #first retrieve the blog id by url
    #https://www.googleapis.com/blogger/v3/blogs/byurl
    #    ?key=AIzaSyCcKuHRAYT1qreLx_Z3zwks9ODuEauJmUU
    #    &url=http://zishygallery.blogspot.fr/2016/08/heaven-starr-bearded-ladies-49-images.html?zx=4b8a257abc62bfe7

    #then get the blog post by the url path
    #https://www.googleapis.com/blogger/v3/blogs/4969494452935498564/posts/bypath?key=AIzaSyCcKuHRAYT1qreLx_Z3zwks9ODuEauJmUU&path=/2016/08/heaven-starr-bearded-ladies-49-images.html

    def get_playable_url(self, media_url, is_probably_a_video=True):
        #match = re.compile('^https?://.*\.blog(?:spot|ger)\..*?/(.*)?$', re.DOTALL).findall(media_url)

        content = self.ret_blog_post_request()
        if content:
            j = content.json()
            #log( pprint.pformat(j, indent=1) )
            #author_image=j.get('author').get('image').get('url')
            #log('    author image:' + author_image)

            html=j.get('content')
            #could have just ran parseDOM the original media_url...

#            all_images=[]
#             fns=[parseDOM(html, 'img', ret="src"),parseDOM(html, 'a', ret="href") ]
#
#             log( 'zzzzzz' + repr( [ f() for f in fns])  )
#             all_images.append(  f() for f in fns )
#
#             for i in all_images:
#                 log('      all i:' + i )

#             for images=f() in fns:

#                 if images:
#                     for i in images:
#                         log('      images:'+ repr(i))
            #https://www.reddit.com/r/learnpython/comments/50ciod/calling_functions_in_a_list/




            images=parseDOM(html, name='img', ret="src")
            #log('      1st parse dom: %d %s' %(len(images), repr(images))  )
            if images:
                #for i in images:
                #    log('      images:'+ repr(i))
                self.thumb_url=images[0]
                self.poster_url=self.thumb_url

                if len(images) == 1:
                    return images[0], self.TYPE_IMAGE
                else:
                    return media_url, self.TYPE_ALBUM



            images=parseDOM(html, name='a', ret="href")
            #log('      2nd parse dom: %d %s' %(len(images), repr(images))  )
            if images:
                #for i in images:
                #    log('      images:'+ repr(i))
                log('        check[0] if playable:' + images[0])
                if link_url_is_playable(images[0]) == 'image':
                    log('        [0] is playable')
                    self.thumb_url=images[0]
                    self.poster_url=self.thumb_url

                    if len(images) == 1:
                        return images[0], self.TYPE_IMAGE
                    else:
                        return media_url, self.TYPE_ALBUM

        else:
            log('    error: %s ret_blog_post_request failed' %(self.__class__.__name__  ) )

        return '',''

    def ret_blog_post_request(self):
        o=urlparse(self.media_url)   #scheme, netloc, path, params, query, fragment
        #log( '  blogpath=' + o.path )
        blog_path= o.path

        if not blog_path:
            log('    could not determine blog path in:' + self.media_url)
            return None

        blog_info_request='https://www.googleapis.com/blogger/v3/blogs/byurl?' + self.key_string + '&url=' + self.media_url
        content = self.requests_get(blog_info_request)

        j = content.json()
        #log( pprint.pformat(j, indent=1) )
        blog_id=j.get('id')

        blog_post_request='https://www.googleapis.com/blogger/v3/blogs/%s/posts/bypath?%s&path=%s' %( blog_id, self.key_string, blog_path)
        #log( '    api request:'+blog_post_request )
        content = self.requests_get(blog_post_request)
        return content

    def get_thumb_url(self):
        if self.thumb_url:
            return self.thumb_url

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        import itertools
        content = self.ret_blog_post_request()
        if content:
            j = content.json()    #log( pprint.pformat(j, indent=1) )
            html=j.get('content')

            all_images=[]

#             images=parseDOM(html, name='img', ret="src")
#             if images:
#                 for i in images:
#                     all_images.append(i)
#                     #log('      images:'+ repr(i))
#
#             images=parseDOM(html, name='a', ret="href")
#             if images:
#                 for i in images:
#                     all_images.append(i)
#                     #log('      images:'+ repr(i))

            #https://www.reddit.com/r/learnpython/comments/50ciod/calling_functions_in_a_list/

            #doesn't work
            #params=[('img','src'),('a', 'href')]
            #all_images = [parseDOM(html, name, ret=ret) for name,ret in params]

            names = ['img', 'a']
            rets = ['src','href']
            all_images = []

            for name, ret in zip(names, rets):
                images = parseDOM(html, name = name, ret = ret)
                titles = parseDOM(html, name = 'img', ret = 'title')
                if images:
                    all_images.extend(images)

            l2=map(list,itertools.izip_longest(all_images,titles, fillvalue=None)) #instead of map(list,zip(all_images,titles)) zip will only combine lists only up to the shortest list
            #for i in l2: log('  images:' + repr(i)  )

            #for i in all_images: log('  images:' + i  )

            def k2(x): return x[0]
            l3=remove_duplicates(l2, k2 )
            images =[]
            #for i in list1: log('  checking links in list1:' + i)
            for i in l3:
                #if 'blogspot' in i: continue
                if link_url_is_playable(i[0]) == 'image':
                    title=i[1] if i[1] else None
                    images.append( {'title': title,
                                    'type': self.TYPE_IMAGE,
                                    #'description': descrip,
                                    'url': i[0],
                                    'thumb': i[0],
                                    #'width': width,
                                    #'height': height,
                                    #'isPlayable':'true',
                                    }  )
            #for i in images: log(repr(i)  )

            self.assemble_images_dictList(  images    )
            #for i in self.dictList: log(repr(i)  )
            return self.dictList
        else:
            log('    content blank ')

class ClassInstagram(sitesBase):
    regex='(instagram.com)'

    def get_playable_url(self, media_url, is_probably_a_video=True):
        #the instagram api has limits and that would not work for this purpose
        #  scrape the instagram post instead.
        r = self.requests_get(media_url)
        #log(r.text)
        #grab the json-like object
        jo=re.compile('window._sharedData = ({.*});</script>').findall(r.text)
        if jo:
            #import pprint; log( pprint.pformat(jo[0], indent=1) )
            try:
                j=json.loads(jo[0] )
                #log(str(j))
                entry_data=j.get('entry_data')
                if entry_data:
                    #log(repr(entry_data.keys()))
                    if 'PostPage' in entry_data.keys():
                        post_pages=entry_data.get('PostPage')
                        #log('    post_pages %d' %len(post_pages) )
                        #log('    post_page ' +repr(post_pages[0]) )
                        post_page=post_pages[0]
                        media=post_page.get('media')
                        if media:
                            #log(str(j['entry_data']['PostPage'][0]['media']['display_src']))
                            display_src=media.get('display_src')
                        else:
                            #this part added to parse: https://www.instagram.com/p/BBqU7WPtudX/?taken-by=insecuregod
                            media=nested_lookup('shortcode_media',post_page)[0]
                            display_src=media.get('display_url')

                        is_video=media.get('is_video')
                        self.media_w=media.get('dimensions').get('width')
                        self.media_h=media.get('dimensions').get('height')

                        self.thumb_url=display_src
                        self.poster_url=self.thumb_url
                        #log('      vid=%s %dx%d %s' %(is_video,self.media_w,self.media_h,display_src)  )
                        if is_video:
                            self.media_url=media.get('video_url')
                            self.link_action=sitesBase.DI_ACTION_PLAYABLE
                            return self.media_url, sitesBase.TYPE_VIDEO
                        else:
                            return display_src, sitesBase.TYPE_IMAGE
                    if 'ProfilePage' in entry_data.keys():
                        profile_page=entry_data.get('ProfilePage')[0]
                        #user=profile_page.get('user')

                        self.thumb_url=nested_lookup('profile_pic_url',profile_page)[0]
                        #log('  profile thumb='+repr(self.thumb_url))

                        images=self.ret_images_dict_from_album_json(profile_page)
                        #for i in images: log( '##' + repr(i))
                        self.assemble_images_dictList(images)

                        return media_url, sitesBase.TYPE_ALBUM
                else:
                    log("  Could not get 'entry_data' from scraping instagram [window._sharedData = ]")

            except (AttributeError,TypeError) as e:
                log('    exception while parsing json:'+str(e))

        return '', ''

    def ret_images_dict_from_album_json(self, j):
        images=[]
        album_nodes=j.get('user').get('media').get('nodes') #only returns about 12. we're not getting the rest for now
        #log(' insta album:'+repr(album))

        for entry in album_nodes:
            is_video=entry.get('is_video')
            link_action=''
            if is_video:
                #'code' and 'id' might be used to get the video?
                media_url=entry.get('video_url')  #video_url is not in json!
                #media_url=entry.get('display_src')
                link_action=sitesBase.DI_ACTION_PLAYABLE
                media_type=self.TYPE_VIDEO
                isPlayable='true'
            else:
                media_url=entry.get('display_src')
                media_type=self.TYPE_IMAGE
                isPlayable='false'

            width    =entry.get('dimensions').get('width')
            height   =entry.get('dimensions').get('height')
            title    =entry.get('caption')
            descrip  =entry.get('caption')
            thumb_url=entry.get('thumbnail_src')

            images.append( {'title': title,
                            'type': media_type,
                            'description': descrip,
                            'url': media_url,
                            'thumb': thumb_url,
                            'width': width,
                            'height': height,
                            'isPlayable':isPlayable,
                            'link_action':link_action,
                            }  )
        return images

    def ret_album_list(self,album_url):
        r = self.requests_get(album_url)
        jo=re.compile('window._sharedData = ({.*});</script>').findall(r.text)
        if jo:
            #import pprint; log( pprint.pformat(jo[0], indent=1) )
            try:
                j=json.loads(jo[0] )
                entry_data=j.get('entry_data')
                if entry_data:
                    if 'ProfilePage' in entry_data.keys():
                        profile_page=entry_data.get('ProfilePage')[0]

                        images=self.ret_images_dict_from_album_json(profile_page)
                        #for i in images: log( '##' + repr(i))
                        self.assemble_images_dictList(images)

                        return self.dictList
                else:
                    log("  Could not get 'entry_data' from scraping instagram [window._sharedData = ]")

            except (AttributeError,TypeError) as e:
                log('    exception while parsing json:'+str(e))

    def get_thumb_url(self):
        if self.thumb_url:
            return self.thumb_url

class ClassGyazo(sitesBase):
    regex='(gyazo\.com)'

    def get_playable_url(self, link_url, is_probably_a_video=True):

        #media_url='http://gyazo.com/b8c993ab1435171eafefb882d8e2d17a'
        api_url='https://api.gyazo.com/api/oembed?url=%s' %(link_url )

        r = self.requests_get(api_url)
        #if 'ff27ee' in link_url: log(r.text)
        j=json.loads(r.text.replace('\\"', '\''))

        media_type=j.get('type')
        self.media_w=j.get('width')
        self.media_h=j.get('height')
        media_url=j.get('url')

        log('      gyazo=%s %dx%d %s' %(media_type, self.media_w,self.media_h, j.get('url'))  )

        if ret_url_ext(link_url)=='gif':
            self.link_action=sitesBase.DI_ACTION_PLAYABLE
            self.media_type=sitesBase.TYPE_GIF
            self.media_url=link_url
        else:
            if media_type=='photo':
                self.thumb_url=media_url
                self.poster_url=self.thumb_url

                self.media_type=sitesBase.TYPE_IMAGE
                self.media_url=media_url
            elif media_type=='video':
                #url tag missing... 3/1/2017 - discovered that there is no more url tag for video. (we can stil parse the html tag for 'src' and parse that link for the <video autoplay..src=.mp4
                #   but to heck with that, just send link to ytdl
                #self.link_action=sitesBase.DI_ACTION_PLAYABLE
                self.link_action=sitesBase.DI_ACTION_YTDL
                self.media_type=sitesBase.TYPE_VIDEO
                #self.media_url=media_url
                self.media_url=link_url

        return self.media_url,self.media_type


    def get_thumb_url(self):
        if self.thumb_url:
            return self.thumb_url

class ClassFlickr(sitesBase):
    regex='(flickr\.com|flic\.kr)'

    api_key='a3662f98e08266dca430404d37d8dc95'
    thumb_url=""
    poster_url=""

    fTYPE_ALBUM='album'
    fTYPE_PHOTO='photo'
    fTYPE_GROUP='group'
    fTYPE_VIDEO='video'
    fTYPE_GALLERY='gallery'
    fmedia_type=''

    def get_thumb_url(self):
        #call this after calling get_playable_url
        return self.thumb_url

    def get_photo_id_flic_kr(self, url):
        #Flickr provides a URL shortening service for uploaded photos (and videos). Short URLs can be useful in a variety of contexts including: email, on business cards, IM, text messages, or short status updates.
        #Every photo on Flickr has a mathematically calculated short URL of the form:
        #   https://flic.kr/p/{base58-photo-id}
        #Base58 is used to compress the photo-ids using a mix of letters and numbers. You can find more info on base58, and code samples in the Flickr API Group.

        #after some testing, found that the flickr api accepts the undecoded photo id.
        #after some more testing, undecoded photo id for photos only. for photosets(album), it has to be decoded

        #flic\.kr\/(?:.+\/)?(.+)|flickr\.com\/photos\/|flic\.kr\/(?:.+\/)?(\d+)
        #match = re.findall('flic\.kr\/(?:.+\/)?(.+)',url)
        #photo_id=match[0]

        from base58 import decode
        b58e_id=url.split('/')[-1] #https://flic.kr/p/KSt6Hh   https://flic.kr/s/aHskGjN56V

        a = decode(b58e_id)
        sa= str(a)
        #this site is helpful to test decoding:
        #  https://www.darklaunch.com/tools/base58-encoder-decoder

        if self.media_type==self.fTYPE_GROUP:
            # https://flic.kr/g/stemc  ==>  https://www.flickr.com/groups/2995418@N23/
            #log( " group id was %s" %a )
            #log( " group id now %s" %( a[0:-2] + '@N' + a[-2:] ) )  #[ begin : end : step ]
            sa =( sa[0:-2] + '@N' + sa[-2:] )

        if self.media_type==self.fTYPE_GALLERY:
            #note: this was done through trial and error. the short code did not decode to the correct galleryID.
            # https://flic.kr/y/2sfUimC  ==>  https://www.flickr.com/photos/flickr/galleries/72157671483451751/
            a = a + 72157616180848087
            sa=str(a)

        log( '    decoding flickrID:' + b58e_id + ' => ' + sa )
        return sa

    def get_video_id(self):
        #this method cannot determine ID from flikr group like  https://www.flickr.com/groups/flickrfriday/   (https://flic.kr/g/ju9j6)
        #  flickrfriday is the friendly name for the group. you need to use the flickr api to get groupID
        #  https://www.flickr.com/services/api/flickr.urls.lookupGroup.html
        #
        #  not doing that right now.
        #use shortened url. it worked for groups

        self.video_id=''
        if 'flic.kr' in self.media_url:
            photo_id=self.get_photo_id_flic_kr(self.media_url)
        else:
            #get the photoID
            #match = re.findall('flickr\.com\/photos\/(?:.+\/)?(\d+)',media_url)
            if self.is_an_album(self.media_url):
                match = re.findall('flickr\.com/photos/(?:.+)?(?:/sets/|/albums/|/s/|/groups/|/g/|galleries|/y/)(\d+)|flickr\.com/photo\.gne\?short=(.+)',self.media_url)
            else:
                match = re.findall('flickr\.com\/photos\/(?:.+\/)?(\d+)|flickr\.com/photo\.gne\?short=(.+)',self.media_url)  #sometimes url comes like this: https://www.flickr.com/photo.gne?short=LHmhpR

            for m in match[0]:
                if m:
                    photo_id=m

        self.video_id=photo_id

    def get_playable_url(self, media_url, is_probably_a_video=True ):

        if self.is_an_album(media_url):
            return media_url, sitesBase.TYPE_ALBUM

        self.fmedia_type="photo"
        ret_url=""

        #figure out the media type; this determines how we extract the ID and api call to use
        self.fmedia_type=self.flickr_link_type(media_url)
        log( '    media_type='+ self.fmedia_type + "  from:" + media_url)

        self.get_video_id()
        photo_id=self.video_id

        if self.fmedia_type==self.fTYPE_ALBUM:
            #log('  is a flickr album (photoset)')
            api_method='flickr.photosets.getPhotos'
            api_arg='photoset_id=%s' %photo_id
        elif self.fmedia_type==self.fTYPE_PHOTO:
            api_method='flickr.photos.getSizes'
            api_arg='photo_id=%s' %photo_id
        elif self.fmedia_type==self.fTYPE_GROUP:
            api_method='flickr.groups.pools.getPhotos'
            api_arg='group_id=%s' %photo_id
        elif self.fmedia_type==self.fTYPE_GALLERY:
            api_method='flickr.galleries.getPhotos'
            api_arg='gallery_id=%s' %photo_id


        api_url='https://api.flickr.com/services/rest/?format=json&nojsoncallback=1&api_key=%s&method=%s&%s' %(self.api_key,api_method,api_arg )

        #log('  flickr apiurl:'+api_url)
        r = self.requests_get(api_url)
        #log(r.text)
        j=json.loads(r.text.replace('\\"', '\''))

        status=j.get('stat')
        if status=='fail':
            message=j.get('message')
            raise Exception(message)

        if self.fmedia_type in [self.fTYPE_ALBUM, self.fTYPE_GROUP, self.fTYPE_GALLERY ]:   #for  #photosets, galleries, pools? panda?
            self.media_type=sitesBase.TYPE_ALBUM

            if self.fmedia_type==self.fTYPE_ALBUM:
                photos=j['photoset']['photo']
                owner=j.get('photoset').get('ownername')
            else:
                #elif self.media_type in [self.fTYPE_GROUP, self.fTYPE_GALLERY]:
                photos=j['photos']['photo']

            '''
            You can construct the source URL to a photo once you know its ID, server ID, farm ID and secret, as returned by many API methods.
            The URL takes the following format:
            https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}.jpg
            https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}_[mstzb].jpg
            https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{o-secret}_o.(jpg|gif|png)
                The letter suffixes are as follows:
                s    small square 75x75
                q    large square 150x150
                t    thumbnail, 100 on longest side
                m    small, 240 on longest side
                n    small, 320 on longest side
                -    medium, 500 on longest side
                z    medium 640, 640 on longest side
                c    medium 800, 800 on longest side†
                b    large, 1024 on longest side*
                h    large 1600, 1600 on longest side†
                k    large 2048, 2048 on longest side†
                o    original image, either a jpg, gif or png, depending on source format
            '''
            dictList=[]
            for i, p in enumerate( photos ):
                ownerstring=''
                if self.fmedia_type in [self.fTYPE_GROUP, self.fTYPE_GALLERY]:
                    owner=p.get('ownername')
                    if owner:
                        ownerstring ='by %s'%(owner)

                photo_url='https://farm%s.staticflickr.com/%s/%s_%s_%c.jpg' %(p['farm'],p['server'],p['id'],p['secret'],'b' )
                thumb_url='https://farm%s.staticflickr.com/%s/%s_%s_%c.jpg' %(p['farm'],p['server'],p['id'],p['secret'],'n' )
                poster_url='https://farm%s.staticflickr.com/%s/%s_%s_%c.jpg' %(p['farm'],p['server'],p['id'],p['secret'],'z' )
                #log(" %d  %s" %(i,photo_url ))
                #log(" %d  %s" %(i,thumb_url ))

                infoLabels={ "Title": p['title'], "plot": ownerstring , "director": p.get('ownername'), "exif:exifcomment": '',  }

                e=[ p['title'] if p['title'] else str(i+1)             #'li_label'           #  the text that will show for the list  (list label will be the caption or number if caption is blank)
                   ,p['title']                                         #'li_label2'          #
                   ,""                                                 #'li_iconImage'       #
                   ,thumb_url                                          #'li_thumbnailImage'  #
                   ,photo_url                                          #'DirectoryItem_url'  #
                   ,False                                              #'is_folder'          #
                   ,'pictures'                                         #'type'               # video pictures  liz.setInfo(type='pictures',
                   ,True                                               #'isPlayable'         # key:value       liz.setProperty('IsPlayable', 'true')  #there are other properties but we only use this
                   ,infoLabels                                         #'infoLabels'         # {"title": post_title, "plot": description, "plotoutline": description, "Aired": credate, "mpaa": mpaa, "Genre": "r/"+subreddit, "studio": hoster, "director": posted_by }   #, "duration": 1271}   (duration uses seconds for titan skin
                   ,'none'                                             #'context_menu'       # ...
                      ]

                dictList.append(dict(zip(keys, e)))

                #use first image as thumbnail and poster
                if i==0:
                    self.thumb_url=thumb_url
                    self.poster_url=poster_url

            return dictList

        elif self.fmedia_type==self.fTYPE_PHOTO:

            sizes=j['sizes']
            #log('    sizes' + str(sizes))
            #Square, Large Square, Thumbnail, Small, Small 320, Medium, Medium 640, Medium 800, Large, Large 1600, Large 2048, Original
            for s in sizes['size']:
                #log('    images size %s url=%s' %( s['label'], s['source']  ) )
                if s['label'] == 'Medium 640':
                    self.poster_url=s['source']

                #if s['label'] == 'Medium 800':
                #    self.poster_url=s['source']

                if s['label'] == 'Thumbnail':
                    self.thumb_url=s['source']

                if s['label'] == 'Small':
                    self.thumb_url=s['source']

                #sometimes large is not available we just brute force the list starting from lowest that we'll take
                if s['label'] == 'Medium':
                    ret_url=s['source']
                    #media_type=s['media']   #'photo'

                if s['label'] == 'Medium 640':
                    ret_url=s['source']
                    #media_type=s['media']   #'photo'

                if s['label'] == 'Medium 800':
                    ret_url=s['source']
                    #media_type=s['media']   #'photo'

                if s['label'] == 'Large':
                    ret_url=s['source']
                    #media_type=s['media']

                if s['label'] == 'Large 1600':
                    ret_url=s['source']
                    #media_type=s['media']

        return ret_url, self.TYPE_IMAGE

    @classmethod
    def is_an_album(self,media_url):
        #returns true if link is a bunch of images
        a=['/sets/','/albums/','/s/','/groups/','/g/','/galleries/','/y/']
        if any(x in media_url for x in a):
            return True
        return False

    def flickr_link_type(self,media_url):
        a=['/sets/','/albums/','/s/']
        g=['/groups/','/g/']
        y=['/galleries/','/y/']
        if any(x in media_url for x in a):
            return self.fTYPE_ALBUM

        if any(x in media_url for x in g):
            return self.fTYPE_GROUP

        if any(x in media_url for x in y):
            return self.fTYPE_GALLERY

        #p=['/photo/','/p/']
        return self.fTYPE_PHOTO

    def ret_album_list(self, album_url, thumbnail_size_code=''):

        if not self.is_an_album(album_url):
            log('  flickr link is not an album' + album_url)
            return ''

        self.fmedia_type="photo"

        #figure out the media type; this determines how we extract the ID and api call to use
        self.fmedia_type=self.flickr_link_type(album_url)
        log( '    media_type='+ self.fmedia_type + "  from:" + album_url)

        self.get_video_id()
        photo_id=self.video_id

        if self.fmedia_type==self.fTYPE_ALBUM:
            #log('  is a flickr album (photoset)')
            api_method='flickr.photosets.getPhotos'
            api_arg='photoset_id=%s' %photo_id
        elif self.fmedia_type==self.fTYPE_PHOTO:
            api_method='flickr.photos.getSizes'
            api_arg='photo_id=%s' %photo_id
        elif self.fmedia_type==self.fTYPE_GROUP:
            api_method='flickr.groups.pools.getPhotos'
            api_arg='group_id=%s' %photo_id
        elif self.fmedia_type==self.fTYPE_GALLERY:
            api_method='flickr.galleries.getPhotos'
            api_arg='gallery_id=%s' %photo_id

        api_url='https://api.flickr.com/services/rest/?format=json&nojsoncallback=1&api_key=%s&method=%s&%s' %(self.api_key,api_method,api_arg )

        #log('  flickr apiurl:'+api_url)
        r = self.requests_get(api_url)
        #log(r.text)
        j=json.loads(r.text.replace('\\"', '\''))

        status=j.get('stat')
        if status=='fail':
            message=j.get('message')
            raise Exception(message)

        if self.fmedia_type in [self.fTYPE_ALBUM, self.fTYPE_GROUP, self.fTYPE_GALLERY ]:   #for  #photosets, galleries, pools? panda?
            self.media_type=sitesBase.TYPE_ALBUM

            if self.fmedia_type==self.fTYPE_ALBUM:
                photos=j['photoset']['photo']
                owner=j.get('photoset').get('ownername')
            else:
                #elif self.media_type in [self.fTYPE_GROUP, self.fTYPE_GALLERY]:
                photos=j['photos']['photo']

            '''
            You can construct the source URL to a photo once you know its ID, server ID, farm ID and secret, as returned by many API methods.
            The URL takes the following format:
            https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}.jpg
            https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}_[mstzb].jpg
            https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{o-secret}_o.(jpg|gif|png)
                The letter suffixes are as follows:
                s    small square 75x75
                q    large square 150x150
                t    thumbnail, 100 on longest side
                m    small, 240 on longest side
                n    small, 320 on longest side
                -    medium, 500 on longest side
                z    medium 640, 640 on longest side
                c    medium 800, 800 on longest side†
                b    large, 1024 on longest side*
                h    large 1600, 1600 on longest side†
                k    large 2048, 2048 on longest side†
                o    original image, either a jpg, gif or png, depending on source format
            '''
            dictList=[]
            for i, p in enumerate( photos ):
                ownerstring=''
                if self.fmedia_type in [self.fTYPE_GROUP, self.fTYPE_GALLERY]:
                    owner=p.get('ownername')
                    if owner:
                        ownerstring ='by %s'%(owner)

                photo_url='https://farm%s.staticflickr.com/%s/%s_%s_%c.jpg' %(p['farm'],p['server'],p['id'],p['secret'],'b' )
                thumb_url='https://farm%s.staticflickr.com/%s/%s_%s_%c.jpg' %(p['farm'],p['server'],p['id'],p['secret'],'n' )
                #poster_url='https://farm%s.staticflickr.com/%s/%s_%s_%c.jpg' %(p['farm'],p['server'],p['id'],p['secret'],'z' )
                #log(" %d  %s" %(i,photo_url ))
                #log(" %d  %s" %(i,thumb_url ))

                infoLabels={ "Title": p['title'], "plot": ownerstring , "director": p.get('ownername'), "exif:exifcomment": '',  }

                e=[ p['title'] if p['title'] else str(i+1)             #'li_label'           #  the text that will show for the list  (list label will be the caption or number if caption is blank)
                   ,p['title']                                         #'li_label2'          #
                   ,""                                                 #'li_iconImage'       #
                   ,thumb_url                                          #'li_thumbnailImage'  #
                   ,photo_url                                          #'DirectoryItem_url'  #
                   ,False                                              #'is_folder'          #
                   ,'pictures'                                         #'type'               # video pictures  liz.setInfo(type='pictures',
                   ,True                                               #'isPlayable'         # key:value       liz.setProperty('IsPlayable', 'true')  #there are other properties but we only use this
                   ,infoLabels                                         #'infoLabels'         # {"title": post_title, "plot": description, "plotoutline": description, "Aired": credate, "mpaa": mpaa, "Genre": "r/"+subreddit, "studio": hoster, "director": posted_by }   #, "duration": 1271}   (duration uses seconds for titan skin
                   ,'none'                                             #'context_menu'       # ...
                      ]

                dictList.append(dict(zip(keys, e)))

            return dictList

        else:
            log('    NOT AN ALBUM: unexpected flickr media type ' + self.fmedia_type )

class ClassRedgifs(sitesBase):
    regex='(redgifs.com)'

    def get_playable_url(self, media_url, is_probably_a_video=True ):
        #the video id i get do not have capital letters
        #ytdl seems to be able to get the correct video id
        self.link_action=sitesBase.DI_ACTION_YTDL
        self.media_type=sitesBase.TYPE_VIDEO
        return media_url, self.media_type

        #end here
        self.get_video_id()
        if self.video_id:
            #redgifs use the same api as gfycat but they have not released an official api
            #request_url="https://redgifs.com/cajax/get/" + self.video_id  #this endpoint has been deprecated
            #request_url="https://api.redgifs.com/v1/redgifs/%s" % self.video_id

            self.link_action=sitesBase.DI_ACTION_PLAYABLE
            stream_url='https://thumbs1.redgifs.com/'+self.video_id+'.webm'

            #https://redgifs.com/watch/darlingmagnificentconey
            #return 'https://thumbs1.redgifs.com/DarlingMagnificentConey.webm', self.TYPE_VIDEO
            return stream_url, self.TYPE_VIDEO
        else:
            log("cannot get redgif id")
        return '', ''

    def get_video_id(self):
        self.video_id=''
        match = re.findall("redgifs.com/watch/(.+?)(?:-|$|')", self.media_url)
        if match:
            log('  found video id['+match[0]+']')
            self.video_id=match[0]


    def get_thumb_url(self):
        #call this after calling get_playable_url
        return self.thumb_url

class ClassGfycat(sitesBase):
    regex='(gfycat.com)'

    def get_playable_url(self, media_url, is_probably_a_video=True ):
        self.get_video_id()

        if self.video_id:
            #log('    video id:' + repr(self.video_id) )
            #request_url="https://gfycat.com/cajax/get/" + self.video_id  #this endpoint has been deprecated
            request_url="https://api.gfycat.com/v1/gfycats/%s" % self.video_id
            #request_url="https://api.gfycat.com/v1test/gfycats/{gfyid}".format(gfyid=self.video_id)  #this method requires auth token etc.

            try:
                content = self.requests_get(request_url)
                #log('gfycat response:'+ content.text)
                content = content.json()
            except requests.exceptions.HTTPError:
                log('    Error requesting info via api endpoint. Trying actual link: '+media_url)
                #encountered a link that returns 404 with the api request but exists using browser. https://gfycat.com/gifs/detail/DeliciousBowedAlpinegoat
                # we will parse it manually
                r = self.requests_get(media_url)
                jo=re.compile('___INITIAL_STATE__=({.*});').findall(r.text)
                if jo:
                    #import pprint
                    #log( pprint.pformat(jo[0], indent=1) )
                    j=json.loads(jo[0])
                    content=j.get('detail')

            gfyItem=content.get('gfyItem')
            if gfyItem:
                self.media_w=safe_cast(gfyItem.get('width'),int,0)
                self.media_h=safe_cast(gfyItem.get('height'),int,0)
                webmSize=safe_cast(gfyItem.get('webmSize'),int,0)
                mp4Size =safe_cast(gfyItem.get('mp4Size'),int,0)

                self.thumb_url =gfyItem.get('posterUrl')  #thumb100PosterUrl
                self.poster_url=gfyItem.get('posterUrl')

                #pick the smaller of the streams
                if mp4Size > webmSize:
                    #log('      using webm  wm(%d) m4(%d)' %(webmSize,mp4Size) )
                    stream_url=gfyItem.get('webmUrl') if gfyItem.get('webmUrl') else gfyItem.get('mp4Url')
                else:
                    #log('      using mp4   wm(%d) m4(%d)' %(webmSize,mp4Size) )
                    stream_url=gfyItem.get('mp4Url') if gfyItem.get('mp4Url') else gfyItem.get('webmUrl')

                #log('      %dx%d %s' %(self.media_w,self.media_h,stream_url)  )

                self.link_action=sitesBase.DI_ACTION_PLAYABLE
                return stream_url, self.TYPE_GIF #sitesBase.TYPE_VIDEO
            else:
                error=content.get('error')
                if error:
                    self.link_action=self.DI_ACTION_ERROR
                    return error, ""
        else:
            log("cannot get gfycat id")

        return '', ''

    def get_video_id(self):
        self.video_id=''
        #https://thumbs.gfycat.com/DefenselessVillainousHapuku-size_restricted.gif
        #https://thumbs.gfycat.com/DefenselessVillainousHapuku
        #python3 notes: for some reason the last  '   from   b'https://gfycat.com/weeklycelebratedfirebelliedtoad'    is included in match[0] i had to modify the regex to ignore the last  '
        #atch = re.findall("gfycat.com/(.+?)(?:-|$)"  , self.media_url)
        match = re.findall("gfycat.com/(.+?)(?:-|$|')", self.media_url)
        if match:
            #log('  found video id['+match[0]+']')
            self.video_id=match[0]


    def get_thumb_url(self):
        #call this after calling get_playable_url
        return self.thumb_url

class ClassGifsCom(sitesBase):
    regex='(gifs\.com)'
    #also vidmero.com

    api_key='gifs577da09e94ee1'   #gifs577da0485bf2a'
    headers = { 'Gifs-API-Key': api_key, 'Content-Type': "application/json" }
    #request_url="https://api.gifs.com"

    def get_playable(self, media_url='', is_probably_a_video=False ):
        media_type=self.TYPE_VIDEO
        if not media_url:
            media_url=self.media_url

        filename,ext=parse_filename_and_ext_from_url(media_url)
        #log('    file:%s.%s' %(filename,ext)  )
        if ext in ["mp4","webm","gif"]:
            if ext=='gif':
                media_type=self.TYPE_GIF
                self.link_action=sitesBase.DI_ACTION_PLAYABLE
                self.thumb_url=media_url.replace( '%s.%s'%(filename,ext) , '%s.jpg' %(filename))
                self.poster_url=self.thumb_url
                self.media_url=media_url.replace( '%s.%s'%(filename,ext) , '%s.mp4' %(filename))   #just replacing gif to mp4 works
            return self.media_url, media_type

        if ext in image_exts:  #excludes .gif
            self.link_action='viewImage'
            self.thumb_url=media_url
            self.poster_url=self.thumb_url
            return media_url,self.TYPE_IMAGE

        return self.get_playable_url(self.media_url, is_probably_a_video=False )


    def get_thumb_url(self):
        #call this after calling get_playable_url
        return self.thumb_url

    def get_video_id(self):
        #looks like the filename is also the video id and some links have it at the "-"end od url
        self.video_id=''

        #https://j.gifs.com/zpOmn5.gif       <-- this is handled in get_playable -> .gif replaced with .mp4
        #http://gifs.com/gif/qxBQMp                   <-- parsed here.
        #https://gifs.com/gif/yes-nooo-whaaa-5yZ8rK   <-- parsed here.

        match = re.compile('gifs\.com/(?:gif/)?(.+)(?:.gif|$)').findall(self.media_url)
        #log('    matches' + repr(match) )

        if match:
            vid=match[0]
            if '-' in vid:
                vid= vid.split('-')[-1]

            self.video_id=vid

    def get_playable_url(self, media_url, is_probably_a_video=True ):
        #api method abandoned. doesn't seem to be any way to get media info. api is just for upload and convert(?)

        #can also parse the link...
#               <div class="gif-display">
#                   <video id="video" muted class="gifyt-player gifyt-embed" preload="auto"
#                          poster="https://j.gifs.com/gJoYy9.jpg" loop="" autoplay="">
#                       <source src="https://j.gifs.com/gJoYy9.mp4" type="video/mp4">
#                   </video>
#               </div>

        self.get_video_id()
        log('    gifs.com videoID:' + self.video_id )

        self.link_action=sitesBase.DI_ACTION_PLAYABLE
        return 'http://j.gifs.com/%s.mp4' %self.video_id , sitesBase.TYPE_VIDEO


class ClassEroshare(sitesBase):
    SITE='eroshare'
    regex='(eroshare.com)'

    def get_playable_url(self, link_url, is_probably_a_video=True ):

        content = self.requests_get( link_url )
        #if 'pnnh' in media_url:
        #    log('      retrieved:'+ str(content) )

        match = re.compile('var album\s=\s(.*)\;').findall(content.text)
        if match:
            j = json.loads(match[0])
            items = j.get('items')
            #log( '      %d item(s)' % len(items) )

            self.media_type, playable_url, self.poster_url, self.thumb_url=self.get_media(items[0])
            if len(items) == 1:
                #item=items[0]
                #log('      single %s %s' %( self.media_type, playable_url ))
                #self.media_type=item.get('type')
                #self.media_type, playable_url, self.poster_url, self.thumb_url=self.get_media(item)
                if self.media_type==sitesBase.TYPE_VIDEO:
                    self.link_action=sitesBase.DI_ACTION_PLAYABLE

                return playable_url, self.media_type
            else:
                #check if all items are video or image
                media_types = []
                for item in items:
                    #log('    multiple: %s orig=%s ' %( item.get('type').lower(), item.get('url_orig') ))
                    media_types.append( item.get('type').lower() )

                #data already here, might as well parse it.
                images=self.ret_images_dict_from_album_json(j)
                self.assemble_images_dictList(images)

                if all_same(media_types):
                    if media_types[0]==self.TYPE_IMAGE:
                        log('    eroshare link has all images %d' %len(items) )
                        self.media_type=self.TYPE_ALBUM

                    elif media_types[0]==self.TYPE_VIDEO:
                        log('    eroshare link has all video %d' %len(items) )
                        self.link_action=sitesBase.DI_ACTION_YTDL
                        self.media_type=self.TYPE_VIDS

                    return link_url, self.media_type
                else: #video and images
                    log('    eroshare link has mixed video and images %d' %len(items) )
                    self.link_action=None #sitesBase.DI_ACTION_YTDL
                    self.media_type=self.TYPE_ALBUM
                    return link_url, self.media_type
        else:
            #try an alternate method (not an album)
            #log('      var album string not found. trying alternate method ')

            div_item_list = parseDOM(content.text, "div", attrs = { "class": "item-list" })
            #log('div_item_list=' + repr(div_item_list))
            poster = parseDOM(div_item_list, "video", ret = "poster")
            #log('    poster=' + repr(poster))
            if poster:
                #assume video if there is poster
                self.poster_url='http:' + poster[0]

                playable_url = parseDOM(div_item_list, "source", ret = "src")
                #log('playable_url=' + repr(playable_url))
                if playable_url:
                    self.link_action=sitesBase.DI_ACTION_PLAYABLE
                    return playable_url[0], self.TYPE_VIDEO
            else:
                #assume image if can't get poster
                image=parseDOM(div_item_list, "img", ret = "src")
                if image:
                    self.poster_url='http:' + image[0]
                    return self.poster_url, self.TYPE_IMAGE

        return '', ''

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem
        content = self.requests_get( album_url)

        match = re.compile('var album\s=\s(.*)\;').findall(content.text)
        #log('********* ' + match[0])
        if match:
            j = json.loads(match[0])
            images=self.ret_images_dict_from_album_json(j)
            self.assemble_images_dictList(images)
            #self.assemble_images_dictList(   ( [ s.get('description'), prefix+s.get('url_full')] for s in items)    )

        else:
            log('      eroshare:ret_album_list: var album string not found. ')

        return self.dictList

    def ret_images_dict_from_album_json(self,j):
        images=[]
        try:
            reddit_submission=j.get('reddit_submission')
            reddit_submission_title=''
            if reddit_submission:
                reddit_submission_title=reddit_submission.get('title')

            title=j.get('title') if j.get('title') else reddit_submission_title
            items=j.get('items')
            #log( '      %d item(s)' % len(items) )
            prefix='https:'
            for s in items:
                media_type=s.get('type').lower()
                description=s.get('description') if s.get('description') else title  #use title if description is blank
                #media_url=prefix+s.get('url_orig')   #this size too big...
                media_url=prefix+s.get('url_full')
                width=s.get('width')
                height=s.get('height')
                thumb=prefix+s.get('url_thumb')
                if media_type==self.TYPE_VIDEO:
                    self.link_action=sitesBase.DI_ACTION_PLAYABLE
                    images.append( {
                                    'isPlayable':True,
                                    'thumb':thumb,
                                    'type': self.TYPE_VIDEO,
                                    'description': description,
                                    'url': s.get('url_mp4'),
                                    'width': width,
                                    'height': height,
                                    }  )
                else:
                    images.append( {
                                    'thumb':thumb,
                                    'description': description,
                                    'url': media_url,
                                    'width': width,
                                    'height': height,
                                    }  )
        except AttributeError as e:
            log('  error parsing eroshare album:'+str(e))
        return images

    def get_media(self, j_item):
        h='https:'
        media_type=j_item.get('type').lower()
        if media_type==sitesBase.TYPE_VIDEO:
            media_url =  j_item.get('url_mp4')
            poster_url=h+j_item.get('url_full')
            thumb_url =h+j_item.get('url_thumb')
        elif media_type==sitesBase.TYPE_IMAGE:
            poster_url=h+j_item.get('url_full')
            media_url =poster_url    #h+j_item.get('url_orig')  #url_orig is very slow
            thumb_url =h+j_item.get('url_thumb')
        else:
            log('   returned media type(%s) does not match defined media types ' %media_type )
        return media_type, media_url, poster_url, thumb_url

    def get_thumb_url(self):
        return self.thumb_url

class ClassImgbox(sitesBase):
    SITE='imgbox'
    regex='(imgbox.com)'

    include_gif_in_get_playable=True

    def is_album(self, media_url):
        if '/g/' in media_url:
            self.media_type = self.TYPE_ALBUM
            return True
        else:
            return False

    def get_playable_url(self, media_url, is_probably_a_video=False ):
        if self.is_album(media_url):
            log('  is an album:'+ media_url )
            self.media_type = self.TYPE_ALBUM
            return media_url, sitesBase.TYPE_ALBUM

        log('  scraping:'+ media_url )
        content = self.requests_get( media_url)

        #https://github.com/downthemall/anticontainer/blob/master/plugins/imgbox.com.json
        match = re.compile("id=\"img\".+?src=\"(.+?)\" title=\"(.+?)\"", re.DOTALL).findall(content.text)
        #log('    match:' + repr(match))
        if match:
            #log('      match' + match[0][0])
            self.poster_url=match[0][0]
            self.thumb_url=self.poster_url
            return self.poster_url, self.TYPE_IMAGE
        else:
            log("    %s can't scrape image " %(self.__class__.__name__ ) )

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem

        content = self.requests_get( album_url)

        div_item_list=parseDOM(content.text, "div", attrs = { "id": "gallery-view-content" })
        #log('    div_item_list='+repr(div_item_list))

        #<a href="/fbDGR5kF"><img alt="Fbdgr5kf" src="http://1.s.imgbox.com/fbDGR5kF.jpg" /></a>
        #<a href="/3f2FGZBl"><img alt="3f2fgzbl" src="http://4.s.imgbox.com/3f2FGZBl.jpg" /></a>
        #<a href="/qnUS37TF"><img alt="Qnus37tf" src="http://6.s.imgbox.com/qnUS37TF.jpg" /></a>
        #<a href="/PgEHrpIy"><img alt="Pgehrpiy" src="http://9.s.imgbox.com/PgEHrpIy.jpg" /></a>
        #<a href="/W2sv8pFp"><img alt="W2sv8pfp" src="http://3.s.imgbox.com/W2sv8pFp.jpg" /></a>

        if div_item_list:
            thumbs = parseDOM(div_item_list, "img", ret = "src" )
            href   = parseDOM(div_item_list,   "a", ret = "href" )

            #reassemble href into the image urls
            images = ('http://i.imgbox.com%s.jpg' %s for s in href)
            #self.assemble_images_dictList( images )

            #combine 2 list into 1 multidimensional list http://stackoverflow.com/questions/12624623/two-lists-into-one-multidimensional-list
            list3= map(list,zip( images, thumbs ))

            #assemble_images_dictList expects the 1st item to be the image title, we don't have one
            #add an additional column in out multidimensional list
            list3 = [['',i,t] for i,t in list3]

            #for i in list3:
            #    log('    ' + repr(i))

            #for i in images:
            #    log('    ' + i)

            self.assemble_images_dictList( list3 )
        else:
            log('      %s: cant find <div ... id="gallery-view-content"> '  %(self.__class__.__name__ ) )

        #log( pprint.pformat(self.dictList, indent=1) )
        return self.dictList

    def get_thumb_url(self):
        if self.thumb_url:
            return self.thumb_url

class ClassReddit(sitesBase):
    #matching /r/  /u/   and reddit.com
    regex='^\/r\/(.+)(?:\/|$)|(^\/u\/)(.+)(?:\/|$)|(reddit\.com)'

    def get_playable_url(self, link_url, is_probably_a_video):
        from . reddit import assemble_reddit_filter_string
        subreddit=self.get_video_id(link_url)
        self.video_id=subreddit
        #log('    **get_playable_url subreddit=' + self.video_id )

        self.media_type=sitesBase.TYPE_REDDIT

        #if link_url is in the form of https://np.reddit.com/r/teslamotors/comments/50bc6a/tesla_bumped_dying_man_up_the_production_queue_so/d72vfbg?context=2
        if '/comments/' in link_url:
            self.link_action='listLinksInComment'
            return link_url, self.media_type
        else:
            #link_url is in the form of "r/subreddit". this type of link is found in comments
            if subreddit:
                self.link_action='listSubReddit'
                reddit_url=assemble_reddit_filter_string('',subreddit)
                return reddit_url, self.media_type
            if link_url.startswith('/u/'):
                author=link_url.split('/u/')[1]
                self.link_action='listSubReddit'
                #show links submitted by author
                reddit_url=assemble_reddit_filter_string("","/user/"+author+'/submitted')
                return reddit_url, self.media_type
        return '',''
    @classmethod
    def get_video_id(self, reddit_url):
        #returns subreddit name
        match = re.findall( '^\/?r\/(.+?)(?:\/|$)|https?://(?:.+?\.)?reddit\.com\/r\/(.+?)(?:\/|$)' , reddit_url)
        #returns an array of tuples
        if match:
            for m in match[0]:
                if m: #just use the first non-empty match
                    return m

    def get_thumb_url(self):
        headers = {'User-Agent': reddit_userAgent}
        body_text=None
        from .utils import clean_str

        #log('get thumb url from '+self.original_url)
        if '/comments/' in self.original_url:
            #this is mainly for r/bestof. we extract the text and add it on the description
            u=self.original_url
            if '?' in self.original_url:
                url=self.original_url.split('?', 1)[0]+'.json?limit=1&'+self.original_url.split('?', 1)[1]
                u=self.original_url.replace('?','/')
            else:
                url=self.original_url+'.json?limit=1'
                if not self.original_url.endswith('/'):
                    u=self.original_url+'/'

            #determine whether the good info is in the post's 'selftext'(t3)  or the comment's 'body'
            #  link to comments(t1) have 2 id's in the url.
            #  link to posts(t3) only have 1 id

            #log(u);log(repr( u.count('/') ) )
            s_count=u.count('/')  #very crude way to determine how many id's in the url is to just count the '/' separators
            #if '64f9' in self.original_url:
            #    log('url= '+self.original_url)
            #    log(repr(j))

            if s_count > 8:#this is a comment (t1)
                r = self.requests_get( url, headers=headers)
                j=r.json()
                body_text=clean_str(j,[1,'data','children',0,'data','body']  )
            else:  #this is a post (t3)
                #we skip getting the selftext for posts
                #   t3 posts in r/bestof does not have selftext BUT other subreddit have them.
                #   this causes a duplicate and unnecessary bandwidth. --> r/bestof is not a big priority
                #body_text=clean_str(j,[0,'data','children',0,'data','selftext']  )
                pass

            self.description=body_text

        if self.video_id:
            #get subreddit icon_img, header_img or banner_img
            req='https://www.reddit.com/r/%s/about.json' %self.video_id
            #log( req )
            #log('headers:' + repr(headers))
            r = self.requests_get( req, headers=headers)
            j=r.json()
            j=j.get('data')
            #log( pprint.pformat(j, indent=1) )
            icon_img=j.get('icon_img')
            banner_img=j.get('banner_img')
            header_img=j.get('header_img')

            icon=next((item for item in [icon_img,header_img,banner_img] if item ), '')

            self.thumb_url=icon
            self.poster_url=banner_img

class ClassKindgirls(sitesBase):
    regex='(kindgirls.com)'

    def is_album(self, media_url):
        if '/gallery/' in media_url:
            self.media_type = self.TYPE_ALBUM
            return True
        else:
            return False

    def get_playable_url(self, link_url, is_probably_a_video=False ):

        if self.is_album(link_url):
            self.media_type = sitesBase.TYPE_ALBUM
            return link_url, self.media_type

        content = self.requests_get( link_url)

        #<meta id="metaTag" property="og:image" content="http://www.vidble.com/a9CvdmX9gu_sqr.jpeg"></meta>
        thumb= parseDOM(content.text, "meta", attrs = { "id": "metaTag" }, ret = "content")
        #log('    thumb='+repr(thumb))
        if thumb:
            self.thumb_url=thumb[0]

        div_item_list = parseDOM(content.text, "div", attrs = { "id": "photo" })

        #log('    div_item_list=' + repr(div_item_list))
        if div_item_list:
            images = parseDOM(div_item_list, "img", ret = "src")
            #for idx, item in enumerate(images):
            #    log('    %d %s' %(idx, item))
            if images[0]:
                self.thumb_url = images[0]
                self.poster_url= images[0]

                return self.poster_url, self.TYPE_IMAGE

        #try parsing for video
        div_video = parseDOM(content.text, "div", attrs = { "id": "cuerpo" })

        #log('    div_video=' + repr(div_video))
        if div_video:
            vid_thumb = parseDOM(div_video, "video", ret = "poster")
            #log('    vid=' + repr(vid_thumb))
            if vid_thumb:
                self.thumb_url='http://www.kindgirls.com'+vid_thumb[0]
                self.poster_url=self.thumb_url
            #determined that link leads to video. could parse it but we'll just send to ytdl
            self.link_action=sitesBase.DI_ACTION_YTDL
            self.media_type=sitesBase.TYPE_VIDEO
            return link_url, self.media_type

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem
        content = self.requests_get(album_url)
        images=[]
        div_item_list = parseDOM(content.text, "div", attrs = { "id": "cuerpo" })
        #log('      div_item_list=' + repr(div_item_list))

        if div_item_list:
            thumb_div=parseDOM(div_item_list, "div", attrs = { "id": "up_der" })
            #log( repr( thumb_div) )
            if thumb_div:
                #log('    thumb div')
                thumb = parseDOM(thumb_div,"a", ret="href")[0]
                if thumb:
                    self.thumb_url=thumb
                    self.poster_url=self.thumb_url
                    #log('    thumb:' + thumb )

            img_divs=parseDOM(div_item_list, "div", attrs = { "class": "gal_list" })

            if img_divs:
                for div in img_divs:
                    image_p     = parseDOM(div,"img", ret="src")[0]
                    image_title = parseDOM(div,"img", ret="title")[0]
                    image_o     = parseDOM(div,"a", attrs={ "target":"_blank"}, ret="href")[0]

                    images.append( [image_title, image_o, image_p]  )

            #for i in images: log( repr(i) )
            self.assemble_images_dictList( images )
            #log( pprint.pformat(self.dictList, indent=1) )

        else:
            log("      can't find div id cuerpo")

        #log( pprint.pformat(self.dictList, indent=1) )
        return self.dictList

    def get_thumb_url(self):
        #log('    get thumb [%s]' %self.thumb_url )
        if self.thumb_url:
            return self.thumb_url

        #log('    checking if album')
        if self.is_album(self.original_url):
            #log('    is album')
            #this also gets the thumb and poster url's
            self.ret_album_list( self.original_url )
            return self.thumb_url

class Class500px(sitesBase):
    regex='(500px.com)'

    key_string='consumer_key=aKLU1q5GKofJ2RDsNVEJScLy98aLKNmm7lADwOSB'

    def is_album(self, media_url):
        if '/galleries/' in media_url:
            self.media_type = self.TYPE_ALBUM
            return True
        else:
            return False

    def get_thumb_url(self):

        self.get_photo_info()

        if self.poster_url:
            return self.poster_url

        return ''

    def get_photo_info(self, photo_url=''):
        if not photo_url:
            photo_url=self.media_url

        self.get_video_id()
        #log('    videoID:' + self.video_id)
        if self.video_id:
            #image_size — Numerical size of the image to link to, 1 being the smallest and 4 being the largest.
            api_url= 'https://api.500px.com/v1/photos/%s?image_size=6&%s' %(self.video_id, self.key_string)
            #log( '    ' + api_url )
            r = self.requests_get(api_url)
            #log(r.text)

            j=json.loads(r.text)   #.replace('\\"', '\'')
            j=j.get('photo')

            #title=j.get('name')
            self.poster_url=j.get('image_url')
            self.media_w=j.get('width')  #width and height not accurate unless image size 6  (not sure if applies to all)
            self.media_h=j.get('height')
            self.media_url=self.poster_url

            #log('      %s %dx%d %s' %(title, self.media_w,self.media_h, self.poster_url )  )
            #return self.poster_url, sitesBase.TYPE_IMAGE
        else:
            log("    %s cannot get videoID %s" %( self.__class__.__name__, self.original_url) )


    def get_playable_url(self, media_url, is_probably_a_video=True ):
        #log('    class 500px prep media url')

        if self.is_album(media_url):
            return media_url, sitesBase.TYPE_ALBUM

        self.get_photo_info()

        if self.poster_url:
            return self.poster_url, sitesBase.TYPE_IMAGE

        return '',''

    def get_video_id(self):
        self.video_id=''
        #match = re.findall( '500px\.com/(?:photo)/(.+)(?:/|$)' , self.original_url)
        match = re.findall( '500px\.com/photo/(.+?)(?:\/|$)' , self.original_url)
        #log('    '+ repr(match) )
        if match:
            self.video_id=match[0]

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem

        #first query for the user id then call the request that gets the image list

        #gallery links look like this:
        #  https://500px.com/seanarcher/galleries/outdoor-portraits
        #  https://500px.com/mikimacovei/galleries/favorites
        #result = re.search('500px\.com/(.*?)/galleries', self.original_url)
        result = re.search('500px\.com/(.*?)/(.+)?', self.original_url)
        username  =result.group(1)
        album_name=result.group(2)
        log('    username:%s album:%s' %(username, album_name) )

        api_call='https://api.500px.com/v1/users/show?username=%s&%s' %(username, self.key_string)
        log('    req='+api_call)
        r = self.requests_get(api_call)

        j=r.json()
        user_id=j.get('user').get('id')

        if user_id:
            #         https://api.500px.com/v1/users/777395/galleries/outdoor-portraits/items?consumer_key=aKLU1q5GKofJ2RDsNVEJScLy98aLKNmm7lADwOSB
            api_call='https://api.500px.com/v1/users/%s/%s/items?image_size=6&rpp=100&%s' %(user_id, album_name, self.key_string)
            log('    req='+api_call)
            r = self.requests_get(api_call)
            #log( r.text )
            images=[]
            j=r.json()
            j=j.get('photos')
            for photo in j:
                title=photo.get('name')
                description=photo.get('description')
                image=photo.get('image_url')
                width=photo.get('width')
                height=photo.get('height')
                #combined=self.combine_title_and_description(title, description)

                #images.append( [combined, image ]  )
                images.append( {'title': title,
                                'description': description,
                                'url': image,
                                'width': width,
                                'height': height,
                                }  )


            #for i in images: log( repr(i) )
            self.assemble_images_dictList( images )
            #log( pprint.pformat(self.dictList, indent=1) )
        else:
            log("    can't get user id")
            return
        return self.dictList

class ClassSlimg(sitesBase):
    regex='(sli.mg)'

    #header='Authorization: Client-ID {YOUR_CLIENT_ID}'
    header={'Authorization': 'Client-ID M5assQr4h9pj1xQNJ6ehAEXuDq27RsYE'}
    #api_key='M5assQr4h9pj1xQNJ6ehAEXuDq27RsYE'

    def is_album(self, link_url):
        if '/a/' in link_url:
            self.media_type = self.TYPE_ALBUM
            return True
        else:
            return False

    def get_playable_url(self, link_url, is_probably_a_video):

        if self.is_album(link_url):
            return link_url, sitesBase.TYPE_ALBUM

        self.get_video_id()

        api_req='https://api.sli.mg/media/' + self.video_id
        #log('  ' + api_req )
        r = self.requests_get(api_req, headers=self.header)

        j=r.json()
        j=j.get('data')
        self.media_url=j.get('url_direct')
        self.thumb_url=self.media_url
        self.poster_url=self.media_url

        self.media_w=j.get('width')
        self.media_h=j.get('height')

        if j.get('webm'):  #use webm if available.
            self.link_action=sitesBase.DI_ACTION_PLAYABLE
            self.media_type=sitesBase.TYPE_VIDEO
            self.media_url=j.get('url_webm')
        else:  #we're assuming that all items without a webm is image
            self.media_type=sitesBase.TYPE_IMAGE

        #if 'gif' in j.get('mimetype'):
        #    self.media_url=j.get('url_mp4')   #url_webm is also available

        return self.media_url, self.media_type

    def get_video_id(self):
        #looks like the filename is also the video id
        self.video_id=''

        match = re.compile('sli\.mg/(?:a/|album/)?(.+)').findall(self.media_url)
        #log('    matches' + repr(match) )
        if match:
            self.video_id=match[0]

    def get_thumb_url(self):
        if self.thumb_url:
            return self.thumb_url

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        self.get_video_id()

        api_req='https://api.sli.mg/album/%s/media' % self.video_id
        #log('  ' + api_req )
        r = self.requests_get(api_req, headers=self.header)

        j=r.json()
        j=j.get('data')

        #media_count=j.get('media_count')
        images=[]
        for i in j.get('media'):

            title=i.get('title')
            description=i.get('description')
            media_url=i.get('url_direct')
            media_w=i.get('width')
            media_h=i.get('height')
            #combined='[B]%s[/B]\n%s' % (title, description)

            #combined= self.combine_title_and_description(title,description)

            if i.get('webm'):  #we don't support video in album but still avoid gif video  if possible.
                media_url=j.get('url_webm')

            images.append( {'title': title,
                            'description': description,
                            'url': media_url,
                            'width': media_w,
                            'height': media_h,
                            }  )

        self.assemble_images_dictList(images)

        return self.dictList

# class Deviantart(sitesBase):
#     regex='(deviantart.com)|(sta.sh)'
#
#     clientid='5198'
#
#     def get_playable_url(self, media_url, is_probably_a_video):
#         pass
#
#     def get_thumb_url(self):
#         pass
#
#     def ret_album_list(self, album_url, thumbnail_size_code=''):
#         pass

class ClassImgTrex(sitesBase):
    SITE='imgtrex'
    regex='(imgtrex.com)'

    include_gif_in_get_playable=True

    #imgtrex is devious in that the link has a .jpg .gif extension but it actually leads to an html page.
    #  we need to parse the html to get the actual image
    def get_playable(self, media_url='', is_probably_a_video=False ):
        if not media_url:
            media_url=self.media_url
        return self.get_playable_url(self.media_url, is_probably_a_video=False )

    def get_playable_url(self, link_url, is_probably_a_video=False ):
        content = self.requests_get(link_url)

        #is_album=parseDOM(content.text, name='img', attrs = { "class": "pic" }, ret='galleryimg' )  #this should return "no" but does not
        #log( '  isalbum:' + pprint.pformat(is_album, indent=1) )
        #add album checking code here. i think the galleryimg property in the img tag holds a clue but can't find gallery sample

        image=parseDOM(content.text, name='img', attrs = { "class": "pic" }, ret="src")
        #log( '  ' + repr(image ) )
        #if 'sYS' in link_url: log( repr(image) )
        if image[0]:
            #***** there were instances where imgtrex returned image extension as .jpg but it is actually .gif.    we can't do anything about this.
            self.set_media_type_thumb_and_action(image[0])
            return self.media_url, self.media_type

    def get_thumb_url(self):
        pass

class ClassImgFlip(sitesBase):
    SITE='imgflip'
    regex='(imgflip.com)'
    include_gif_in_get_playable=True

    def get_playable_url(self, link_url, is_probably_a_video=False ):
        content = self.requests_get(link_url)
        i=parseDOM(content.text, "meta", attrs = { "property": "og:image" }, ret="content" )
        iw=parseDOM(content.text, "meta", attrs = { "property": "og:image:width" }, ret="content" )
        ih=parseDOM(content.text, "meta", attrs = { "property": "og:image:height" }, ret="content" )
        if i:
            image=i[0]
            self.set_media_type_thumb_and_action(image)
            self.media_w=iw[0]
            self.media_h=ih[0]
            return self.media_url,self.media_type
        else:
            log('      %s: cant find <meta property'  %(self.__class__.__name__ ) )

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        return None

    def get_thumb_url(self):
        pass

class ClassSupload(sitesBase):
    regex='(supload.com)'

    def get_playable_url(self, link_url, is_probably_a_video=False ):
        self.media_url=link_url

        #u=media_url.split('?')[0]
        html=self.requests_get(link_url)

        meta_og_type=parseDOM(html.text, "meta", attrs = { "property": "og:type" }, ret="content" )
        og_image_list=parseDOM(html.text, "meta", attrs = { "property": "og:image" }, ret="content" )

        #if 'o9g' in link_url:log(repr(meta_og_type)+'\n'+repr(og_image_list))
        if og_image_list:
            og_image=og_image_list[0]
            self.thumb_url=og_image
            self.poster_url=og_image
        else:
            log('      %s: cant find <meta property="og:image" '  %(self.__class__.__name__ ) )

        if meta_og_type:
            meta_og_type=meta_og_type[0]
            if meta_og_type=='image':
                self.media_type=sitesBase.TYPE_IMAGE
                self.media_url=og_image
            elif meta_og_type=='video':
                self.media_type=sitesBase.TYPE_VIDEO
            else:
                log('      unknown meta og type:'+meta_og_type)
        else:
            log('      no meta og type')
            raise Exception("Could not determine media type" )

        #og image is not good enough. we try to retrieve a better image by parsing html
        section_imageWrapper=parseDOM(html.text, "section", attrs = { "class": "imageWrapper" }, ret=None )
        #if 'o9g' in link_url: log( pprint.pformat(section_imageWrapper) )
        if section_imageWrapper:
            if meta_og_type=='image':
                #can also parse <a href for best image quality
                #srcset=parseDOM(section_imageWrapper, "img", attrs={}, ret='srcset' )
                #if 'xr9g' in link_url: log( pprint.pformat(srcset) )
                img=parseDOM(section_imageWrapper, "img", attrs={}, ret='src' )
                if img:
                    self.set_media_type_thumb_and_action(img[0])
            elif meta_og_type=='video':
                video_url=parseDOM(html.text, "meta", attrs = { "property": "og:video" }, ret="content" )
                #if 'o9g' in link_url: log( repr(video_url) )
                if video_url:
                    self.set_media_type_thumb_and_action(video_url[0])
                    #supload classify gif as video. we need to determine if video is a gif so that we'll call looped playback
                    #  in the og_image header, if it is a gif, there will be 2  og_image. one is jpg, other is a gif.
                    #      we test for the presence of this .gif
                    if self.is_a_gif(og_image_list):
                        #override the media type assigned by set_media_type_thumb_and_action() from video to gif
                        self.media_type=sitesBase.TYPE_GIF


        #log( '['+self.media_type+']:'+self.media_url)
        return self.media_url, self.media_type

    def get_thumb_url(self):
        self.thumb_url=self.media_url
        self.poster_url=self.media_url
        return self.thumb_url

    @classmethod
    def is_a_gif(self, og_image_list):
        for i in og_image_list:
            if '.gif' in i:
                return True
        return False

class ClassAcidcow(sitesBase):
    regex='(acidcow.com)'

    include_gif_in_get_playable=True
    p=['acidcow.com', '', ['div', { "class": "newsarea" },None],
                        ['div', {"class": "fb-like"}, "data-image"]
        ]

    def get_playable_url(self, link_url, is_probably_a_video=False ):
        self.media_url=link_url

        #u=media_url.split('?')[0]
        html=self.requests_get(link_url)
        #if '11616' in link_url:log(html.text)

        images=self.get_images(html.text,self.p)
        if images:
            #if '11616' in link_url:log(pprint.pformat(images))
            self.media_type=self.TYPE_ALBUM
            return self.media_url, self.media_type
        else:
            #default to youtube-dl video.
            #direct image link posts are already taken care of in get_playable()
            #the only video sample i found is not playable via ytdl. TODO: .mp4 is in javascript block
            #    http://acidcow.com/video/61149-russian_soldiers_got_the_steel_balls.html
            self.link_action=self.DI_ACTION_YTDL
            return self.media_url, self.TYPE_VIDEO

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        html=self.requests_get(album_url)

        images=self.get_images(html.text,self.p)
        if images:
            #TODO: parse image descriptions --http://acidcow.com/pics/83717-the-top-15-most-evil-and-ruthless-cult-leaders-from-history-15-pics.html
            self.assemble_images_dictList(images)
            return self.dictList

    def get_images(self, html, p):
        images=[]
        #log( '***name=%s, attrs=%s, ret=%s)' %(p[2][0], p[2][1], p[2][2]))
        big_div=parseDOM(html, name=p[2][0], attrs=p[2][1], ret=p[2][2])
        if big_div:
            #log('     %d     big_div=%s' %( len(big_div), pprint.pformat(big_div)) )
            imgs = parseDOM(big_div,name=p[3][0], attrs=p[3][1], ret=p[3][2])
            #imgs = parseDOM(big_div,name='img', attrs={}, ret='src')
            #log('     %d       imags=%s' %( len(imgs)   , pprint.pformat(imgs) )   )
            #images.append(imgs)
            images.extend(imgs)

        return images

    def get_thumb_url(self):
        self.thumb_url=self.media_url
        self.poster_url=self.media_url
        return self.thumb_url

class genericAlbum1(sitesBase):
    regex='(http://www.houseofsummersville.com/)|(weirdrussia.com)|(cheezburger.com)|(hentailair.xyz)|(designyoutrust.com)'
    #links are checked for valid image extensions. use no_ext to bypass this check

    ps=[  [ 'houseofsummersville.com', '',          ['div', { "dir": "ltr" },None],
                                                    ['div', { "class": "separator" },None],
                                                    ['a', {}, "href"]
            ],
          [         'weirdrussia.com', '',          ['div', { "class": "thecontent clearfix" },None],
                                                    ['img', {}, "data-layzr"]
            ],
          [         'cheezburger.com', 'no_ext',    ['div', { "class": "nw-post-asset" },None],
                                                   # ['li', { "class": "list-asset-item" },None],
                                                    ['img', {}, "src"]
            ],
          [         'hentailair.xyz', '',           ['div', { "class": "box-inner-block" },None],   # with hentailair.xyz->imgtrex the actual image is in  the style attribute of the img tag
                                                    ['a', {}, "style"]                              #  "background-image: url('http://raptor.imgtrex.com/i/01882/gntod25j7lcf_t.jpg'); background-size: cover; background-position: 50% 50%; background-repeat: no-repeat;"
            ],
          [     'designyoutrust.com', '',          ['div', { "class": "mainpost" },None],
                                                    ['img', {}, "src"]
            ],
        ]


    def get_playable_url(self, link_url, is_probably_a_video=False ):
        return link_url, self.TYPE_ALBUM

    def get_thumb_url(self):
        img=self.request_meta_ogimage_content()
        self.thumb_url=img
        self.poster_url=self.thumb_url

    def ret_album_list(self, album_url, thumbnail_size_code=''):
        #returns an object (list of dicts) that contain info for the calling function to create the listitem/addDirectoryItem

        for p in self.ps:
            if p[0] in album_url:
                break

        html = self.get_html( album_url )
        if html:
            images=self.get_images(html, p)
            #for i in images: log( '      ' + repr(i) )
            #log( pprint.pformat(self.dictList, indent=1) )
            self.assemble_images_dictList( images )

        return self.dictList

    def get_images(self, html, p):
        log(    'len %d' %(len(p)) )
        p_options=p[1]
        images=[]
        if len(p)==5:
            div_item_list = parseDOM(html, name=p[2][0], attrs = p[2][1], ret=p[2][2] )
            #log('        div_item_list=' + repr(div_item_list))
            if div_item_list:
                #img_divs=parseDOM(div_item_list, name="div", attrs = { "class": "separator" }, ret=None)
                img_divs=parseDOM(div_item_list, name=p[3][0], attrs=p[3][1], ret=p[3][2])
                if img_divs:
                    #log('          img_divs=' + repr(img_divs))
                    for div in img_divs:
                        #log('          img_div=' + repr(div))
                        #image_p     = parseDOM(div,"img", ret="src")[0]
                        #image_title = parseDOM(div,"img", ret="title")[0]
                        #image_o     = parseDOM(div,name="a", attrs={}, ret="href")
                        image_o      = parseDOM(div,name=p[4][0], attrs=p[4][1], ret=p[4][2])
                        #log('          image_o=' + repr(image_o))
                        if image_o:
                            if p_options=='no_ext':   #don't check for image extensions
                                images.append( image_o[0] )
                            else:
                                if link_url_is_playable( image_o[0] ) == 'image':
                                    #log('          appending:' + repr(image_o))
                                    images.append( image_o[0] )
        elif len(p)==4:
            #log( '***name=%s, attrs=%s, ret=%s)' %(p[2][0], p[2][1], p[2][2]))
            big_div=parseDOM(html, name=p[2][0], attrs=p[2][1], ret=p[2][2])
            if big_div:
                #log('     %d     big_div=%s' %( len(big_div), pprint.pformat(big_div)) )
                imgs = parseDOM(big_div,name=p[3][0], attrs=p[3][1], ret=p[3][2])
                #imgs = parseDOM(big_div,name='img', attrs={}, ret='src')
                #log('     %d       imags=%s' %( len(imgs)   , pprint.pformat(imgs) )   )
                self.append_imgs( imgs, p, images)
        elif len(p)==3:
            #log( '***name=%s, attrs=%s, ret=%s)' %(p[1][0], p[1][1], p[1][2]))
            imgs=parseDOM(html, name=p[2][0], attrs=p[2][1], ret=p[2][2])
            self.append_imgs( imgs, p, images)

        return images

    def append_imgs(self, imgs, p, images_list):
        p_options=p[1]
        if imgs:
            for i in imgs:
                #log('          i=' + repr(i))
                if i:
                    i=self.get_first_url_from(i)   # this is added for hentailair.xyz the actual image is in the style attribute of the img tag. probably fine for others
                    #log('         *i=' + repr(i))
                    if p_options=='no_ext':   #don't check for image extensions
                        images_list.append( i )
                    else:
                        if link_url_is_playable( i ) == 'image':
                            images_list.append( i )

class smb(sitesBase):
    regex='(^smb:\/\/)'
    def get_thumb_url(self):
        pass
    def get_playable(self, link_url='', is_probably_a_video=False ):
        self.link_action=self.DI_ACTION_PLAYABLE
        return link_url,self.TYPE_VIDEO

    def get_playable_url(self, link_url, is_probably_a_video):
        pass

class local(sitesBase):
    regex=r"^(?:[a-zA-Z]\:|\\\\[\w\.]+\\[\w.$]+)\\"  #^(?:[a-zA-Z]\:|\\\\[\w\.]+\\[\w.$]+)\\(?:[\w]+\\)*\w([\w.])+$'
    def get_thumb_url(self):
        pass
    def get_playable(self, link_url='', is_probably_a_video=False ):
        self.link_action=self.DI_ACTION_PLAYABLE
        return link_url,self.TYPE_VIDEO
    def get_playable_url(self, link_url, is_probably_a_video):
        pass

class genericImage(sitesBase):
    regex='(i.redd.it/)|(RedditUploads)|(RedditMedia)|(\.(jpg|jpeg|png|gif)(?:\?|$))'

    def get_playable_url(self, link_url, is_probably_a_video=False ):
        media_url=link_url.replace('&amp;','&')  #this replace is only for  RedditUploads but seems harmless for the others...
        self.media_url=media_url

        u=media_url.split('?')[0]
        self.set_media_type_thumb_and_action(u,
                                             default_type=self.TYPE_IMAGE,
                                             default_action='')
        #note that we didn't use self.media_url below  (u is assigned to self.media_url upon calling set_media_type_thumb_and_action()
        #RedditUploads require all the stuff after the image to work
        return media_url, self.media_type

    def get_thumb_url(self):
        self.thumb_url=self.media_url
        self.poster_url=self.media_url
        return self.thumb_url

class genericVideo(sitesBase):
    regex='(v.redd.it/)|(\.(mp4|webm|avi|3gp|gif|MPEG|WMV|ASF|FLV|MKV|MKA)(?:\?|$))'
    def get_thumb_url(self):
        pass

    def get_playable(self, link_url='', is_probably_a_video=False ):
        if not link_url:
            link_url=self.media_url

        self.set_media_type_thumb_and_action(link_url)
        if url_resolver_support(link_url):
            self.link_action=self.DI_ACTION_URLR
            self.media_type=self.TYPE_VIDEO

        return self.media_url,self.media_type

    def get_playable_url(self, link_url, is_probably_a_video):
        pass


class LinkDetails():
    def __init__(self, media_type, link_action, playable_url='', thumb='', poster='', poster_w=0, poster_h=0, dictlist=None, description='' , video_id=''):
        #self.kodi_url = kodi_url
        self.playable_url = playable_url
        self.media_type = media_type
        self.link_action = link_action
        self.thumb = thumb
        self.poster = poster
        self.poster_w = poster_w
        self.poster_h = poster_h
        self.dictlist = dictlist #for img albums
        self.desctiption=description #for text gathered from link to present to the user. (r/bestof comment body for now)
        self.video_id=video_id   #for youtube video id

def sitesManager( media_url ):
    #picks which class will handle the media identification and extraction for website_name

    #first resolve url shortener
    shorteners=['bit.ly','goo.gl','tinyurl.com']
    if any(shortener in media_url for shortener in shorteners):
        #v=sitesBase.requests_get('https://unshorten.me/s/'+ urllib.quote_plus( media_url ) )
        v = requests.head( media_url, timeout=REQUEST_TIMEOUT, allow_redirects=True )
        log('  short url(%s)=%s'%(media_url,repr(v.url)))
        media_url=v.url

    for subcls in sitesBase.__subclasses__():
        regex=subcls.regex
        if regex:
            match=re.compile( regex  , re.I).findall( media_url )
            if match :
                return subcls( media_url )

def parse_reddit_link(link_url, assume_is_video=True, needs_preview=False, get_playable_url=False, image_ar=0 ):
    if not link_url: return

    album_dict_list=None
    hoster = sitesManager( link_url )
    #log( '  %s %s => %s' %(hoster.__class__.__name__, link_url, hoster.media_url if hoster else '[Not supported]' ) )

    try:
        if hoster:
            hoster.dictList=[]  #make sure the dictlist is empty otherwise we end up appending for every post
            if get_playable_url:
                pass

            prepped_media_url, media_type = hoster.get_playable(link_url, assume_is_video)
            #log( '    parsed: [%s] type=%s url=%s ' % ( hoster.link_action, media_type,  prepped_media_url ) )
            if not prepped_media_url:
                log("  Failed to parse %s" %(link_url) )

            if needs_preview:
                hoster.get_thumb_url()

            if not hoster.link_action:
                if media_type==sitesBase.TYPE_IMAGE:
                    if image_ar>0 and image_ar < 0.4: #special action for tall images
                        hoster.link_action='viewTallImage'
                    else:
                        hoster.link_action='viewImage'

                if media_type==sitesBase.TYPE_ALBUM:
                    album_dict_list=hoster.dictList
                    hoster.link_action='listAlbum'

            ld=LinkDetails(media_type, hoster.link_action, prepped_media_url, hoster.thumb_url, hoster.poster_url, dictlist=album_dict_list,description=hoster.description  )
            return ld

        else:
            if url_resolver_support(link_url):
                ld=LinkDetails(sitesBase.TYPE_VIDEO, sitesBase.DI_ACTION_URLR, link_url, '', '')
                return ld

            if False: #resolve_undetermined:  (abandoned, too slow)
                log('sending undetermined link to ytdl...')
                media_url=ydtl_get_playable_url(link_url)
                if media_url:
                    ld=LinkDetails(sitesBase.TYPE_VIDEO, sitesBase.DI_ACTION_PLAYABLE, media_url[0], '', '')
                    return ld

    except Exception as e:
        log("  EXCEPTION parse_reddit_link "+ str( sys.exc_info()[0]) + " - " + str(e) )
        ld=LinkDetails('', sitesBase.DI_ACTION_ERROR, str(e) )
        return ld


#    if ytdl_sites:  pass
#    else: load_ytdl_sites()
#
#    ytdl_match=False
#    for rex in ytdl_sites:
#        #if rex.startswith('f'):log( ' rex=='+ rex )
#        if rex in link_url:
#            #log( "    ydtl-" + rex +" matched IN>"+ media_url)
#            hoster=rex
#            ytdl_match=True
#            break
#        #regex is much slower than the method above.. left here in case needed in the future
#        # match = re.compile( "(%s)" %rex  , re.DOTALL).findall( media_url )
#        # if match : log( "matched ytdl:"+ rex);  break
#    if ytdl_match:
#        ld=LinkDetails(sitesBase.TYPE_VIDEO, 'playYTDLVideo', link_url, '', '')
#        return ld

#def url_is_supported(url_to_check):
#    #search our supported_sites[] to see if media_url can be handled by plugin
#    #log('    ?url_is_supported:'+ url_to_check)
#    dont_support=False
#    #if ytdl_sites:  pass
#    #else: load_ytdl_sites()
#
#    hoster = sitesManager( url_to_check )
#    if hoster:
#        log( '  url_is_supported by: %s %s ' %(hoster.__class__.__name__, url_to_check ) )
#        return True
#
##    #if this setting is set to true, all links are supported. it is up to ytdl to see if it actually plays
##    if use_ytdl_for_unknown_in_comments:
##        return True
##
##    #originally ytdl sites were matched in supported sites[] but it is getting so big that it is moved to a separate configurable file.
##    #check if it matches ytdl sites
##    for rex in ytdl_sites:
##        if rex in url_to_check:
##            #log( "    ydtl-" + rex +" matched IN>"+ media_url)
##            #hoster=rex
##            return True
##
##        #regex is much slower than the method above.. left here in case needed in the future
##        # match = re.compile( "(%s)" %rex  , re.DOTALL).findall( media_url )
##        # if match : log( "matched ytdl:"+ rex);  break
#
#    if url_to_check.startswith('/r/'):
#        return True
#
#    return True #False

#def load_ytdl_sites():
#    #log( '***************load_ytdl_sites '  )
#    #reads the ytdl supported sites file
#    #http://stackoverflow.com/questions/1706198/python-how-to-ignore-comment-lines-when-reading-in-a-file
#    global ytdl_sites
#    with open(default_ytdl_psites_file) as f:   #ytdl_psites_file=special://profile/addon_data/script.reddit.reader/ytdl_psites_file
#        for line in f:
#            line = line.split('#', 1)[0]
#            line = line.rstrip()
#            ytdl_sites.append(line)
#
#    with open(default_ytdl_sites_file) as f:   #ytdl_psites_file=special://profile/addon_data/script.reddit.reader/ytdl_psites_file
#        for line in f:
#            line = line.split('#', 1)[0]
#            line = line.rstrip()
#            ytdl_sites.append(line)
#
#
#def ytdl_hoster( url_to_check ):
#    pass


def ydtl_get_playable_url( url_to_check ):
    from .utils import link_url_is_playable
    from .default import YDStreamExtractor
    #log('ydtl_get_playable_url:' +url_to_check )
    if link_url_is_playable(url_to_check)=='video':
        return url_to_check

    choices = []

    if YDStreamExtractor.mightHaveVideo(url_to_check,resolve_redirects=True):
        #log('      YDStreamExtractor.mightHaveVideo[true]=' + url_to_check)
        #xbmc_busy()
        #https://github.com/ruuk/script.module.youtube.dl/blob/master/lib/YoutubeDLWrapper.py
        vid = YDStreamExtractor.getVideoInfo(url_to_check,0,True)  #quality is 0=SD, 1=720p, 2=1080p and is a maximum
        if vid:
            #log("        getVideoInfo playableURL="+vid.streamURL())
            #log("        %s  %s %s" %( vid.sourceName , vid.description, vid.thumbnail ))   #usually just 'generic' and blank on everything else
            if vid.hasMultipleStreams():
                #vid.info  <-- The info property contains the original youtube-dl info
                log("          video hasMultipleStreams %d" %len(vid._streams) )
                for s in vid.streams():
                    title = s['title']
                    #log('            choices: %s... %s' %( title.ljust(15)[:15], s['xbmc_url']  )   )
                    choices.append(s['xbmc_url'])
                #index = some_function_asking_the_user_to_choose(choices)
                #vid.selectStream(0) #You can also pass in the the dict for the chosen stream
                #return choices  #vid.streamURL()

            choices.append(vid.streamURL())
            return choices

    return None

if __name__ == '__main__':
    pass
        #name='' if name==None else name.         decode('unicode_escape').encode('ascii','ignore')
        #name='' if name==None else name.encode().decode("unicode-escape").encode('ascii','ignore')

def build_DirectoryItem_url_based_on_media_type(ld, url, arg_name='', arg_type='', script_to_call="", on_autoplay=False, img_w=0, img_h=0):
    setProperty_IsPlayable='false'  #recorded in vieoxxx.db if set to 'true'
    isFolder=True
    DirectoryItem_url=''
    title_prefix=''
    url='' if url==None else url.encode().decode('unicode_escape').encode('ascii','ignore')
    arg_name=arg_name.encode('utf-8')             #sometimes we pass the title of the post on &name=. need to encode('utf-8') here otherwise we get a keyError
    if ld:
        if ld.media_type==sitesBase.TYPE_IMAGE:
            if addon.getSetting("hide_IMG") == "true": return
            title_prefix='[IMG]'
            isFolder=False
            if ld.link_action=='viewTallImage':  #viewTallImage uses/needs the name and type arg to hold the image width and height
                arg_name=str(img_w)
                arg_type=str(img_h)

        elif ld.media_type==sitesBase.TYPE_ALBUM:
            if addon.getSetting("hide_IMG") == "true": return
            title_prefix='[ALBUM]'
            isFolder=True

        elif ld.media_type==sitesBase.TYPE_REDDIT:
            if addon.getSetting("hide_reddit") == "true": return
            title_prefix='[Reddit]'
            isFolder=True

        elif ld.media_type==sitesBase.TYPE_VIDEO:
            if addon.getSetting("hide_video") == "true": return
            setProperty_IsPlayable='true'
            isFolder=False
            #exception to loop gifs

        elif ld.media_type==sitesBase.TYPE_VIDS:
            if addon.getSetting("hide_video") == "true": return
            #setProperty_IsPlayable='true'
            title_prefix='[ALBUM]'   #treat link with multiple video as album
            ld.link_action='listAlbum'
            isFolder=True

        elif ld.media_type==sitesBase.TYPE_GIF:
            if addon.getSetting("hide_video") == "true": return
            if on_autoplay:
                #method used to play video in loopedPlayback() does not work on autoplay
                #setProperty_IsPlayable='true'
                #isFolder=False
                pass
            else:
                ld.link_action = 'loopedPlayback'
                setProperty_IsPlayable='false'
                #title_prefix='[Gif]'
                isFolder=False
            #else:
            #    setProperty_IsPlayable='true'
            #    isFolder=False
            #log('  %s:%s'%(ld.link_action,ld.playable_url))
        elif ld.media_type=='' or ld.media_type==None:  #ld.link_action=sitesBase.DI_ACTION_ERROR
#            #when there is an error resolving the post link
            setProperty_IsPlayable='false'
            isFolder=False

        if ld.link_action == sitesBase.DI_ACTION_PLAYABLE:
            setProperty_IsPlayable='true'
            isFolder=False
            DirectoryItem_url=ld.playable_url
        else:
            DirectoryItem_url=sys.argv[0]\
            +"?url="+ urllib.parse.quote_plus(ld.playable_url) \
            +"&mode="+urllib.parse.quote_plus(ld.link_action) \
            +"&name="+urllib.parse.quote_plus(arg_name) \
            +"&type="+urllib.parse.quote_plus(arg_type)
    else:
        if addon.getSetting("hide_undetermined") == "true": return
        title_prefix='[?]'
        #***NOTE: if a ytdl link resolves into multiple streams. it 'should' be added into a playlist and xbmc.Player().play(playlist, windowed=False)  setProperty_IsPlayable='false'
        #         if it resolves into a single stream. we CAN also put it in a playlist and handle it just like multiple streams
        #         BUT this breaks the 'play all' function.
        #            there are not that many links that resolve to multiple streams and more users use the 'play all' function so
        #            we choose to not handle playing multiple links
        setProperty_IsPlayable='true'  #pluginhandle=-1 if set to 'false' and isFolder set to False
        isFolder=False                 #isFolder=True avoids the WARNING: XFILE::CFileFactory::CreateLoader /  ERROR: InputStream: Error opening, ...
        DirectoryItem_url=sys.argv[0]\
        +"?url="+ urllib.parse.quote_plus(url) \
        +"&name="+urllib.parse.quote_plus(arg_name) \
        +"&mode=playYTDLVideo"

    return DirectoryItem_url, setProperty_IsPlayable, isFolder, title_prefix

'''
#special credit to https://www.reddit.com/r/learnpython/comments/4pl11h/dynamically_instantiate_class_from_class_method/
# 6/24/2016 - this portion abandoned because it takes a long time to process.
# dynamically instantiate a classes based on url. similar to how youtube_dl parses media content
class hosterBase(object):

    def __init__(self, url):
        self.url = url

    @classmethod
    def from_url(cls, url):
        for subclass in cls.__subclasses__():
            if subclass.recc.match(url):
                return subclass(url)
            #if re.match(subclass.regex, url):   #            if sub.regex in url:
            #    return subclass(url)
        #raise ValueError('wtf is {}'.format(url))

#     @staticmethod
#     def from_url(url):
#         for cls in hosterBase.__subclasses__():
#             if re.match(cls.regex, url):
#                 return cls(url)
#         raise ValueError("URL %r does not match any image hosts" % url)


class cVidme(hosterBase):
    regex = 'https?://vid\.me/(?:e/)?(?P<id>[\da-zA-Z]*)'
    recc=re.compile(regex)

class b(hosterBase):
    regex = 'bbb'
    recc=re.compile(regex)


#you call this class like:

    m = hosterBase.from_url(media_url)
    log("  "+str(m))
    if m:
        a = m.get_playable_url(media_url, assume_is_video)
        log("  " + a)
        #return


'''

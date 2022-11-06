# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs
import sys
import shutil, os
import re, urllib.request, urllib.parse, urllib.error
import pprint
import json
import urllib.parse

from default import subredditsFile, addon, addon_path, profile_path, ytdl_core_path, pluginhandle, subredditsPickle
from .utils import xbmc_busy, log, translation, xbmc_notify
from .reddit import get_subreddit_entry_info

ytdl_quality=addon.getSetting("ytdl_quality")
try: ytdl_quality=[0, 1, 2, 3][ int(ytdl_quality) ]
except ValueError: ytdl_quality=1
ytdl_DASH=addon.getSetting("ytdl_DASH")=='true'

def addSubreddit(subreddit, name, type_):
    from .utils import colored_subreddit
    from .reddit import this_is_a_multireddit, format_multihub
    alreadyIn = False
    with open(subredditsFile, 'r') as fh:
        content = fh.readlines()
    if subreddit:
        for line in content:
            if line.lower()==subreddit.lower():
                alreadyIn = True
        if not alreadyIn:
            with open(subredditsFile, 'a') as fh:
                fh.write(subreddit+'\n')

            get_subreddit_entry_info(subreddit)
        xbmc_notify(colored_subreddit(subreddit), translation(30019))
    else:
        #dialog = xbmcgui.Dialog()
        #ok = dialog.ok('Add subreddit', 'Add a subreddit (videos)','or  Multiple subreddits (music+listentothis)','or  Multireddit (/user/.../m/video)')
        #would be great to have some sort of help to show first time user here

        keyboard = xbmc.Keyboard('', translation(30001))
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            subreddit = keyboard.getText()

            #cleanup user input. make sure /user/ and /m/ is lowercase
            if this_is_a_multireddit(subreddit):
                subreddit = format_multihub(subreddit)
            else:
                get_subreddit_entry_info(subreddit)

            for line in content:
                if line.lower()==subreddit.lower()+"\n":
                    alreadyIn = True

            if not alreadyIn:
                with open(subredditsFile, 'a') as fh:
                    fh.write(subreddit+'\n')

        xbmc.executebuiltin("Container.Refresh")

def removeSubreddit(subreddit, name, type_):
    log( 'removeSubreddit ' + subreddit)

    with open(subredditsFile, 'r') as fh:
        content = fh.readlines()

    contentNew = ""
    for line in content:
        if line!=subreddit+'\n':
            #log('line='+line+'toremove='+subreddit)
            contentNew+=line
    with open(subredditsFile, 'w') as fh:
        fh.write(contentNew)
        #fh.close()
    xbmc.executebuiltin("Container.Refresh")

def editSubreddit(subreddit, name, type_):
    from .reddit import this_is_a_multireddit, format_multihub
    log( 'editSubreddit ' + subreddit)

    with open(subredditsFile, 'r') as fh:
        content = fh.readlines()

    contentNew = ""

    keyboard = xbmc.Keyboard(subreddit, translation(30003))
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():
        newsubreddit = keyboard.getText()
        #cleanup user input. make sure /user/ and /m/ is lowercase
        if this_is_a_multireddit(newsubreddit):
            newsubreddit = format_multihub(newsubreddit)
        else:
            get_subreddit_entry_info(newsubreddit)

        for line in content:
            if line.strip()==subreddit.strip() :      #if matches the old subreddit,
                #log("adding: %s  %s  %s" %(line, subreddit, newsubreddit)  )
                contentNew+=newsubreddit+'\n'
            else:
                contentNew+=line

        with open(subredditsFile, 'w') as fh:
            fh.write(contentNew)

        xbmc.executebuiltin("Container.Refresh")

def searchReddits(url, name, type_):
    from default import urlMain
    from .main_listing import listSubReddit
    keyboard = xbmc.Keyboard('sort=new&t=week&q=', translation(30005))
    keyboard.doModal()
    if keyboard.isConfirmed() and keyboard.getText():

        #search_string = urllib.quote_plus(keyboard.getText().replace(" ", "+"))
        search_string = keyboard.getText().replace(" ", "+")

        url = urlMain +"/search.json?" +search_string    #+ '+' + nsfw  # + sites_filter skip the sites filter

        listSubReddit(url, name, "")

def setting_gif_repeat_count():
    srepeat_gif_video= addon.getSetting("repeat_gif_video")
    try: repeat_gif_video = int(srepeat_gif_video)
    except ValueError: repeat_gif_video = 0
    #repeat_gif_video          = [0, 1, 3, 10, 100][repeat_gif_video]
    return [0, 1, 3, 10, 100][repeat_gif_video]

def viewImage(image_url, name, preview_url):
    from .guis import cGUI

    log('  viewImage %s, %s, %s' %( image_url, name, preview_url))

    #msg=WINDOW.getProperty(url)
    #WINDOW.clearProperty( url )
    #log( '   msg=' + msg )
    msg=""
    li=[]
    liz=xbmcgui.ListItem(label=msg, label2="")
    liz.setInfo( type='video', infoLabels={"plot": msg, } )
    liz.setArt({"thumb": preview_url, "banner":image_url })

    li.append(liz)
    ui = cGUI('view_450_slideshow.xml' , addon_path, defaultSkin='Default', defaultRes='1080i', listing=li, id=53)
    ui.include_parent_directory_entry=False

    ui.doModal()
    del ui
    return

#     from resources.lib.guis import qGUI
#
#     ui = qGUI('view_image.xml' ,  addon_path, defaultSkin='Default', defaultRes='1080i')
#     #no need to download the image. kodi does it automatically!!!
#     ui.image_path=url
#     ui.doModal()
#     del ui
#     return
#
#     #this is a workaround to not being able to show images on video addon
#     log('viewImage:'+url +'  ' + name )
#
#     ui = ssGUI('tbp_main.xml' , addon_path)
#     items=[]
#
#     items.append({'pic': url ,'description': "", 'title' : name })
#
#     ui.items=items
#     ui.album_name=""
#     ui.doModal()
#     del ui

    #this will also work:
    #download the image, then view it with view_image.xml.
#     url=url.split('?')[0]
#
#     filename,ext=parse_filename_and_ext_from_url(url)
#     #empty_slideshow_folder()  # we're showing only 1 file
#     xbmc.executebuiltin('ActivateWindow(busydialog)')
#
#     os.chdir(SlideshowCacheFolder)
#     download_file= filename+"."+ext
#     if os.path.exists(download_file):
#         log("  file exists")
#     else:
#         log('  downloading %s' %(download_file))
#         downloadurl(url, download_file)
#         log('  downloaded %s' %(download_file))
#     xbmc.executebuiltin('Dialog.Close(busydialog)')
#
#     ui = qGUI('view_image.xml' , addon_path, 'default')
#
#     ui.image_path=SlideshowCacheFolder + fd + download_file  #fd = // or \ depending on os
#     ui.doModal()
#     return

    #download_file=download_file.replace(r"\\",r"\\\\")

    #addonUserDataFolder = xbmc.translatePath("special://profile/addon_data/"+addonID)
    #i cannot get this to work reliably...
    #xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":"1","method":"Player.Open","params":{"item":{"directory":"%s"}}}' %(addonUserDataFolder) )
    #xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":"1","method":"Player.Open","params":{"item":{"directory":"%s"}}}' %(r"d:\\aa\\") )
    #xbmc.executeJSONRPC('{"jsonrpc":"2.0","id":"1","method":"Player.Open","params":{"item":{"file":"%s"}}}' %(download_file) )
    #return

    #whis won't work if addon is a video add-on
    #xbmc.executebuiltin("XBMC.SlideShow(" + SlideshowCacheFolder + ")")

def viewTallImage(image_url, width, height):
    log( 'viewTallImage %s: %sx%s' %(image_url, width, height))
    #image_url=unescape(image_url) #special case for handling reddituploads urls
    #log( 'viewTallImage %s: %sx%s' %(image_url, width, height))

    #useWindow=xbmcgui.WindowDialog()
    useWindow=xbmcgui.WindowXMLDialog('slideshow05.xml', addon_path)
    #useWindow.setCoordinateResolution(1)

    #screen_w=useWindow.getHeight()  #1280
    #screen_h=useWindow.getWidth()  #720
    screen_w=1920
    screen_h=1080

    log('screen %dx%d'%(screen_w,screen_h))
    try:
        w=int(float(width))
        h=int(float(height))
        ar=float(w/h)
        resize_percent=float(screen_w)/w
        if w > screen_w:
            new_h=int(h*resize_percent)
        else:
            if abs( h - screen_h) < ( screen_h / 10 ):  #if the image height is about 10 percent of the screen height, zoom it a bit
                new_h=screen_h*2
            elif h < screen_h:
                new_h=screen_h
            else:
                new_h=h

        log( '   image=%dx%d resize_percent %f  new_h=%d ' %(w,h, resize_percent, new_h))

        loading_img = xbmc.validatePath('/'.join((addon_path, 'resources', 'skins', 'Default', 'media', 'srr_busy.gif' )))

        slide_h=new_h-screen_h
        log( '  slide_h=' + repr(slide_h))
        #sy=0

        #note: y-axis not accurate. 0 does not always indicate top of screen
        img_control = xbmcgui.ControlImage(0, 0, screen_w, new_h, '', aspectRatio=2)  #(values 0 = stretch (default), 1 = scale up (crops), 2 = scale down (black bars)
        #img_control = useWindow.getControl( 101 )
        img_loading = xbmcgui.ControlImage(screen_w-100, 0, 100, 100, loading_img, aspectRatio=2)

        #the cached image is of lower resolution. we force nocache by using setImage() instead of defining the image in ControlImage()
        img_control.setImage(image_url, False)

        useWindow.addControls( [ img_loading, img_control])
        #useWindow.addControl(  img_control )
        img_control.setPosition(0,0)
        scroll_time=(int(h)/int(w))*20000

        img_control.setAnimations( [
                                    ('conditional', "condition=true delay=6000 time=%d effect=slide  start=0,-%d end=0,0 tween=sine easing=inout  pulse=true" %( scroll_time, slide_h) ),
                                    ('conditional', "condition=true delay=0  time=4000 effect=fade   start=0   end=100    "  ) ,
                                    ]  )
        useWindow.doModal()
        useWindow.removeControls( [img_control,img_loading] )
        del useWindow
    except Exception as e:
        log("  EXCEPTION viewTallImage:="+ str( sys.exc_info()[0]) + "  " + str(e) )

def display_album_from(dictlist, album_name):
    from .domains import parse_reddit_link, build_DirectoryItem_url_based_on_media_type, sitesBase
    from .utils import build_script
    directory_items=[]

    album_viewMode=addon.getSetting("album_viewMode")

    if album_viewMode=='450': #using custom gui
        using_custom_gui=True
    else:
        using_custom_gui=False

    #log( repr(dictlist))
    for _, d in enumerate(dictlist):
        ti=d['li_thumbnailImage']
        media_url=d.get('DirectoryItem_url')

        #log('  display_album_from list:'+ media_url + "  " )
        #There is only 1 textbox for Title and description in our custom gui.
        #  I don't know how to achieve this in the xml file so it is done here:
        #  combine title and description without [CR] if label is empty. [B]$INFO[Container(53).ListItem.Label][/B][CR]$INFO[Container(53).ListItem.Plot]
        #  new note: this is how it is done:
        #     $INFO[Container(53).ListItem.Label,[B],[/B][CR]] $INFO[Container(53).ListItem.Plot]  #if the infolabel is empty, nothing is printed for that block
        #combined = '[B]'+ d['li_label2'] + "[/B][CR]" if d['li_label2'] else ""
        combined = d['infoLabels'].get('plot') if d['infoLabels'].get('plot') else ""
        d['infoLabels']['plot'] = combined

        liz=xbmcgui.ListItem(label=d.get('li_label'), label2=d.get('li_label2') )

        #parse the link so that we can determine whether it is image or video.
        ld=parse_reddit_link(media_url)
        DirectoryItem_url, setProperty_IsPlayable, isFolder, _ = build_DirectoryItem_url_based_on_media_type(ld, media_url, '', '', script_to_call="")
        #log('isFolder:' + repr(isFolder)+ ' IsPlayable:'+repr(setProperty_IsPlayable) + ' DirectoryItem_url:' + repr(DirectoryItem_url))
        if using_custom_gui:
            url_for_DirectoryItem=media_url
            liz.setProperty('onClick_action',  DirectoryItem_url )
            liz.setProperty('is_video','true')
            #if setProperty_IsPlayable=='true':
            if ld:
                if ld.link_action == sitesBase.DI_ACTION_PLAYABLE:
                    liz.setProperty('item_type','playable')
                else:
                    #this part is for playing video that needs to be resolved first. (youtube_dl)
                    #I could not get this to work  -->  #Attempt to use invalid handle -1
                    #I think you can't setresolvedUrl a listitem from a custom gui
                    #url_for_DirectoryItem=DirectoryItem_url
                    liz.setProperty('item_type','script')
        else:
            #sys.argv[0]+"?url="+ urllib.quote_plus(d['DirectoryItem_url']) +"&mode=viewImage"

            #with xbmc's standard gui, we need to specify to call the plugin to open the gui that shows image
            #log('***'+'isFolder:' + repr(isFolder)+ ' IsPlayable:'+repr(setProperty_IsPlayable) +'**[diu]:'+ DirectoryItem_url)
            liz.setProperty('IsPlayable',setProperty_IsPlayable)
            url_for_DirectoryItem=DirectoryItem_url

        liz.setInfo( type='video', infoLabels=d['infoLabels'] ) #this tricks the skin to show the plot. where we stored the picture descriptions
        liz.setArt({"thumb": ti,'icon': ti, "poster":media_url, "banner":media_url, "fanart":media_url, "landscape":media_url   })

        directory_items.append( (url_for_DirectoryItem, liz, isFolder) )

    if using_custom_gui:
        from .guis import cGUI
        li=[]
        for di in directory_items:
            li.append( di[1] )

        ui = cGUI('view_450_slideshow.xml' , addon_path, defaultSkin='Default', defaultRes='1080i', listing=li, id=53)
        ui.include_parent_directory_entry=False

        ui.doModal()
        del ui
    else:
        if album_viewMode!='0':
            xbmc.executebuiltin('Container.SetViewMode('+album_viewMode+')')

        xbmcplugin.addDirectoryItems(handle=pluginhandle, items=directory_items )
        xbmcplugin.endOfDirectory(pluginhandle)

def listAlbum(album_url, name, type_):
    from .slideshow import slideshowAlbum
    from .domains import sitesManager
    log("    listAlbum:"+album_url)

    hoster = sitesManager( album_url )
    #log( '  %s %s ' %(hoster.__class__.__name__, album_url ) )

    if hoster:
        dictlist=hoster.ret_album_list(album_url)

        if type_=='return_dictlist':  #used in autoSlideshow
            return dictlist

        if not dictlist:
            xbmc_notify(translation(32200),translation(32055)) #slideshow, no playable items
            return

        if addon.getSetting('use_slideshow_for_album') == 'true':
            slideshowAlbum( dictlist, name )
        else:
            display_album_from( dictlist, name )

def playURLRVideo(url, name, type_):
    dialog_progress_title='URL Resolver'
    dialog_progress_YTDL = xbmcgui.DialogProgressBG()
    dialog_progress_YTDL.create(dialog_progress_title )
    dialog_progress_YTDL.update(10,dialog_progress_title,translation(30024)  )

    parsed_uri = urllib.parse.urlparse( url )
    domain = '{uri.netloc}'.format(uri=parsed_uri)

    try:
        import urlresolver
        #hmf = urlresolver.HostedMediaFile(url)
        dialog_progress_YTDL.update(20,dialog_progress_title,translation(30022)  )
        media_url = urlresolver.resolve(url)
        dialog_progress_YTDL.update(80,dialog_progress_title,translation(30023)  )
        if media_url:
            log( '  URLResolver stream url=' + repr(media_url ))

            listitem = xbmcgui.ListItem(path=media_url)
            xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
        else:
            log( "  Can't URL Resolve:" + repr(url))
            xbmc_notify('URLresolver',translation(30192))
    except Exception as e:
        xbmc_notify('URLresolver', str(e) )
    dialog_progress_YTDL.close()

def loopedPlayback(url, name, type_):
    #for gifs
    #log('*******************loopedplayback ' + url)
    pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    pl.clear()
    pl.add(url, xbmcgui.ListItem(name))
    for _ in range( 0, setting_gif_repeat_count() ):
        pl.add(url, xbmcgui.ListItem(name))

    #pl.add(url, xbmcgui.ListItem(name))
    xbmc.Player().play(pl, windowed=False)

def error_message(message, name, type_):
    if name:
        sub_msg=name
    else:
        sub_msg=translation(30021) #Parsing error
    xbmc_notify(message,sub_msg)

def playVideo(url, name, type_):
    if url :
        #url='http://i.imgur.com/ARdeL4F.mp4'
        #url='plugin://plugin.video.reddit_viewer/?mode=comments_gui'
        listitem = xbmcgui.ListItem(label=name,path=url)
        xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
    else:
        log("playVideo(url) url is blank")

def playYTDLVideo(url, name, type_):
    if pluginhandle==-1:
        xbmc_notify("Error","Attempt to use invalid handle -1") #saves the user from waiting
        return

    dialog_progress_title='Youtube_dl'  #.format(ytdl_get_version_info())
    dialog_progress_YTDL = xbmcgui.DialogProgressBG()
    dialog_progress_YTDL.create(dialog_progress_title )
    dialog_progress_YTDL.update(10,dialog_progress_title,translation(30024)  )

    from .YoutubeDLWrapper import YoutubeDLWrapper, _selectVideoQuality

    o = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(o.query)
    video_index=0
    #note that in domains.py youtube class will send a simplified url to avoid sending
    #   https://www.youtube.com/watch?v=R6_dZhE-4bk&index=22&list=PLGJ6ezwqAB2a4RP8hWEWAGB9eT2bmaBsy  (ytdl will parse around 90+ videos, takes a very long time)
    #   http://youtube.com/v/R6_dZhE-4bk   (will be faster)
    if 'index' in query:
        try:video_index=int(query['index'][0])
        except (TypeError, ValueError): video_index=0
        #log( repr(video_index) )
        dialog_progress_YTDL.update(20,dialog_progress_title,translation(30025)  )
    else:
        #if there is index, link is likely a playlist, parsing will take a looooong time.
        #  we move progress dialog here to differentiate
        dialog_progress_YTDL.update(20,dialog_progress_title,translation(30022)  )

    #use YoutubeDLWrapper by ruuk to avoid  bad file error
    ytdl=YoutubeDLWrapper()
    try:
        ytdl.params['youtube_include_dash_manifest'] = True
        ytdl.params['verbose'] = True
        ydl_info=ytdl.extract_info(url, download=False)
        #in youtube_dl utils.py def unified_timestamp(date_str, day_first=True):
        # there was an error playing https://vimeo.com/14652586
        #   on line 1195:
        # change          except ValueError:
        #     to          except (ValueError,TypeError):
        #   this already fixed by ruuk magic. in YoutubeDLWrapper

        #log( "YoutubeDL extract_info:\n" + pprint.pformat(ydl_info, indent=1) )
        video_infos=_selectVideoQuality(ydl_info, quality=ytdl_quality, disable_dash=(not ytdl_DASH))
        #log( "video_infos:\n" + pprint.pformat(video_infos, indent=1, depth=3) )
        dialog_progress_YTDL.update(80,dialog_progress_title,translation(30023)  )

        if len(video_infos)>1:
            log('    ***ytdl link resolved to %d streams. playing #%d' %(len(video_infos), video_index))
            #xbmc_notify("Multiple video", "{} videos in playlist".format(len(pl)))

        li=ytdl_video_info_to_listitem(video_infos, video_index, name)
        xbmcplugin.setResolvedUrl(pluginhandle, True, li)

    except Exception as e:
        ytdl_ver=dialog_progress_title+' v'+ytdl_get_version_info('local')
        err_msg=str(e)+';'  #ERROR: No video formats found; please report this issue on https://yt-dl.org/bug . Make sure you are using the latest vers....
        short_err=err_msg.split(';')[0]
        log( "playYTDLVideo Exception:" + str( sys.exc_info()[0]) + "  " + str(e) )
        xbmc_notify(ytdl_ver, short_err)

        #try urlresolver
        log('   trying urlresolver...')
        playURLRVideo(url, name, type_)
#    finally:
    dialog_progress_YTDL.update(100,dialog_progress_title ) #not sure if necessary to set to 100 before closing dialogprogressbg
    dialog_progress_YTDL.close()

def ytdl_video_info_to_listitem(video_infos, video_index, title=None):

    if video_index > 0 and video_index<len(video_infos):
        video_info=video_infos[video_index-1]
    else:
#       #we are only playing the first stream because this is a plugin and it expects to play links via setResolvedUrl()
#       #   another option would be to make a playlist and play that but this breaks other functionality(play all...)
        video_info=video_infos[0]

    use_input_stream_adaptive=False
    input_stream_adaptive_manifest_type='mpd'
    url=video_info.get('xbmc_url')  #there is also  video_info.get('url')  url without the |useragent...
    manifest_url=video_info.get('manifest_url') #v.redd.it has this but youtube does not.  they both support DASH video
    #log('***befor:'+pprint.pformat(video_info, indent=1, depth=2))
    if manifest_url:
        use_input_stream_adaptive=True
		#special  thanks to Chaotnix for figuring this part out. 							  
        hls_url=manifest_url.rsplit('/', 1)[0]+'/HLSPlaylist.m3u8'
        log(hls_url)
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError
        req = Request(hls_url)
        try:
            response = urlopen(req)
        except HTTPError as e:
            log('No HLSPlaylist '+'Error code: '+str(e.code))
        except URLError as e:
            log('We failed to reach a server.')
            log('Reason: ', e.reason)
        else:
            url=hls_url
            log('hls_url: '+hls_url)
        if manifest_url.endswith('.mpd'):
            input_stream_adaptive_manifest_type='mpd'
        elif manifest_url.endswith('.m3u8'):
            input_stream_adaptive_manifest_type='hls'
        elif manifest_url.endswith('.ism'):
            input_stream_adaptive_manifest_type='ism'

        #url=video_info.get('manifest_url')

    #log('***befor:'+repr(url))
    url=urllib.parse.quote_plus(url.encode('utf-8'), safe="&$+,/:;=?@#<>[]{}|\^%")
    #log('***after :'+repr(url))
    title=video_info.get('title') or title


    ytdl_format=video_info.get('ytdl_format')
    if ytdl_format:
        description=ytdl_format.get('description')
        #check if there is a time skip code
        try:
            start_time=ytdl_format.get('start_time',0)   #int(float(ytdl_format.get('start_time')))
            duration=ytdl_format.get('duration',0)
            StartPercent=(float(start_time)/duration)*100
        except (ValueError, TypeError, ZeroDivisionError):
            StartPercent=0

        video_thumbnail=video_info.get('thumbnail')
        li=xbmcgui.ListItem(label=title,
                            label2='',
                            path=url)
        li.setInfo( type="Video", infoLabels={ "Title": title, "plot": description } )
        li.setArt( {'icon':video_thumbnail, 'thumb':video_thumbnail} )

        #li.setProperty('StartOffset', str(start_time)) does not work when using setResolvedUrl
        #    we need to use StartPercent.
        li.setProperty('StartPercent', str(StartPercent))

        if use_input_stream_adaptive:
            log('using inputstream.adaptive')
            li.setProperty('inputstreamaddon', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', input_stream_adaptive_manifest_type)
            #li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            #li.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            #li.setProperty('inputstream.adaptive.license_key', 'https://cwip-shaka-proxy.appspot.com/no_auth' + '||R{SSM}|')

        return li

def playYTDLVideoOLD(url, name, type_):
    #url = "http://www.youtube.com/watch?v=_yVv9dx88x0"   #a youtube ID will work as well and of course you could pass the url of another site

    #url='https://www.youtube.com/shared?ci=W8n3GMW5RCY'
    #url='http://burningcamel.com/video/waster-blonde-amateur-gets-fucked'
    #url='http://www.3sat.de/mediathek/?mode=play&obj=51264'
    #url='http://www.4tube.com/videos/209271/hurry-fuck-i-bored'
    #url='http://www.pbs.org/newshour/rundown/cubas-elian-gonzalez-now-college-graduate/'

#these checks done in around May 2016
#does not work:  yourlust  porntube xpornvid.com porndig.com  thumbzilla.com eporner.com yuvutu.com porn.com pornerbros.com fux.com flyflv.com xstigma.com sexu.com 5min.com alphaporno.com
# stickyxtube.com xxxbunker.com bdsmstreak.com  jizzxman.com pornwebms.com pornurl.pw porness.tv openload.online pornworms.com fapgod.com porness.tv hvdporn.com pornmax.xyz xfig.net yobt.com
# eroshare.com kalporn.com hdvideos.porn dailygirlscute.com desianalporn.com indianxxxhd.com onlypron.com sherloxxx.com hdvideos.porn x1xporn.com pornhvd.com lxxlx.com xrhub.com shooshtime.com
# pornvil.com lxxlx.com redclip.xyz younow.com aniboom.com  gotporn.com  virtualtaboo.com 18porn.xyz vidshort.net fapxl.com vidmega.net freudbox.com bigtits.com xfapzap.com orgasm.com
# userporn.com hdpornstar.com moviesand.com chumleaf.com fucktube.com fookgle.com pornative.com dailee.com pornsharia.com fux.com sluttyred.com pk5.net kuntfutube.com youpunish.com
# vidxnet.com jizzbox.com bondagetube.tv spankingtube.tv pornheed.com pornwaiter.com lubetube.com porncor.com maxjizztube.com asianxtv.com analxtv.com yteenporn.com nurglestube.com yporn.tv
# asiantubesex.com zuzandra.com moviesguy.com bustnow.com dirtydirtyangels.com yazum.com watchersweb.com voyeurweb.com zoig.com flingtube.com yourfreeporn.us foxgay.com goshgay.com
# player.moviefap.com(www.moviefap.com works) nosvideo.com

# also does not work (non porn)
# rutube.ru  mail.ru  afreeca.com nicovideo.jp  videos.sapo.pt(many but not all) sciencestage.com vidoosh.tv metacafe.com vzaar.com videojug.com trilulilu.ro tudou.com video.yahoo.com blinkx.com blip.tv
# blogtv.com  brainpop.com crackle.com engagemedia.org expotv.com flickr.com fotki.com hulu.com lafango.com  mefeedia.com motionpictur.com izlesene.com sevenload.com patas.in myvideo.de
# vbox7.com 1tv.ru 1up.com 220.ro 24video.xxx 3sat.de 56.com adultswim.com atresplayer.com techchannel.att.com v.baidu.com azubu.tv www.bbc.co.uk/iplayer bet.com biobiochile.cl biqle.com
# bloomberg.com/news/videos bpb.de bravotv.com byutv.org cbc.ca chirbit.com cloudtime.to(almost) cloudyvideos.com cracked.com crackle.com criterion.com ctv.ca culturebox.francetvinfo.fr
# cultureunplugged.com cwtv.com daum.net dctp.tv democracynow.org douyutv.com dumpert.nl eitb.tv ex.fm fc-zenit.ru  ikudonsubs.com akb48ma.com Flipagram.com ft.dk Formula1.com
# fox.com/watch(few works) video.foxnews.com foxsports.com france2.fr franceculture.fr franceinter.fr francetv.fr/videos francetvinfo.fr giantbomb.com hbo.com History.com hitbox.tv
# howcast.com HowStuffWorks.com hrt.hr iconosquare.com infoq.com  ivi.ru kamcord.com/v video.kankan.com karrierevideos.at KrasView.ru hlamer.ru kuwo.cn la7.it laola1.tv le.com
# media.ccc.de metacritic.com mitele.es  moevideo.net,playreplay.net,videochart.net vidspot.net(might work, can't find recent post) movieclips.com mtv.de mtviggy.com muenchen.tv myspace.com
# myvi.ru myvideo.de myvideo.ge 163.com netzkino.de nfb.ca nicovideo.jp  videohive.net normalboots.com nowness.com ntr.nl nrk.no ntv.ru/video ocw.mit.edu odnoklassniki.ru/video
# onet.tv onionstudios.com/videos openload.co orf.at parliamentlive.tv pbs.org

# news site (can't find sample to test)
# bleacherreport.com crooksandliars.com DailyMail.com channel5.com Funimation.com gamersyde.com gamespot.com gazeta.pl helsinki.fi hotnewhiphop.com lemonde.fr mnet.com motorsport.com MSN.com
# n-tv.de ndr.de NDTV.com NextMedia.com noz.de


# these sites have mixed media. can handle the video in these sites:
# 20min.ch 5min.com archive.org Allocine.fr(added) br.de bt.no  buzzfeed.com condenast.com firstpost.com gameinformer.com gputechconf.com heise.de HotStar.com(some play) lrt.lt natgeo.com
# nbcsports.com  patreon.com
# 9c9media.com(no posts)

#ytdl plays this fine but no video?
#coub.com

#supported but is an audio only site
#acast.com AudioBoom.com audiomack.com bandcamp.com clyp.it democracynow.org? freesound.org hark.com hearthis.at hypem.com libsyn.com mixcloud.com
#Minhateca.com.br(direct mp3)

#
# ytdl also supports these sites:
# myvideo.co.za  ?
#bluegartr.com  (gif)
# behindkink.com   (not sure)
# facebook.com  (need to work capturing only videos)
# features.aol.com  (inconsistent)
# livestream.com (need to work capturing only videos)
# mail.ru inconsistent(need to work capturing only videos)
# miomio.tv(some play but most won't)
# ooyala.com(some play but most won't)
#

#     extractors=[]
#     from youtube_dl.extractor import gen_extractors
#     for ie in gen_extractors():
#         #extractors.append(ie.IE_NAME)
#         try:
#             log("[%s] %s " %(ie.IE_NAME, ie._VALID_URL) )
#         except Exception as e:
#             log( "zz   " + str(e) )

#     extractors.sort()
#     for n in extractors: log("'%s'," %n)
    parsed_uri = urllib.parse.urlparse( url )
    domain = '{uri.netloc}'.format(uri=parsed_uri)

    dialog_progress_YTDL = xbmcgui.DialogProgressBG()
    dialog_progress_YTDL.create('YTDL' )
    dialog_progress_YTDL.update(10,'YTDL','Checking link...' )

    try:
        from domains import ydtl_get_playable_url
        stream_url = ydtl_get_playable_url(url)
        if stream_url:
            dialog_progress_YTDL.update(80,'YTDL', 'Playing' )
            listitem = xbmcgui.ListItem(path=stream_url[0])   #plugins play video like this.
            xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
        else:
            dialog_progress_YTDL.update(40,'YTDL', 'Trying URLResolver' )
            log('YTDL Unable to get playable URL, Trying UrlResolver...' )

            #ytdl seems better than urlresolver for getting the playable url...
            media_url = urlresolver.resolve(url)
            if media_url:
                dialog_progress_YTDL.update(88,'YTDL', 'Playing' )
                #log( '------------------------------------------------urlresolver stream url ' + repr(media_url ))
                listitem = xbmcgui.ListItem(path=media_url)
                xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
            else:
                log('UrlResolver cannot get a playable url' )
                xbmc_notify(translation(30192), domain)

    except Exception as e:
        xbmc_notify("%s(YTDL)"% domain,str(e))
    finally:
        dialog_progress_YTDL.update(100,'YTDL' ) #not sure if necessary to set to 100 before closing dialogprogressbg
        dialog_progress_YTDL.close()

#This handles the links sent via jsonrpc (i.e.: links sent by kore to kodi by calling)
# videoUrl = "plugin://script.reddit.reader/?mode=play&url=" + URLEncoder.encode(videoUri.toString(), "UTF-8");
def parse_url_and_play(url, name, type_):
    from .domains import parse_reddit_link, sitesBase, ydtl_get_playable_url, build_DirectoryItem_url_based_on_media_type
    #from actions import viewImage

    log('parse_url_and_play url='+url)
    #log('pluginhandle='+str(pluginhandle) )
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    ld=parse_reddit_link(url,True, False, False  )

    DirectoryItem_url, setProperty_IsPlayable, isFolder, title_prefix = build_DirectoryItem_url_based_on_media_type(ld, url)

    if setProperty_IsPlayable=='true':
        log( '---------IsPlayable---------->'+ DirectoryItem_url)
        playVideo(DirectoryItem_url,'','')
    else:
        if isFolder: #showing album
            log( '---------using ActivateWindow------>'+ DirectoryItem_url)
            xbmc.executebuiltin('ActivateWindow(Videos,'+ DirectoryItem_url+')')
        else:  #viewing image
            log( '---------using setResolvedUrl------>'+ DirectoryItem_url)
            #viewImage(DirectoryItem_url,'','' )

            #error message after picture is displayed, kore remote will be unresponsive
            #playVideo(DirectoryItem_url,'','')

            #endless loop. picture windowxml opens after closing, opens again after closing....
            #xbmc.executebuiltin('ActivateWindow(Videos,'+ DirectoryItem_url+')')

            #log( 'Container.Update(%s?path=%s?prl=zaza&mode=viewImage&url=%s)' % ( sys.argv[0], sys.argv[0], urllib.quote_plus(url) )  )
            #xbmc.executebuiltin('Container.Update(%s?path=%s?prl=zaza&mode=viewImage&url=%s)' % ( sys.argv[0], sys.argv[0], urllib.quote_plus(url) ) )

            listitem = xbmcgui.ListItem(path='')
            listitem.setProperty('IsPlayable', 'false')
            xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)

            #DirectoryItem_url=DirectoryItem_url.replace('plugin://', 'script://')
            #xbmc.executebuiltin('RunScript(script.reddit.reader)' )
            #xbmc.executebuiltin('RunScript(script.reddit.reader,mode=viewImage&url=%s)' %urllib.quote_plus(url) )
            #xbmc.executebuiltin('RunPlugin(%s?path=%s?prl=zaza&mode=viewImage&url=%s)' % ( sys.argv[0], sys.argv[0], urllib.quote_plus(url) ) )
            xbmc.executebuiltin('RunPlugin(%s)' % ( DirectoryItem_url ) )

        #listitem = xbmcgui.ListItem(path=DirectoryItem_url)
        #listitem.setProperty('IsPlayable', setProperty_IsPlayable)
        #xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)

        #xbmc.executebuiltin('RunPlugin(%s)' %DirectoryItem_url)
        #xbmc.executebuiltin('ActivateWindow(Videos,'+ DirectoryItem_url+')')

#    if ld:
#        if setProperty_IsPlayable=='true':
#            playVideo(DirectoryItem_url,'','')
#        else:
#            listitem = xbmcgui.ListItem(path=DirectoryItem_url)
#            listitem.setProperty('IsPlayable', setProperty_IsPlayable)
#            xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
#
#
#
#    else:
#        playable_url = ydtl_get_playable_url( url )  #<-- will return a playable_url or a list of playable urls
#        #playable_url= '(worked)' + title.ljust(15)[:15] + '... '+ w_url
#        #work
#        if playable_url:
#            if pluginhandle>0:
#                for u in playable_url:
#                    listitem = xbmcgui.ListItem(path=u, label=name)   #plugins play video like this.
#                    xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
#            else:
#                #log('pluginhandleXXXX name=')
#                #this portion won't work with autoplay (playlist)
#                playlist.clear()
#                if len(playable_url)>1: log('    link has multiple videos'  )
#
#                for u in playable_url:
#                    #self.queue.put( [title, u] )
#                    queueVideo(u, name, type_)
#                xbmc.Player().play(playlist)
#        else:
#            xbmc.executebuiltin("XBMC.Notification(%s, %s)"  %( translation(30192), 'Youtube_dl')  )

def queueVideo(url, name, type_):
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    listitem = xbmcgui.ListItem(name)
    playlist.add(url, listitem)






YTDL_VERSION_URL = 'https://yt-dl.org/latest/version'
YTDL_LATEST_URL_TEMPLATE = 'https://yt-dl.org/latest/youtube-dl-{}.tar.gz'

def ytdl_get_version_info(which_one='latest'):
    if which_one=='latest':
        try:
            newVersion = urllib.request.urlopen(YTDL_VERSION_URL).read().strip()
            return newVersion.decode('utf-8')
        except Exception as e:
            log('error getting latest ytdl version:'+str(e))
            return "0.0"
    else:
        try:
            #*** it seems like the script.module.youtube_dl version gets imported if the one from resources.lib is missing
            from .youtube_dl.version import __version__
            return __version__
        except Exception as e:
            log('error getting ytdl local version:'+str(e))
            return "0.0"

#TrellixVulnTeam [PATCH] Adding tarfile member sanitization to extractall()
def is_within_directory(directory, target):
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)

    prefix = os.path.commonprefix([abs_directory, abs_target])
    return prefix == abs_directory

def safe_extract(tar, path=".", members=None, *, numeric_owner=False):

    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if not is_within_directory(path, member_path):
            raise Exception("Attempted Path Traversal in Tar File")

    tar.extractall(path, members, numeric_owner=numeric_owner) 


def update_youtube_dl_core(url,name,action_type):
#credit to ruuk for most of the download code
    import tarfile

    if action_type=='download':
        newVersion=note_ytdl_versions()
        LATEST_URL=YTDL_LATEST_URL_TEMPLATE.format(newVersion)

        profile = xbmcvfs.translatePath(profile_path)  #xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
        archivePath = os.path.join(profile,'youtube_dl.tar.gz')
        extractedPath = os.path.join(profile,'youtube-dl')
        extracted_core_path=os.path.join(extractedPath,'youtube_dl')
        #ytdl_core_path  xbmcvfs.translatePath(  addon_path+"/resources/lib/youtube_dl/" )

        try:
            if os.path.exists(extractedPath):
                shutil.rmtree(extractedPath, ignore_errors=True)
                update_dl_status('temp files removed')

            update_dl_status('Downloading {0} ...'.format(newVersion))
            log('  From: {0}'.format(LATEST_URL))
            log('    to: {0}'.format(archivePath))
            urllib.request.urlretrieve(LATEST_URL,filename=archivePath)

            if os.path.exists(archivePath):
                update_dl_status('Extracting ...')

                with tarfile.open(archivePath,mode='r:gz') as tf:
                    members = [m for m in tf.getmembers() if m.name.startswith('youtube-dl/youtube_dl')] #get just the files from the youtube_dl source directory
                    #tf.extractall(path=profile,members=members)
                    safe_extract(tf, path=profile, members=members)
            else:
                update_dl_status('Download failed')
        except Exception as e:
            update_dl_status('Error:' + str(e))
            return

        update_dl_status('Updating...')

        if os.path.exists(extracted_core_path):
            log( '  extracted dir exists:'+extracted_core_path)

            if os.path.exists(ytdl_core_path):
                log( '  destination dir exists:'+ytdl_core_path)
                shutil.rmtree(ytdl_core_path, ignore_errors=True)
                update_dl_status('    Old ytdl core removed')
                xbmc.sleep(1000)
            try:
                shutil.move(extracted_core_path, ytdl_core_path)
                update_dl_status('    New core copied')
                xbmc.sleep(1000)
                update_dl_status('Update complete')
                xbmc.Monitor().waitForAbort(2.0)
                #ourVersion=ytdl_get_version_info('local')
                setSetting('ytdl_btn_check_version', "")
                setSetting('ytdl_btn_download', "")
            except Exception as e:
                update_dl_status('Failed...')
                log( 'move failed:'+str(e))

    elif action_type=='checkversion':
        note_ytdl_versions()

def note_ytdl_versions():
    #display ytdl versions and return latest version
    setSetting('ytdl_btn_check_version', "checking...")
    ourVersion=ytdl_get_version_info('local')
    setSetting('ytdl_btn_check_version', "{0}".format(ourVersion))

    setSetting('ytdl_btn_download', "checking...")
    newVersion=ytdl_get_version_info('latest')
    setSetting('ytdl_btn_download',      "latest {0}".format(newVersion))

    return newVersion


def update_dl_status(message):
    log(message)
    setSetting('ytdl_btn_download', message)

def setSetting(setting_id, value):
    addon.setSetting(setting_id, value)

def delete_setting_file(url,name,action_type):
    #log( "delete setting file:" + action_type)
    if action_type=='requests_cache':
        file_to_delete=CACHE_FILE+'.sqlite'
    elif action_type=='icons_cache':
        file_to_delete=subredditsPickle
    elif action_type=='subreddits_setting':
        file_to_delete=subredditsFile

    try:
        os.remove(file_to_delete)
        xbmc_notify("Deleting", '..'+file_to_delete[-30:])
    except OSError as e:
        xbmc_notify("Error:", str(e))

def listRelatedVideo(url,name,type_):
    #type_: 'channel' -other videos in the channel
    #       'related' -related videos
    #only youtube is supported for now
    from .domains import ClassYoutube
    from .domains import parse_reddit_link, build_DirectoryItem_url_based_on_media_type

    match=re.compile( ClassYoutube.regex, re.I).findall( url )
    if match:
        #log('***** isYouTubeable' + repr(link_url))
        yt=ClassYoutube(url)
        links_dictList=yt.ret_album_list(type_)  #returns a list of dict same as one used for albums
        if links_dictList:
            #log(pprint.pformat(links_dictList))

            for _, d in enumerate(links_dictList):
                label=d.get('li_label')
                label2=d.get('li_label2')
                #li_iconImage=d.get('li_iconImage')
                ti=d.get('li_thumbnailImage')
                media_url=d.get('DirectoryItem_url')
                #media_type=d.get('type')
                #media_thumb=d.get('thumb')
                #isPlayable=d.get('isPlayable')
                #link_action=d.get('link_action')
                #channel_id=d.get('channel_id')
                #video_id=d.get('video_id')

                liz=xbmcgui.ListItem(label,label2)
                liz.setInfo( type='video', infoLabels=d['infoLabels'] ) #this tricks the skin to show the plot. where we stored the descriptions
                liz.setArt({"thumb": ti,'icon': ti, "poster":ti, "banner":ti, "fanart":ti, "landscape":ti   })

                #a little overkill considering we're only matching for youtube
                ld=parse_reddit_link(media_url)
                DirectoryItem_url, setProperty_IsPlayable, isFolder, _ = build_DirectoryItem_url_based_on_media_type(ld, media_url, '', '', script_to_call="")
                #directory_items.append( (url_for_DirectoryItem, liz, False,) )
                liz.setProperty('IsPlayable', setProperty_IsPlayable)
                xbmcplugin.addDirectoryItem(pluginhandle, DirectoryItem_url, liz, isFolder)

            xbmcplugin.endOfDirectory(handle=pluginhandle,
                              succeeded=True,
                              updateListing=False,   #setting this to True causes the ".." entry to quit the plugin
                              cacheToDisc=True)
        else:
            xbmc_notify('Nothing to list', url)
    else:
        xbmc_notify('cannot identify youtube url', url)

if __name__ == '__main__':
    pass

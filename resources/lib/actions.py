# -*- coding: utf-8 -*-
import xbmc
import xbmcgui
import xbmcplugin
#import xbmcvfs
import sys

from default import pluginhandle, log, translation, xbmc_busy, subredditsFile, addon, addon_path, profile_path, ytdl_core_path, subredditsPickle
import threading

def addSubreddit(subreddit, name, type):
    from utils import this_is_a_multireddit, format_multihub, colored_subreddit
    alreadyIn = False
    fh = open(subredditsFile, 'r')
    content = fh.readlines()
    fh.close()
    if subreddit:
        for line in content:
            if line.lower()==subreddit.lower():
                alreadyIn = True
        if not alreadyIn:
            with open(subredditsFile, 'a') as fh:
                fh.write(subreddit+'\n')

            get_subreddit_entry_info(subreddit)
        xbmc.executebuiltin('XBMC.Notification("%s", "%s" )' %( colored_subreddit(subreddit), translation(30019)  ) )
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
                fh = open(subredditsFile, 'a')
                fh.write(subreddit+'\n')
                fh.close()
        xbmc.executebuiltin("Container.Refresh")

def get_subreddit_entry_info(subreddit):
    #from resources.lib.utils import get_subreddit_info, parse_subreddit_entry, create_default_subreddits, load_dict
    if subreddit.lower() in ['all','random','randnsfw']:
        return
    s=[]
    if '/' in subreddit:  #we want to get diy from diy/top or diy/new
        subreddit=subreddit.split('/')[0]

    if '+' in subreddit:
        s.extend(subreddit.split('+'))
    else:
        s.append(subreddit)

    t = threading.Thread(target=get_subreddit_entry_info_thread, args=(s,) )
    #threads.append(t)
    #log('****starting... '+repr(t))
    t.start()

def get_subreddit_entry_info_thread(sub_list):
    import os
    from utils import get_subreddit_info, load_dict, save_dict

    subreddits_dlist=[]
    #log('**** thread running')
    if os.path.exists(subredditsPickle):
        #log('****file exists ' + repr( subredditsPickle ))
        subreddits_dlist=load_dict(subredditsPickle)
        #for e in subreddits_dlist: log(e.get('entry_name'))
        #log( pprint.pformat(subreddits_dlist, indent=1) )

    #log('****------before for -------- ' + repr(sub_list ))
    for subreddit in sub_list:
        #remove old instance of subreddit
        subreddits_dlist=[x for x in subreddits_dlist if x.get('entry_name') != subreddit.lower() ]

        #for e in subreddits_dlist: log(e.get('entry_name'))

        #log('****getting sub_info ' )

        sub_info=get_subreddit_info(subreddit)

        log('****sub_info ' + repr( sub_info ))

        if sub_info:
            #log('****if sub_info ')
            subreddits_dlist.append(sub_info)
            save_dict(subreddits_dlist, subredditsPickle)
            #log('****saved ')
def removeSubreddit(subreddit, name, type):
    #note: calling code in addDirR()
    fh = open(subredditsFile, 'r')
    content = fh.readlines()
    fh.close()
    contentNew = ""
    for line in content:
        if line!=subreddit+'\n':
            #log('line='+line+'toremove='+subreddit)
            contentNew+=line
    fh = open(subredditsFile, 'w')
    fh.write(contentNew)
    fh.close()
    xbmc.executebuiltin("Container.Refresh")

def editSubreddit(subreddit, name, type):
    from utils import this_is_a_multireddit, format_multihub
    #note: calling code in addDirR()
    fh = open(subredditsFile, 'r')
    content = fh.readlines()
    fh.close()
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

        fh = open(subredditsFile, 'w')
        fh.write(contentNew)
        fh.close()

        xbmc.executebuiltin("Container.Refresh")

def setting_gif_repeat_count():
    srepeat_gif_video= addon.getSetting("repeat_gif_video")
    try: repeat_gif_video = int(srepeat_gif_video)
    except: repeat_gif_video = 0
    #repeat_gif_video          = [0, 1, 3, 10, 100][repeat_gif_video]
    return [0, 1, 3, 10, 100][repeat_gif_video]

def viewImage(image_url, name, preview_url):
    from guis import cGUI

    log('  viewImage %s, %s, %s' %( image_url, name, preview_url))

    #msg=WINDOW.getProperty(url)
    #WINDOW.clearProperty( url )
    #log( '   msg=' + msg )
    msg=""
    li=[]
    liz=xbmcgui.ListItem(label=msg, label2="", iconImage="", thumbnailImage=image_url)
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
    from domains import parse_reddit_link, build_DirectoryItem_url_based_on_media_type
    directory_items=[]

    album_viewMode=addon.getSetting("album_viewMode")

    if album_viewMode=='450': #using custom gui
        using_custom_gui=True
    else:
        using_custom_gui=False

    #log( repr(dictlist))
    for idx, d in enumerate(dictlist):
        ti=d['li_thumbnailImage']
        media_url=d.get('DirectoryItem_url')

        #log('  display_album_from list:'+ media_url + "  " )
        #There is only 1 textbox for Title and description in our custom gui.
        #  I don't know how to achieve this in the xml file so it is done here:
        #  combine title and description without [CR] if label is empty. [B]$INFO[Container(53).ListItem.Label][/B][CR]$INFO[Container(53).ListItem.Plot]
        #  new note: this is how it is done:
        #     $INFO[Container(53).ListItem.Label,[B],[/B][CR]] $INFO[Container(53).ListItem.Plot]  #if the infolabel is empty, nothing is printed for that block
        combined = '[B]'+ d['li_label2'] + "[/B][CR]" if d['li_label2'] else ""
        combined += d['infoLabels'].get('plot') if d['infoLabels'].get('plot') else ""
        d['infoLabels']['plot'] = combined
        #d['infoLabels']['genre'] = "0,-2000"
        #d['infoLabels']['year'] = 1998
        #log( d['infoLabels'].get('plot') )

        liz=xbmcgui.ListItem(label=d['infoLabels']['plot'],
                             label2=d['li_label2'],
                             iconImage='',
                             thumbnailImage='')

        #parse the link so that we can determine whether it is image or video.
        ld=parse_reddit_link(media_url)
        DirectoryItem_url, setProperty_IsPlayable, isFolder, title_prefix = build_DirectoryItem_url_based_on_media_type(ld, media_url, '', '', script_to_call="")

        if using_custom_gui:
            url_for_DirectoryItem=media_url
            if setProperty_IsPlayable=='true':
                liz.setProperty('item_type','playable')
                #liz.setProperty('onClick_action', build_script('play', media_url,'','') )
                liz.setProperty('onClick_action',  media_url )
        else:
            #sys.argv[0]+"?url="+ urllib.quote_plus(d['DirectoryItem_url']) +"&mode=viewImage"

            #with xbmc's standard gui, we need to specify to call the plugin to open the gui that shows image
            #log('*****[diu]:'+ DirectoryItem_url)
            url_for_DirectoryItem=DirectoryItem_url

        liz.setInfo( type='video', infoLabels=d['infoLabels'] ) #this tricks the skin to show the plot. where we stored the picture descriptions
        liz.setArt({"thumb": ti,'icon': ti, "poster":media_url, "banner":media_url, "fanart":media_url, "landscape":media_url   })

        directory_items.append( (url_for_DirectoryItem, liz, False,) )
    #msg=WINDOW.getProperty(url)
    #WINDOW.clearProperty( url )
    #log( '   msg=' + msg )
    #<label>$INFO[Window(10000).Property(foox)]</label>
    #WINDOW.setProperty('view_450_slideshow_title',WINDOW.getProperty(url))

    if using_custom_gui:
        from guis import cGUI
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

def listAlbum(album_url, name, type):
    from slideshow import slideshowAlbum
    from domains import sitesManager

    hoster = sitesManager( album_url )
    #log( '  %s %s ' %(hoster.__class__.__name__, album_url ) )

    if hoster:
        dictlist=hoster.ret_album_list(album_url)

        if type=='return_dictlist':  #used in autoSlideshow
            return dictlist

        if not dictlist:
            xbmc.executebuiltin('XBMC.Notification("%s", "%s" )'  %( translation(32200), translation(32055) )  )  #slideshow, no playable items
            return

        if addon.getSetting('use_slideshow_for_album') == 'true':
            slideshowAlbum( dictlist, name )
        else:
            display_album_from( dictlist, name )

def playURLRVideo(url, name, type):
    import urlresolver
    from urlparse import urlparse
    parsed_uri = urlparse( url )
    domain = '{uri.netloc}'.format(uri=parsed_uri)
    #log( '-----------------'+ domain +'---------------------- play url resolver  ' + repr(url ))

    #ytdl seems better than urlresolver for getting the playable url...

    #hmf = urlresolver.HostedMediaFile(url)
    #log( ' --------------valid_url-----' + repr( hmf.valid_url() )  )

    try:
        media_url = urlresolver.resolve(url)
        if media_url:
            log( '  URLResolver stream url=' + repr(media_url ))

            listitem = xbmcgui.ListItem(path=media_url)
            xbmcplugin.setResolvedUrl(pluginhandle, True, listitem)
        else:
            xbmc.executebuiltin('XBMC.Notification("%s", "%s (URLresolver" )'  %( translation(30192), domain )  )
    except Exception as e:
        xbmc.executebuiltin('XBMC.Notification("%s","%s (URLresolver)")' %(  str(e), domain )  )

def loopedPlayback(url, name, type):
    #for gifs
    log('loopedplayback ' + url)
    pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    pl.clear()
    pl.add(url, xbmcgui.ListItem(name))
    for x in range( 0, setting_gif_repeat_count() ):
        pl.add(url, xbmcgui.ListItem(name))

    #pl.add(url, xbmcgui.ListItem(name))
    xbmc.Player().play(pl, windowed=False)

def error_message(message, name, type):
    if name:
        sub_msg=name
    else:
        sub_msg=translation(30021) #Parsing error
    xbmc.executebuiltin('XBMC.Notification("%s", "%s" )' %( message, sub_msg  ) )




if __name__ == '__main__':
    pass

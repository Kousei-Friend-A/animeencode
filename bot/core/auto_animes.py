from asyncio import gather, create_task, sleep as asleep, Event
from os import path as ospath
from bot import bot, bot_loop, Var, ani_cache, ffQueue, ffLock, ff_queued
from .tordownload import TorDownloader
from .database import db
from .func_utils import getfeed, encode, editMessage, sendMessage, convertBytes
from .text_utils import TextEditor
from .ffencoder import FFEncoder
from .tguploader import TgUploader
from .reporter import rep
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

btn_formatter = {
    '1080':'1080p', 
    '720':'720p',
    '480':'480p',
    '360':'360p'
}

async def fetch_animes():
    await rep.report("Fetch Animes Started !!", "info")
    while True:
        await asleep(60)
        if ani_cache['fetch_animes']:
            for link in Var.RSS_ITEMS:
                if (info := await getfeed(link, 0)):
                    bot_loop.create_task(get_animes(info.title, info.link))

async def get_animes(name, torrent, force=False):
    try:
        aniInfo = TextEditor(name)
        await aniInfo.load_anilist()
        ani_id, ep_no = aniInfo.adata.get('id'), aniInfo.pdata.get("episode_number")
        if ani_id not in ani_cache['ongoing']:
            ani_cache['ongoing'].add(ani_id)
        elif not force:
            return
        if not force and ani_id in ani_cache['completed']:
            return
        if force or (not (ani_data := await db.getAnime(ani_id)) \
            or (ani_data and not (qual_data := ani_data.get(ep_no))) \
            or (ani_data and qual_data and not all(qual for qual in qual_data.values()))):
            
            if "[Batch]" in name:
                await rep.report(f"Torrent Skipped!\n\n{name}", "warning")
                return
            
            await rep.report(f"New Anime Torrent Found!\n\n{name}", "info")
            post_msg = await bot.send_photo(
                Var.MAIN_CHANNEL,
                photo=await aniInfo.get_poster(),
                caption=await aniInfo.get_caption()
            )
            
            await asleep(1.5)
            stat_msg = await sendMessage(Var.MAIN_CHANNEL, f"➤ <b>Anime Name :</b> <b><i>{name}</i></b>\n\n<i>● Downloading...</i>")
            dl = await TorDownloader("./downloads").download(torrent, name)
            if not dl or not ospath.exists(dl):
                await rep.report(f"File Download Incomplete, Try Again", "error")
                await stat_msg.delete()
                return

            post_id = post_msg.id
            ffEvent = Event()
            ff_queued[post_id] = ffEvent
            if ffLock.locked():
                await editMessage(stat_msg, f"➤ <b>Anime Name :</b> <b><i>{name}</i></b>\n\n<i>● Queued to Encode...</i>")
                await rep.report("Added Task to Queue...", "info")
            await ffQueue.put(post_id)
            await ffEvent.wait()
            
            await ffLock.acquire()
            btns = []
            for qual in Var.QUALS:
                filename = await aniInfo.get_upname(qual)
                await editMessage(stat_msg, f"➤ <b>Anime Name :</b> <b><i>{name}</i></b>\n\n<i>● Encoding... [{btn_formatter[qual]}]</i>")
                try:
                    encoder = FFEncoder(stat_msg, dl, filename, qual)
                    out_path = await encoder.start_encode()
                    if not out_path:
                        raise Exception("Encoding did not return a valid output path.")
                except Exception as e:
                    await rep.report(f"Encoding Error for {filename} at quality {qual}: {e}", "error")
                    await stat_msg.delete()
                    ffLock.release()
                    return

                url = await TgUploader().upload(out_path, filename, stat_msg)
                btns.append([InlineKeyboardButton(f'{btn_formatter[qual]}', url=url)])
                await aniInfo.update_db(qual, url)
                
            await bot.edit_message_reply_markup(
                Var.MAIN_CHANNEL,
                post_id,
                reply_markup=InlineKeyboardMarkup(btns)
            )
            await rep.report("All Done!!", "info")
            await stat_msg.delete()
            await asleep(3)
            await TgUploader().clean()
            ffLock.release()
    except Exception as e:
        await rep.report(f"Error in get_animes: {e}", "error")

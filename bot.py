import os, time, math, shutil, pyromod.listen, asyncio, random, shlex, re, requests
from urllib.parse import unquote
from urllib.error import HTTPError
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from pyrogram.errors import BadRequest
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from typing import Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configs
API_HASH = os.environ.get('API_HASH') # Api hash
APP_ID = int(os.environ.get('APP_ID')) # Api id/App id
BOT_TOKEN = os.environ.get('BOT_TOKEN') # Bot token
OWNER_ID = os.environ.get('OWNER_ID') # Your telegram id
AS_ZIP = bool(os.environ.get('AS_ZIP', False)) # Upload method. If True: will Zip all your files and send as zipfile | If False: will send file one by one
BUTTONS = bool(os.environ.get('BUTTONS', False)) # Upload mode. If True: will send buttons (Zip or One by One) instead of AZ_ZIP | If False: will do as you've fill on AZ_ZIP

# Buttons
START_BUTTONS=[
    [
        InlineKeyboardButton("Source", url="https://github.com"),
        InlineKeyboardButton("Channel", url="https://t.me/Students_Helpers"),
    ],
    [InlineKeyboardButton("Master", url="https://t.me/MasterContact_bot")],
]

CB_BUTTONS=[
    [
        InlineKeyboardButton("Zip", callback_data="zip"),
        InlineKeyboardButton("One by one", callback_data="1by1"),
    ]
]

# Helpers

# https://github.com/SpEcHiDe/AnyDLBot
async def progress_for_pyrogram(
    current,
    total,
    ud_type,
    message,
    start
):
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        # if round(current / total * 100, 0) % 5 == 0:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

        progress = "[{0}{1}] \nP: {2}%\n".format(
            ''.join(["█" for i in range(math.floor(percentage / 5))]),
            ''.join(["░" for i in range(20 - math.floor(percentage / 5))]),
            round(percentage, 2))

        tmp = progress + "{0} of {1}\nSpeed: {2}/s\nETA: {3}\n".format(
            humanbytes(current),
            humanbytes(total),
            humanbytes(speed),
            # elapsed_time if elapsed_time != '' else "0 s",
            estimated_total_time if estimated_total_time != '' else "0 s"
        )
        try:
            await message.edit(
                text="{}\n {}".format(
                    ud_type,
                    tmp
                )
            )
        except:
            pass


def humanbytes(size):
    # https://stackoverflow.com/a/49361727/4723940
    # 2**10 = 1024
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2]


async def run_cmd(cmd) -> Tuple[str, str, int, int]:
    if type(cmd) == str:
        cmd = shlex.split(cmd)
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return (
        stdout.decode("utf-8", "replace").strip(),
        stderr.decode("utf-8", "replace").strip(),
        process.returncode,
        process.pid,
    )


# Send media; required ffmpeg
async def send_media(file_name: str, update: Message) -> bool:
    if os.path.isfile(file_name):
        files = file_name
        pablo = update
        if not '/' in files:
            caption = files
        else:
            caption = files.split('/')[-1]
        progress_args = ('Uploading...', pablo, time.time())
        if files.lower().endswith(('.mkv', '.mp4')):
            metadata = extractMetadata(createParser(files))
            duration = 0
            if metadata is not None:
                if metadata.has("duration"):
                    duration = metadata.get('duration').seconds
            rndmtime = str(random.randint(0, duration))
            await run_cmd(f'ffmpeg -ss {rndmtime} -i "{files}" -vframes 1 thumbnail.jpg')
            await update.reply_video(files, caption=caption, duration=duration, thumb='thumbnail.jpg', progress=progress_for_pyrogram, progress_args=progress_args)
            os.remove('thumbnail.jpg')
        elif files.lower().endswith(('.jpg', '.jpeg', '.png')):
            try:
                await update.reply_photo(files, caption=caption, progress=progress_for_pyrogram, progress_args=progress_args)
            except Exception as e:
                print(e)
                await update.reply_document(files, caption=caption, progress=progress_for_pyrogram, progress_args=progress_args)
        elif files.lower().endswith(('.mp3')):
            try:
                await update.reply_audio(files, caption=caption, progress=progress_for_pyrogram, progress_args=progress_args)
            except Exception as e:
                print(e)
                await update.reply_document(files, caption=caption, progress=progress_for_pyrogram, progress_args=progress_args)
        else:
            await update.reply_document(files, caption=caption, progress=progress_for_pyrogram, progress_args=progress_args)
        return True
    else:
        return False


async def download_file(url, dl_path):
    command = [
        'yt-dlp',
        '-f', 'best',
        '-i',
        '-o',
        dl_path+'/%(title)s.%(ext)s',
        url
    ]
    await run_cmd(command)


# https://github.com/MysteryBots/UnzipBot/blob/master/UnzipBot/functions.py
async def absolute_paths(directory):
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            yield os.path.abspath(os.path.join(dirpath, f))


# Running bot
xbot = Client('BulkLoader', api_id=APP_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


if OWNER_ID:
    OWNER_FILTER = filters.chat(int(OWNER_ID)) & filters.incoming
else:
    OWNER_FILTER = filters.incoming

# Start message
@xbot.on_message(filters.command('start') & OWNER_FILTER & filters.private)
async def start(bot, update):
    await update.reply_text(f"I'm BulkLoader\nYou can upload list of urls\n\n/help for more details!", True, reply_markup=InlineKeyboardMarkup(START_BUTTONS))


# Helper msg
@xbot.on_message(filters.command('help') & OWNER_FILTER & filters.private)
async def help(bot, update):
    await update.reply_text(f"How to use BulkLoader?!\n\n2 Methods:\n- send command /link and then send urls, separated by new line.\n- send txt file (links), separated by new line.", True, reply_markup=InlineKeyboardMarkup(START_BUTTONS))

def extract_links(input_url, output_file, excluded_extensions):
    response = requests.get(input_url)
    text = response.text

    links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
    
    filtered_links = [link for link in links if not any(extension in link for extension in excluded_extensions)]
    
    with open(output_file, 'w') as file:
        file.write('\n'.join(filtered_links))

    print(f"✅ Links Extracted")

# Example usage
input_url = input("📤 Enter Direct Link of TXT File: ")
output_file = 'ace.txt'
excluded_extensions = ['.html', '.srt', '.txt', '.png', '.jpg', '.jpeg', '.url', '.nfo', '.webp']  # Add the extensions you want to exclude in this list

extract_links(input_url, output_file, excluded_extensions)

# Upload the file to file.io
file_io_url = 'https://file.io'
files = {'file': open(output_file, 'rb')}
response = requests.post(file_io_url, files=files)

# Get the URL for accessing the file
download_url = response.json()['link']

print("📝 Conversion Completed 🎉")
print(f"📩 Download: {download_url}")



xbot.run()

from urllib import parse
from gtts import gTTS
import requests, os
from tkinter import *
from tkinter.messagebox import showerror
from tkinter.ttk import Combobox
from googletrans import Translator

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

import pygame._sdl2.audio as sdl2_audio
import pygame
from pygame import mixer

import json
from os import path
import numpy as np
import ctypes
import pydub
from torch import no_grad, LongTensor


ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('com.app.mictts')

from AronaTTS import *

TTS_LIST = [
    'google',
    'kakao',
    'arona'
]
TTS_SELECTED = 0

trans = Translator()

max_length = 1000
limitation = False
name = '아로나(アロナ) TTS'
lang = '日本語 (Japanese)'

def get_text(text, hps, is_phoneme):
    text_norm = text_to_sequence(text, hps.symbols, [] if is_phoneme else hps.data.text_cleaners)
    if hps.data.add_blank:
        text_norm = commons.intersperse(text_norm, 0)
    text_norm = LongTensor(text_norm)
    return text_norm


def create_tts_fn(model, hps, speaker_ids):
    def tts_fn(text, speaker, speed, is_phoneme):
        if limitation:
            text_len = len(text)
            max_len = max_length
            if text_len > max_len:
                return 'Error: Text is too long', None

        speaker_id = speaker_ids[speaker]
        stn_tst = get_text(text, hps, is_phoneme)
        with no_grad():
            x_tst = stn_tst.unsqueeze(0)
            x_tst_lengths = LongTensor([stn_tst.size(0)])
            sid = LongTensor([speaker_id])
            audio = model.infer(x_tst, x_tst_lengths, sid=sid, noise_scale=.667, noise_scale_w=0.8,
                                length_scale=1.0 / speed)[0][0, 0].data.cpu().float().numpy()
        del stn_tst, x_tst, x_tst_lengths, sid
        
        # convert to 16-bit wav
        audio = audio.astype(np.float32)
        audio = audio / np.max(np.abs(audio))
        audio = audio * 32767 * 0.9
        audio = audio.astype(np.int16)
        # conver wav to mp3
        audio = pydub.AudioSegment(audio.tobytes(), frame_rate=hps.data.sampling_rate, sample_width=2, channels=1)
        audio = audio.set_frame_rate(24000)
        audio = audio.set_channels(1)
        audio = audio.set_sample_width(2)
        # can i change bitrate to 32kbps?
        audio.export('tts.mp3', format='mp3', bitrate='32k')
        
        #return 'Success', (hps.data.sampling_rate, audio)

    return tts_fn


def create_to_phoneme_fn(hps):
    def to_phoneme_fn(text):
        return _clean_text(text, hps.data.text_cleaners) if text != '' else ''

    return to_phoneme_fn

folder = path.join(path.dirname(path.realpath(__file__)), 'AronaTTS', 'saved_model')
config_path = path.join(folder, 'config.json')
model_path = path.join(folder, 'model.pth')
cover_path = path.join(folder, 'cover.png')
hps = utils.get_hparams_from_file(config_path)
model = SynthesizerTrn(
    len(hps.symbols),
    hps.data.filter_length // 2 + 1,
    hps.train.segment_size // hps.data.hop_length,
    n_speakers=hps.data.n_speakers,
    **hps.model)
utils.load_checkpoint(model_path, model, None)
model.eval()
speaker_ids = [0]
speakers = [name]
arona_tts = create_tts_fn(model, hps, speaker_ids)


pygame.init()

def get_devices(capture_devices = False):
    mixer.init()
    devices = tuple(sdl2_audio.get_audio_device_names(capture_devices))
    mixer.quit()
    return devices

devices = list(get_devices())

SOUND_PATH = path.join(path.dirname(path.realpath(__file__)), 'sounds')
CONFIG = path.join(path.dirname(path.realpath(__file__)), 'config.json')
DEVICE = None
VOLUME = 50
SEL_WIN_OPEN = False
TTS_WIN_OPEN = False

if path.isfile(CONFIG):
    config = json.load(open(CONFIG, 'r'))
    if 'device' in config:
        DEVICE = config['device']
    if 'volume' in config:
        VOLUME = config['volume']
    if 'tts' in config:
        TTS_SELECTED = config['tts']

if not os.path.isdir(SOUND_PATH):
    try:
        os.mkdir(SOUND_PATH)
    except:
        showerror('에러', 'sounds 폴더를 만들 수 없습니다!')
        exit()

# try: 
#     discord = pypresence.Presence('863718334696128533')
#     discord.connect()
#     discord.update(
#         large_image='mint_choco',
#         state='파이썬 스테레오 믹스 프로젝트',
#         details='★뀨♥라리엘♥뀨★#1004과 \앱#5120이 제작한',
#         buttons=[
#             {
#                 'label': '다운로드',
#                 'url':'https://github.com/TeamUnle/mic-tts'
#             }
#         ]
#     )
# except Exception as x:
#     print(x)
    
def play_sound(sound):
    global VOLUME, DEVICE, PLAYER
    if not path.isfile(sound):
        showerror('에러', '파일이 존재하지 않습니다!')
        return
    if not DEVICE:
        showerror('에러', '기기를 먼저 선택하세요!')
        return
    try:
        stop()
        mixer.music.load(sound)
        mixer.music.set_volume(VOLUME / 100)
        mixer.music.play(0)
        mixer.music.set_endevent(pygame.USEREVENT + 1)
    except:
        showerror('에러', '음성을 재생할 수 없습니다!')
        return
    
def tts(event):
    global VOLUME, DEVICE, TTS_SELECTED, TTS_LIST, speakers
    text = event.widget.get()
    if not text:
        return
    try:
        stop()
        ctts = TTS_LIST[TTS_SELECTED]
        if ctts == 'google':
            tts = gTTS(text=text, lang='ko')
            tts.save('tts.mp3')
        elif ctts == 'kakao':
            try:
                r = requests.get(f'https://tts-translate.kakao.com/newtone?message={parse.quote(text)}')
                r.raise_for_status()
                if len(r.content) == 360:
                    raise Exception('unexpected response')
                with open('tts.mp3', 'wb') as f:
                    f.write(r.content)
            except Exception as err:
                print(err)
                showerror('에러', '음성을 생성할 수 없습니다!\ngoogle로 대체됨')
                TTS_SELECTED = TTS_LIST.index('google')
                tts(event)
                return
        elif ctts == 'arona':
            res = trans.detect(text)
            if res.lang != 'ja':
                print('need translate')
                text = trans.translate(text, dest='ja').text
            arona_tts(text, speakers.index(name), 1, False)
        else:
            showerror('에러', '올바른 tts를 선택하세요!')
            return
    except Exception as e:
        raise e
        print(e)
        showerror('에러', '음성을 생성할 수 없습니다!')
        return
    if not path.isfile('tts.mp3'):
        showerror('에러', '음성을 생성할 수 없습니다!')
        return
    if not DEVICE:
        showerror('에러', '기기를 먼저 선택하세요!')
        return
    play_sound('tts.mp3')
    history_box.insert(0, text)
    history_box.delete(10, END)
    entry.delete(0, END)
    entry.insert(0, '')
    init_list()

def stop():
    mixer.music.stop()
    mixer.music.unload()

window = Tk()
window.title('tts!')
window.resizable(False, False)

frame = Frame(window)

history_box = Listbox(frame, width=40, height=30)

scrollbar = Scrollbar(frame)
scrollbar.pack(side='right', fill='y')

list_box = Listbox(frame, width=40, height=30, yscrollcomma=scrollbar.set)

def init_list():
    global list_box
    files = list(map(lambda x: os.path.splitext(x)[0], os.listdir('./sounds/')))
    list_box.delete(0, END)
    if not len(files):
        list_box.insert(0, 'None')
    else:
        for i in range(len(files)):
            list_box.insert(i, files[i])

init_list()

list_box.pack(side=LEFT)
history_box.pack(side=RIGHT)
scrollbar['command'] = list_box.yview

def sel_sound(event):
    selected = event.widget.curselection()
    if not len(selected):
        return
    selected = selected[0]
    selected = list_box.get(selected)
    if selected == 'None':
        return
    play_sound(path.join(SOUND_PATH, f'{selected}.mp3'))

list_box.bind('<<ListboxSelect>>', sel_sound)

def sel_history(event):
    selected = event.widget.curselection()
    if not len(selected):
        return
    selected = selected[0]
    selected = history_box.get(selected)
    if selected == 'None':
        return
    entry.delete(0, END)
    entry.insert(0, selected)

history_box.bind('<<ListboxSelect>>', sel_history)
    
stop_button = Button(
    window,
    width=30,
    command=stop,
    repeatdelay=100,
    repeatinterval=100,
    text='정지'
)

def open_sel_window():
    global SEL_WIN_OPEN, DEVICE
    if SEL_WIN_OPEN:
        return
    SEL_WIN_OPEN = True
    sel_window = Toplevel(window)
    sel_window.wm_transient(window)
    sel_window.title('select input')
    sel_window.resizable(False, False)
    sel_window.geometry('400x150')

    window.eval(f'tk::PlaceWindow {str(sel_window)} center')

    sel_comb = Combobox(sel_window, state='readonly', width=50)
        
    def sel_mic():
        global DEVICE, SEL_WIN_OPEN
        SEL_WIN_OPEN = False
        name = sel_comb.get()
        if name:
            DEVICE = name
            mixer.init(devicename=DEVICE)
            sel_window.destroy()

    sel_button = Button(
        sel_window,
        width=10,
        repeatdelay=100,
        repeatinterval=100,
        text='확인',
        command=sel_mic
    )

    sel_comb['values'] = list(devices)
    sel_comb.current(devices.index(DEVICE) if DEVICE else 0)

    sel_comb.pack(pady=10)
    sel_button.pack(side=BOTTOM, pady=20)
    
def open_sel_tts_window():
    global TTS_WIN_OPEN, TTS_SELECTED
    if TTS_WIN_OPEN:
        return
    TTS_WIN_OPEN = True
    sel_window = Toplevel(window)
    sel_window.wm_transient(window)
    sel_window.title('select tts')
    sel_window.resizable(False, False)
    sel_window.geometry('300x150')

    window.eval(f'tk::PlaceWindow {str(sel_window)} center')

    sel_comb = Combobox(sel_window, state='readonly', width=50)
        
    def sel_mic():
        global TTS_LIST, TTS_SELECTED, TTS_WIN_OPEN
        TTS_WIN_OPEN = False
        name = sel_comb.get()
        if name:
            TTS_SELECTED = TTS_LIST.index(name)
            sel_window.destroy()

    sel_button = Button(
        sel_window,
        width=10,
        repeatdelay=100,
        repeatinterval=100,
        text='확인',
        command=sel_mic
    )

    sel_comb['values'] = list(TTS_LIST)
    sel_comb.current(TTS_SELECTED)

    sel_comb.pack(pady=10)
    sel_button.pack(side=BOTTOM, pady=20)

tool_frame = Frame(window)

resel_button = Button(
    tool_frame,
    width=5,
    command=open_sel_window,
    repeatdelay=100,
    repeatinterval=100,
    text='기기'
)

tts_button = Button(
    tool_frame,
    width=5,
    command=open_sel_tts_window,
    repeatdelay=100,
    repeatinterval=100,
    text='tts'
)

reset_button = Button(
    tool_frame,
    width=5,
    command=init_list,
    repeatdelay=100,
    repeatinterval=100,
    text='리로드'
)

stop_button.pack(side=BOTTOM, pady=10)

entry = Entry(window, width=30)
entry.bind('<Return>', tts)
entry.pack(side=BOTTOM)

def set_volume(event):
    global VOLUME
    VOLUME = int(event)
    mixer.music.set_volume(VOLUME / 100)

var = IntVar()
var.set(VOLUME)
volume = Scale(
    window,
    variable=var,
    command=set_volume,
    orient='horizontal',
    showvalue=True,
    tickinterval=10,
    to=100,
    length=300,
    label='음량 조절'
)
volume.pack(side=BOTTOM)

resel_button.pack(side=LEFT, padx=10)
tts_button.pack(side=LEFT, padx=10)
reset_button.pack(side=LEFT, padx=10)

tool_frame.pack(side=BOTTOM)
frame.pack(pady=50, padx=10)

def handle_music():
    global window
    for event in pygame.event.get():
        if event.type == pygame.USEREVENT + 1:
            if not mixer.music.get_busy():
                mixer.music.unload()
    window.after(100, handle_music)

handle_music()

if not DEVICE:
    open_sel_window()
else:
    mixer.init(devicename=DEVICE)

try:
    window.mainloop()
except Exception as e:
    showerror('ERROR', '오류가 발생했습니다!')

config = {
    'device': DEVICE,
    'volume': VOLUME,
    'tts': TTS_SELECTED
}

json.dump(config, open(CONFIG, 'w'), ensure_ascii=False)


# limitation = os.getenv('SYSTEM') == 'spaces'  # limit text and audio length in huggingface spaces



# t = 'vits'
# models_tts.append((name, cover_path, speakers, lang, example,
#                     create_tts_fn(model, hps, speaker_ids),
#                     create_to_phoneme_fn(hps)))

# css = '''
#         #advanced-btn {
#             color: white;
#             border-color: black;
#             background: black;
#             font-size: .7rem !important;
#             line-height: 19px;
#             margin-top: 24px;
#             margin-bottom: 12px;
#             padding: 2px 8px;
#             border-radius: 14px !important;
#         }
#         #advanced-options {
#             display: none;
#             margin-bottom: 20px;
#         }
# '''


# if __name__ == '__main__':
#     models_tts = []
#     name = '아로나(アロナ) TTS'
#     lang = '日本語 (Japanese)'
#     example = 'おはようございます、先生。'


#     app = gr.Blocks(css=css)

#     with app:
#         gr.Markdown('![visitor badge](https://visitor-badge.glitch.me/badge?page_id=kdrkdrkdr.AronaTTS)\n\n')
        
#         for i, (name, cover_path, speakers, lang, example, tts_fn, to_phoneme_fn) in enumerate(models_tts):

#             with gr.Column():
#                 gr.Markdown(f'## {name}\n\n'
#                             f'![cover](file/{cover_path})\n\n'
#                             f'lang: {lang}')
#                 tts_input1 = gr.TextArea(label=f'Text ({max_length} words limitation)', value=example,
#                                             elem_id=f'tts-input{i}')
#                 tts_input2 = gr.Dropdown(label='Speaker', choices=speakers,
#                                             type='index', value=speakers[0])
#                 tts_input3 = gr.Slider(label='Speed', value=1, minimum=0.5, maximum=2, step=0.1)
                
#                 tts_submit = gr.Button('Generate', variant='primary')
#                 tts_output1 = gr.Textbox(label='Output Message')
#                 tts_output2 = gr.Audio(label='Output Audio', elem_id='tts-audio')
#                 tts_submit.click(tts_fn, inputs=[tts_input1, tts_input2, tts_input3],
#                                     outputs=[tts_output1, tts_output2], api_name='tts')
                
#     app.queue().launch(server_name = '0.0.0.0')
